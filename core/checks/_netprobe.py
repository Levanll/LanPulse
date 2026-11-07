"""检测单元共用的只读网络探测原语。

gateway / mtu / connectivity 三个检测单元都要解析 ping 输出，而中文 Windows 的
ping 文案（「时间」「平均」「需要拆分数据包但是设置 DF」）与英文版不同；把正则集中
在这里，避免三处各写一套、改一处漏两处。

本模块只做探测：不写配置、不下载内容、不发送任何业务数据，所有阻塞调用都带超时。
"""
from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass, field

from .. import platform_win as pw
from ..i18n import t

# --------------------------------------------------------------------------- #
# ping 输出解析
# --------------------------------------------------------------------------- #
# 「包过大且设置不分片」的反馈。中文可能是「需要拆分数据包但是设置 DF。」
# 也可能带「来自 x 的回复: 」前缀，或英文「Packet needs to be fragmented but DF set.」。
_FRAG_HINTS = ("fragmented but df set", "需要拆分数据包", "设置了 df 标志", "已设置 df")
_TIMEOUT_HINTS = ("request timed out", "请求超时")
# 注意不要用 "reply from" 做不可达判据：正常回包也含这串。只匹配真正的不可达文案。
_UNREACH_HINTS = ("destination host unreachable", "无法访问目标主机",
                  "目标主机无法访问", "传输失败")

_TIME_RE = re.compile(r"(?:时间|time)\s*[=<]\s*(\d+(?:\.\d+)?)\s*ms", re.I)
_SENT_RE = re.compile(r"(?:已发送|sent)\s*=\s*(\d+)", re.I)
_RECV_RE = re.compile(r"(?:已接收|received)\s*=\s*(\d+)", re.I)
_LOSS_RE = re.compile(r"(?:丢失|lost)\s*=\s*\d+\s*\(\s*(\d+)%", re.I)
_AVG_RE = re.compile(r"(?:平均|average)\s*=\s*(\d+(?:\.\d+)?)\s*ms", re.I)
_MIN_RE = re.compile(r"(?:最短|minimum)\s*=\s*(\d+(?:\.\d+)?)\s*ms", re.I)
_MAX_RE = re.compile(r"(?:最长|maximum)\s*=\s*(\d+(?:\.\d+)?)\s*ms", re.I)


@dataclass
class PingStats:
    """一次 ping 的结构化结果。原始文本保留在 raw，便于报告里复现结论。"""

    target: str
    sent: int = 0
    received: int = 0
    loss_pct: int = 100
    rtt_avg_ms: float | None = None
    rtt_min_ms: float | None = None
    rtt_max_ms: float | None = None
    frag_blocked: bool = False  # 目标/链路反馈「需要分片」，MTU 探测的关键信号
    timed_out: bool = False
    unreachable: bool = False
    returncode: int = 0
    raw: str = ""

    @property
    def ok(self) -> bool:
        return self.received > 0 and not self.frag_blocked

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "sent": self.sent,
            "received": self.received,
            "loss_pct": self.loss_pct,
            "rtt_avg_ms": self.rtt_avg_ms,
            "rtt_min_ms": self.rtt_min_ms,
            "rtt_max_ms": self.rtt_max_ms,
            "frag_blocked": self.frag_blocked,
            "timed_out": self.timed_out,
            "unreachable": self.unreachable,
            "returncode": self.returncode,
            "raw": self.raw[:1200],
        }


def parse_ping(target: str, text: str, returncode: int = 0) -> PingStats:
    """把 ping 输出解析为 PingStats。中英文文案都覆盖，解析不到的字段留空。"""
    low = text.lower()
    stats = PingStats(target=target, returncode=returncode, raw=text)
    stats.frag_blocked = any(h in low for h in _FRAG_HINTS)
    stats.timed_out = any(h in low for h in _TIMEOUT_HINTS)

    # 逐条回复的「时间=xms」；「时间<1ms」按 0.5ms 计，避免拉低平均值的假象。
    rtts: list[float] = []
    for seg in re.split(r"[\r\n]+", text):
        m = _TIME_RE.search(seg)
        if not m:
            continue
        if "<" in seg[m.start():m.end()] or "＜" in seg:
            rtts.append(0.5)
        else:
            rtts.append(float(m.group(1)))

    m = _SENT_RE.search(text)
    stats.sent = int(m.group(1)) if m else len(rtts)
    m = _RECV_RE.search(text)
    stats.received = int(m.group(1)) if m else len(rtts)
    m = _LOSS_RE.search(text)
    if m:
        stats.loss_pct = int(m.group(1))
    elif stats.sent:
        stats.loss_pct = round(100 * (stats.sent - stats.received) / stats.sent)

    m = _AVG_RE.search(text)
    if m:
        stats.rtt_avg_ms = float(m.group(1))
    elif rtts:
        # 只有一次回复时 Windows 也会打印统计行；缺失时用逐条值兜底。
        stats.rtt_avg_ms = round(sum(rtts) / len(rtts), 1)
    m = _MIN_RE.search(text)
    if m:
        stats.rtt_min_ms = float(m.group(1))
    elif rtts:
        stats.rtt_min_ms = min(rtts)
    m = _MAX_RE.search(text)
    if m:
        stats.rtt_max_ms = float(m.group(1))
    elif rtts:
        stats.rtt_max_ms = max(rtts)

    # 目标不可达与分片失败是两回事，分片失败时不把「来自网关的回复」算成不可达。
    stats.unreachable = any(h in low for h in _UNREACH_HINTS) and not stats.received
    return stats


def ping(
    target: str,
    *,
    count: int = 2,
    wait_ms: int = 1000,
    payload: int | None = None,
    df: bool = False,
    timeout: float = 6.0,
) -> PingStats:
    """执行一次 ping。df=True 时设置「不分片」标志，用于 MTU 探测。"""
    argv: list[str] = ["ping", "-n", str(count), "-w", str(wait_ms)]
    if df:
        argv.append("-f")
    if payload is not None:
        argv += ["-l", str(payload)]
    argv.append(target)
    rc, out = pw.run_cmd(argv, timeout=timeout)
    return parse_ping(target, out, rc)


# --------------------------------------------------------------------------- #
# TCP / DNS 探测
# --------------------------------------------------------------------------- #
@dataclass
class TcpProbe:
    host: str
    port: int
    ok: bool = False
    connect_ms: float | None = None
    error: str = ""

    def to_dict(self) -> dict:
        return {"host": self.host, "port": self.port, "ok": self.ok,
                "connect_ms": self.connect_ms, "error": self.error}


def tcp_connect(host: str, port: int, *, timeout: float = 3.0) -> TcpProbe:
    """TCP 握手探测：只建立连接后立即关闭，不发送任何应用层数据。"""
    started = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:  # 连接被拒 / 超时 / 解析失败，都是「不可达」这一种事实
        return TcpProbe(host=host, port=port, ok=False,
                        connect_ms=round((time.perf_counter() - started) * 1000, 1),
                        error=f"{type(exc).__name__}: {exc}")
    return TcpProbe(host=host, port=port, ok=True,
                    connect_ms=round((time.perf_counter() - started) * 1000, 1))


@dataclass
class ResolveProbe:
    name: str
    ok: bool = False
    ms: float | None = None
    addresses: list[str] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "ms": self.ms,
                "addresses": self.addresses, "error": self.error}


def resolve_timed(name: str, *, timeout: float = 2.0) -> ResolveProbe:
    """用 getaddrinfo 计时解析，超时用工作线程兜底（getaddrinfo 自身不接受超时）。

    dns_resolve 检测单元优先走 DnsQuery_W，这里作为非 Windows / API 不可用时的回退。
    """
    import threading

    box: dict = {}

    def worker() -> None:
        started = time.perf_counter()
        try:
            infos = socket.getaddrinfo(name, None, socket.AF_INET, socket.SOCK_STREAM)
            box["ips"] = sorted({info[4][0] for info in infos})
            box["ms"] = round((time.perf_counter() - started) * 1000, 1)
        except OSError as exc:  # 解析失败是正常结果（域名不存在 / DNS 不可用）
            box["error"] = f"{type(exc).__name__}: {exc}"
            box["ms"] = round((time.perf_counter() - started) * 1000, 1)

    thread = threading.Thread(target=worker, name=f"resolve-{name}", daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        return ResolveProbe(name=name, ok=False, ms=round(timeout * 1000, 1),
                            error=t("err.resolve_timeout", sec=f"{timeout:.1f}"))
    if "error" in box:
        return ResolveProbe(name=name, ok=False, ms=box.get("ms"), error=box["error"])
    ips = box.get("ips") or []
    if not ips:
        return ResolveProbe(name=name, ok=False, ms=box.get("ms"),
                            error=t("err.no_a_record"))
    return ResolveProbe(name=name, ok=True, ms=box.get("ms"), addresses=ips)


__all__ = [
    "PingStats",
    "TcpProbe",
    "ResolveProbe",
    "parse_ping",
    "ping",
    "tcp_connect",
    "resolve_timed",
]
