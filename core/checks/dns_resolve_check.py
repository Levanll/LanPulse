"""检测单元：域名解析与响应速度。

与其他检测项不同，这里**真实发出 DNS 查询**来量响应时间——DNS 配置看起来正确、
但解析已经坏掉的情况非常常见（上游 DNS 无响应、被运营商劫持、代理软件残留等），
只有真查一次才能发现。

实现要点：
  * 直接 ctypes 调 `dnsapi!DnsQuery_W`（A 记录），走的是 Windows 自己的解析器，
    因此结果与浏览器实际看到的一致；不加任何第三方库。
  * 每个域名最多等 2 秒、整轮最多 8 秒（超时的查询线程被放弃，进程退出时自然回收）。
  * 只做本地解析，不上传任何数据、不下载任何内容。
"""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from dataclasses import dataclass

from ..context import DiagnosticContext
from ..i18n import t
from ..i18n_args import resolve_args as _resolve_args
from ..models import CheckResult, Metric, Severity
from . import _netprobe

# 探测域名：全部为国内可直连的大站，覆盖不同 CDN 与省份调度，容错性最好。
PROBE_DOMAINS = ("www.baidu.com", "www.qq.com", "www.taobao.com", "www.bilibili.com")

# 单域名超时 2 秒 / 整轮 8 秒：再慢也已经超过「用户能感知」的阈值，
# 继续等下去只会拖长体检总时长而不改变结论。
PER_DOMAIN_TIMEOUT = 2.0
TOTAL_BUDGET = 8.0

# RTT 分级（同一次查询，含本地缓存命中）。本地 DNS 缓存命中通常 <5ms，
# 走路由器转发 5~30ms，出省出口 30~80ms；超过 150ms 用户开始能感觉到「网页慢半拍」。
EXCELLENT_MS = 60.0
NORMAL_MS = 150.0
SLOW_MS = 400.0

# 解析结果指向这些地址时，浏览器一定打不开站点：典型 HOSTS 屏蔽或 DNS 劫持特征。
BLOCKING_TARGETS = {"0.0.0.0", "127.0.0.1", "::1", "::", "255.255.255.255"}
HIJACK_CRITICAL_COUNT = 2  # 命中 2 个及以上大站被屏蔽，就按严重处理

# 返回码 → i18n key。文案在语言包里，这里只保留码表。
_RC_KEYS = {
    0: "rc.0",
    9003: "rc.9003",
    9002: "rc.9002",
    9501: "rc.9501",
    1460: "rc.1460",
    11001: "rc.11001",
    11002: "rc.11002",
    11003: "rc.11003",
    11004: "rc.11004",
}


@dataclass
class _Probe:
    name: str
    ok: bool
    ms: float | None
    addresses: list[str]
    error: str = ""
    via: str = "dnsapi"

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "ms": self.ms,
                "addresses": self.addresses, "error": self.error, "via": self.via}


class DnsResolveCheck:
    check_id = "dns_resolve"
    title = "check.dns_resolve.title"
    category = "check.dns_resolve.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        started = time.perf_counter()
        probes: list[_Probe] = []
        for name in PROBE_DOMAINS:
            remaining = TOTAL_BUDGET - (time.perf_counter() - started)
            if remaining <= 0.2:
                break
            probes.append(_resolve(name, timeout=min(PER_DOMAIN_TIMEOUT, remaining)))

        ok = [p for p in probes if p.ok]
        failed = [p for p in probes if not p.ok]
        times = [p.ms for p in ok if p.ms is not None]
        avg = round(sum(times) / len(times), 1) if times else None

        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        if not probes:
            # 只在系统时间被大幅跳变等极端情况下出现；没有样本就不能下结论。
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.SKIP,
                summary=t("check.dns_resolve.summary_skip"),
                summary_key="check.dns_resolve.summary_skip",
                detail=t("check.dns_resolve.detail_skip", budget=f"{TOTAL_BUDGET:.0f}"),
                metrics=[Metric("metric.total_budget",
                                t("value.seconds", n=f"{TOTAL_BUDGET:.0f}"), ok=False)],
                evidence={"probes": [], "budget": TOTAL_BUDGET},
            )

        metrics.append(Metric(
            "metric.probe_domains", str(len(probes)),
            t("check.dns_resolve.note.probe_domains", ok=len(ok), fail=len(failed)),
            ok=not failed))
        for p in probes:
            status = (t("value.ms", n=f"{p.ms:.0f}") if (p.ok and p.ms is not None)
                      else (p.error or t("status.failed")))
            metrics.append(Metric(p.name, status, t("sep.list").join(p.addresses[:4]),
                                  ok=p.ok))
        if avg is not None:
            metrics.append(Metric("metric.avg_resolve_ms", t("value.ms", n=f"{avg:.0f}"),
                                  _grade_text(avg), ok=avg < NORMAL_MS))
            metrics.append(Metric("metric.min_max_ms",
                                  f"{min(times):.0f}ms / {max(times):.0f}ms"))

        # ---- 全部失败 ----
        bad: list[_Probe] = []
        if not ok:
            severity = Severity.CRITICAL
            problems.append(t("check.dns_resolve.problem.all_fail", n=len(probes)))
            advice.append(t("check.dns_resolve.advice.flush"))
            actions.append("dns.flush_cache")
        else:
            # ---- 慢 ----
            if avg is not None and avg > SLOW_MS:
                severity = _worse(severity, Severity.CRITICAL)
                problems.append(
                    t("check.dns_resolve.problem.avg_very_slow", ms=f"{avg:.0f}"))
                advice.append(t("check.dns_resolve.advice.switch_public"))
                actions.append("dns.set_public")
            elif avg is not None and avg > NORMAL_MS:
                severity = _worse(severity, Severity.WARN)
                problems.append(t("check.dns_resolve.problem.avg_slow",
                                  ms=f"{avg:.0f}", limit=f"{NORMAL_MS:.0f}"))
                advice.append(t("check.dns_resolve.advice.try_ali_tencent"))
                actions.append("dns.set_public")
            # ---- 部分失败 ----
            if failed and len(failed) < len(probes):
                severity = _worse(severity, Severity.WARN)
                problems.append(t("check.dns_resolve.problem.partial", n=len(failed)))
                actions.append("dns.flush_cache")
            # ---- 劫持 / 屏蔽 ----
            bad = [p for p in ok if any(a in BLOCKING_TARGETS for a in p.addresses)]
            if bad:
                severity = _worse(severity, Severity.CRITICAL if len(bad) >= HIJACK_CRITICAL_COUNT
                                  else Severity.WARN)
                names = t("sep.list").join(f"{p.name}→{p.addresses[0]}" for p in bad[:4])
                problems.append(t("check.dns_resolve.problem.hijacked",
                                  n=len(bad), names=names))
                advice.append(t("check.dns_resolve.advice.check_hosts"))
                actions.extend(["dns.flush_cache", "hosts.clean_bad_lines"])

        metrics.append(Metric(
            "metric.resolve_via", probes[0].via if probes else t("status.not_run"),
            t("value.dnsapi") if probes and probes[0].via == "dnsapi"
            else t("value.getaddrinfo"),
            ok=True))

        detail_lines = []
        for p in probes:
            if p.ok and p.ms is not None:
                ips = t("sep.list").join(p.addresses[:4]) or t("check.dns_resolve.no_a_record")
                detail_lines.append(t("check.dns_resolve.detail.ok",
                                      name=p.name, ips=ips, ms=f"{p.ms:.0f}"))
            else:
                detail_lines.append(t("check.dns_resolve.detail.fail",
                                      name=p.name, err=p.error))
        ok_key, ok_args = _ok_summary(avg, ok)
        summary_text = t(ok_key, **_resolve_args(ok_args))
        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            summary=summary_text,
            summary_key="" if problems else ok_key,
            summary_args={} if problems else ok_args,
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=_unique(actions),
            evidence={
                "probes": [p.to_dict() for p in probes],
                "avg_ms": avg,
                "thresholds": {"excellent": EXCELLENT_MS, "normal": NORMAL_MS,
                               "slow": SLOW_MS, "per_domain_timeout": PER_DOMAIN_TIMEOUT,
                               "total_budget": TOTAL_BUDGET},
                "hijacked": [{"name": p.name, "addresses": p.addresses} for p in bad],
            },
        )


# --------------------------------------------------------------------------- #
# DnsQuery_W 绑定
# --------------------------------------------------------------------------- #
_DNS_TYPE_A = 1
_DNS_QUERY_BYPASS_CACHE = 0x00000008
_DNS_FREE_RECORD_LIST = 1


class _DNS_RECORD(ctypes.Structure):
    pass


# 与 Windows 的 DNS_RECORD 前段布局对齐：pNext / pszName / wType / wDataLength /
# Flags / dwTtl / dwReserved，之后是 Data 联合体；A 记录即 4 字节 IP 地址。
# 只读前段字段，其余联合体成员不参与解析。
_DNS_RECORD._fields_ = [
    ("pNext", ctypes.c_void_p),
    ("pszName", ctypes.c_wchar_p),
    ("wType", ctypes.c_ushort),
    ("wDataLength", ctypes.c_ushort),
    ("Flags", ctypes.c_uint32),
    ("dwTtl", ctypes.c_uint32),
    ("dwReserved", ctypes.c_uint32),
    ("A", ctypes.c_uint32),
]

_PDNS_RECORD = ctypes.POINTER(_DNS_RECORD)
_dnsapi = None


def _load_dnsapi():
    """按需加载 dnsapi.dll。非 Windows 或加载失败时返回 None，由调用方回退。"""
    global _dnsapi
    if _dnsapi is not None:
        return _dnsapi or None
    if sys.platform != "win32":
        _dnsapi = False
        return None
    try:
        lib = ctypes.WinDLL("dnsapi", use_last_error=True)
        lib.DnsQuery_W.argtypes = [ctypes.c_wchar_p, ctypes.c_ushort, ctypes.c_uint32,
                                   ctypes.c_void_p, ctypes.POINTER(_PDNS_RECORD),
                                   ctypes.c_void_p]
        lib.DnsQuery_W.restype = ctypes.c_long
        lib.DnsRecordListFree.argtypes = [_PDNS_RECORD, ctypes.c_int]
        lib.DnsRecordListFree.restype = None
        _dnsapi = lib
    except (OSError, AttributeError):
        # 只可能发生在非 Windows 或系统 DLL 缺位，此时按回退路径处理，不影响体检。
        _dnsapi = False
        return None
    return lib


def _query_once(name: str) -> tuple[int, list[str]]:
    """执行一次 DnsQuery_W，返回 (错误码, A 记录地址列表)。"""
    lib = _load_dnsapi()
    if lib is None:
        raise RuntimeError(t("err.dnsapi_unavailable"))
    result = _PDNS_RECORD()
    rc = lib.DnsQuery_W(name, _DNS_TYPE_A, _DNS_QUERY_BYPASS_CACHE,
                        None, ctypes.byref(result), None)
    addresses: list[str] = []
    try:
        node = result
        while node:
            record = node.contents
            if record.wType == _DNS_TYPE_A:
                raw = record.A
                addresses.append(".".join(str((raw >> shift) & 0xFF)
                                          for shift in (0, 8, 16, 24)))
            node = ctypes.cast(record.pNext, _PDNS_RECORD) if record.pNext else _PDNS_RECORD()
    finally:
        if result:
            lib.DnsRecordListFree(result, _DNS_FREE_RECORD_LIST)
    return rc, addresses


def _resolve(name: str, *, timeout: float) -> _Probe:
    """带硬超时的单域名解析：worker 线程跑 DnsQuery，主线程只等到 deadline。

    线程无法被强制杀死，但它是 daemon 且只做一次 API 调用，超时后即被放弃，
    不会泄漏系统资源，也不会阻塞体检结束。
    """
    box: dict = {}

    def worker() -> None:
        try:
            started = time.perf_counter()
            rc, addresses = _query_once(name)
            ms = round((time.perf_counter() - started) * 1000, 1)
            box.update(rc=rc, addresses=addresses, ms=ms, via="dnsapi")
        except (OSError, RuntimeError) as exc:
            box.update(error=f"{type(exc).__name__}: {exc}", via="dnsapi")

    thread = threading.Thread(target=worker, name=f"dnsquery-{name}", daemon=True)
    thread.start()
    thread.join(timeout)

    if thread.is_alive():
        return _Probe(name=name, ok=False, ms=round(timeout * 1000, 1), addresses=[],
                      error=t("err.resolve_timeout", sec=f"{timeout:.1f}"))
    if "error" in box:
        # dnsapi 不可用（非 Windows 等）：换标准库计时，保证功能可用而非直接失败。
        fallback = _netprobe.resolve_timed(name, timeout=timeout)
        return _Probe(name=name, ok=fallback.ok, ms=fallback.ms,
                      addresses=fallback.addresses, error=fallback.error, via="getaddrinfo")
    rc = int(box.get("rc", 0))
    addresses = list(box.get("addresses") or [])
    if rc != 0 or not addresses:
        # DnsQuery 返回 0 但没有 A 记录（只有 CNAME/AAAA）也视为取不到地址
        return _Probe(name=name, ok=False, ms=box.get("ms"), addresses=addresses,
                      error=t("err.dnsquery_rc", rc=rc, text=_rc_text(rc)))
    return _Probe(name=name, ok=True, ms=box.get("ms"), addresses=addresses)


def _rc_text(rc: int) -> str:
    return t(_RC_KEYS.get(rc, "rc.unknown"))


def _grade_text(avg: float) -> str:
    return t(_grade_key(avg))


def _grade_key(avg: float) -> str:
    """返回等级对应的 i18n key（而非译文）。

    用于 summary_args：渲染时会按当前语言解析，
    否则英文界面里会残留中文的「优秀/良好」。
    """
    if avg < EXCELLENT_MS:
        return "grade.excellent"
    if avg < NORMAL_MS:
        return "grade.normal"
    if avg < SLOW_MS:
        return "grade.slow"
    return "grade.very_slow"


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _ok_summary(avg: float | None, ok: list[_Probe]) -> tuple[str, dict]:
    if avg is None:
        return "check.dns_resolve.summary_ok_noms", {"n": len(ok)}
    # grade 同样传 key，避免英文界面里出现中文等级词
    return ("check.dns_resolve.summary_ok",
            {"n": len(ok), "ms": f"{avg:.0f}", "grade": _grade_key(avg)})


__all__ = ["DnsResolveCheck", "PROBE_DOMAINS"]
