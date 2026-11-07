"""检测单元：HOSTS 文件。

HOSTS 是唯一能「不经过 DNS」直接改写域名解析结果的地方，因此也是广告屏蔽工具、
破解补丁、恶意软件的共同落点。这里只读地做行级解析，把结论拆成三类：

  * normal   —— 普通自定义映射（例如内网服务器别名）；
  * blocked  —— 映射到 0.0.0.0 / 127.0.0.1 等黑洞地址（屏蔽型，常见于广告拦截与破解补丁）；
  * hijacked —— 命中常见大站清单（劫持型，无论指向哪个 IP）。

屏蔽型本身不是病毒：大量正经工具（如某些广告拦截脚本）就是这么写。因此屏蔽型只给
WARN 并在 summary 里说清「做了屏蔽」，真正高危的是劫持型（大站被指到第三方 IP）。

`parse_hosts` 是**纯函数**，不读文件、不改文件、不打印，供修复引擎复用同一套判定口径，
避免检测方与修复方各写一套规则、互相打架。`reason` 字段是派生的解释文本（不是原始
数据），因此在这里就用 t() 渲染成当前语言。
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field

from .. import platform_win as pw
from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity

# 黑洞地址：写进 HOSTS 就等于「该域名不可访问」。
BLACKHOLE_IPS = frozenset({"0.0.0.0", "127.0.0.1", "::1", "::"})

# 这些域名指向黑洞地址是系统默认行为（本机名解析），永远不算可疑。
DEFAULT_LOCAL_NAMES = frozenset({
    "localhost", "localhost.localdomain", "localhost4", "localhost4.localdomain4",
    "localhost6", "localhost6.localdomain6", "ip6-localhost", "ip6-loopback",
    "broadcasthost", "local", "localdomain",
})

# 常见大站清单（含子域匹配）。劫持这些域名会直接导致「能上网但打不开常用网站」，
# 也是恶意软件劫持广告/搜索流量的典型手法，因此单列一档高危。
WATCHED_DOMAINS = (
    "baidu.com", "qq.com", "weixin.qq.com", "wechat.com", "tencent.com",
    "taobao.com", "tmall.com", "alipay.com", "alicdn.com", "aliyun.com",
    "jd.com", "sina.com.cn", "weibo.com", "163.com", "126.net",
    "bilibili.com", "douyin.com", "kuaishou.com", "zhihu.com", "xiaohongshu.com",
    "microsoft.com", "windowsupdate.com", "live.com", "office.com", "msn.com",
    "apple.com", "icloud.com", "google.com", "gmail.com", "youtube.com",
    "github.com", "steamcommunity.com", "steampowered.com", "epicgames.com",
    "adobe.com", "nvidia.com", "amd.com", "intel.com",
)

# 正常 HOSTS 至少包含 localhost 两行；只有 1 行有效内容通常意味着被覆盖或损坏。
MIN_PLAUSIBLE_LINES = 2
DETAIL_LIMIT = 20


@dataclass
class HostsEntry:
    """一条有效映射行。"""

    line_no: int
    raw: str
    ip: str
    hostnames: list[str] = field(default_factory=list)
    kind: str = "normal"  # normal | blocked | hijacked
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "line_no": self.line_no,
            "raw": self.raw,
            "ip": self.ip,
            "hostnames": self.hostnames,
            "kind": self.kind,
            "reason": self.reason,
        }


@dataclass
class HostsAnalysis:
    """parse_hosts 的完整结果。"""

    entries: list[HostsEntry] = field(default_factory=list)
    blocked: list[HostsEntry] = field(default_factory=list)
    suspicious: list[HostsEntry] = field(default_factory=list)
    hijacked: list[HostsEntry] = field(default_factory=list)
    total_lines: int = 0
    byte_size: int = 0

    def to_dict(self) -> dict:
        return {
            "entries": [e.to_dict() for e in self.entries],
            "blocked": [e.to_dict() for e in self.blocked],
            "suspicious": [e.to_dict() for e in self.suspicious],
            "hijacked": [e.to_dict() for e in self.hijacked],
            "total_lines": self.total_lines,
            "byte_size": self.byte_size,
        }


class HostsCheck:
    check_id = "hosts"
    title = "check.hosts.title"
    category = "check.hosts.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        try:
            text = ctx.hosts_text
        except OSError as exc:
            # 文件不存在或没权限读：这是真实故障（HOSTS 被安全软件锁死也会这样），
            # 不能当成「没有记录」处理。
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.CRITICAL,
                summary=t("check.hosts.summary_read_error", err=exc.__class__.__name__),
                summary_key="check.hosts.summary_read_error",
                summary_args={"err": exc.__class__.__name__},
                detail=t("check.hosts.detail_read_error", path=pw.HOSTS_PATH, err=exc),
                metrics=[Metric("metric.file_path", pw.HOSTS_PATH, ok=False)],
                advice=["check.hosts.advice.admin_notepad"],
                action_ids=["hosts.restore_default"],
                evidence={"path": pw.HOSTS_PATH, "error": str(exc)},
            )

        analysis = parse_hosts(text)
        metrics: list[Metric] = [
            Metric("metric.file_size", t("value.bytes", n=analysis.byte_size), pw.HOSTS_PATH),
            Metric("metric.total_lines", str(analysis.total_lines)),
            Metric("metric.mapping_lines", str(len(analysis.entries)),
                   t("check.hosts.note.mapping_lines")),
            Metric("metric.blocked_records", str(len(analysis.blocked)),
                   t("check.hosts.note.blocked"),
                   ok=not analysis.blocked),
            Metric("metric.hijack_records", str(len(analysis.hijacked)),
                   t("check.hosts.note.hijacked"), ok=not analysis.hijacked),
            Metric("metric.suspicious_total", str(len(analysis.suspicious)),
                   ok=not analysis.suspicious),
        ]

        problems: list[str] = []
        advice: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        if analysis.hijacked:
            severity = Severity.CRITICAL
            names = t("sep.list").join(
                f"{h.hostnames[0]}→{h.ip}" for h in analysis.hijacked[:3] if h.hostnames)
            problems.append(t("check.hosts.problem.hijacked",
                              n=len(analysis.hijacked), names=names))
            advice.append(t("check.hosts.advice.clean"))
            actions.append("hosts.clean_bad_lines")

        if analysis.blocked:
            severity = _worse(severity, Severity.WARN)
            problems.append(t("check.hosts.problem.blocked", n=len(analysis.blocked)))
            advice.append(t("check.hosts.advice.blocked"))
            actions.append("hosts.clean_bad_lines")

        if analysis.total_lines < MIN_PLAUSIBLE_LINES and not analysis.entries:
            severity = Severity.CRITICAL
            problems.append(t("check.hosts.problem.near_empty"))
            advice.append(t("check.hosts.advice.restore"))
            actions.append("hosts.restore_default")

        if analysis.byte_size == 0:
            severity = Severity.CRITICAL
            problems.append(t("check.hosts.problem.zero"))

        detail_lines: list[str] = []
        if analysis.suspicious:
            detail_lines.append(t("check.hosts.detail.suspicious_head", n=DETAIL_LIMIT))
            for entry in analysis.suspicious[:DETAIL_LIMIT]:
                detail_lines.append(t("check.hosts.detail.suspicious_line",
                                      line=entry.line_no, raw=entry.raw.strip(),
                                      reason=entry.reason))
            if len(analysis.suspicious) > DETAIL_LIMIT:
                detail_lines.append(t("check.hosts.detail.more",
                                      n=len(analysis.suspicious) - DETAIL_LIMIT))
        else:
            detail_lines.append(t("check.hosts.detail.none"))
        if analysis.entries:
            detail_lines.append(t("check.hosts.detail.entries_head", n=len(analysis.entries)))
            for entry in analysis.entries[:DETAIL_LIMIT]:
                detail_lines.append(t("check.hosts.detail.entry",
                                      line=entry.line_no, ip=entry.ip,
                                      hosts=" ".join(entry.hostnames)))

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            summary=(t("sep.summary").join(problems) if problems
                     else t("check.hosts.summary_ok", n=len(analysis.entries))),
            summary_key="" if problems else "check.hosts.summary_ok",
            summary_args={} if problems else {"n": len(analysis.entries)},
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=_unique(actions),
            evidence=analysis.to_dict() | {"path": pw.HOSTS_PATH},
        )


def parse_hosts(text: str) -> HostsAnalysis:
    """纯函数：解析 HOSTS 原文，返回结构化的分析结果。

    不读文件、不写文件、不抛异常（非法行直接跳过），可被单元测试与修复引擎直接复用。
    byte_size 按 UTF-8 编码长度计算，与实际文件字节数一致（HOSTS 通常是 ASCII）。
    """
    analysis = HostsAnalysis(byte_size=len(text.encode("utf-8", errors="surrogateescape")))
    if not text:
        return analysis
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    analysis.total_lines = len(lines)
    seen_lines: set[int] = set()

    for index, raw in enumerate(lines, start=1):
        parsed = _parse_line(index, raw)
        if parsed is None:
            continue
        analysis.entries.append(parsed)
        blocked = parsed.kind == "blocked"
        hijacked = parsed.kind == "hijacked"
        if blocked:
            analysis.blocked.append(parsed)
        if hijacked:
            analysis.hijacked.append(parsed)
        if (blocked or hijacked) and index not in seen_lines:
            seen_lines.add(index)
            analysis.suspicious.append(parsed)

    analysis.suspicious.sort(key=lambda e: e.line_no)
    return analysis


def _parse_line(line_no: int, raw: str) -> HostsEntry | None:
    """解析单行。非映射行（注释/空行/格式错误）返回 None。"""
    body = raw.split("#", 1)[0].strip()
    if not body:
        return None
    parts = body.split()
    if len(parts) < 2:
        return None
    ip_text, names = parts[0], parts[1:]
    try:
        ip = str(ipaddress.ip_address(ip_text))
    except ValueError:
        return None
    hostnames = [n.lower().rstrip(".") for n in names if n and not n.startswith("#")]
    if not hostnames:
        return None

    entry = HostsEntry(line_no=line_no, raw=raw.rstrip(), ip=ip, hostnames=hostnames)
    reasons: list[str] = []

    if _is_blackhole(ip) and not _all_default_names(hostnames):
        reasons.append(t("check.hosts.reason.blackhole", ip=ip))
    watched = _watched_hits(hostnames)
    if watched:
        reasons.append(t("check.hosts.reason.watched", name=watched[0]))

    if watched:
        entry.kind = "hijacked"
    elif reasons:
        entry.kind = "blocked"
    entry.reason = t("sep.summary").join(reasons)
    return entry


def _is_blackhole(ip: str) -> bool:
    return ip in BLACKHOLE_IPS


def _all_default_names(hostnames: list[str]) -> bool:
    return all(name in DEFAULT_LOCAL_NAMES for name in hostnames)


def _watched_hits(hostnames: list[str]) -> list[str]:
    """返回命中「常见大站」清单的域名（子域也算命中）。"""
    hits: list[str] = []
    for name in hostnames:
        for watched in WATCHED_DOMAINS:
            if name == watched or name.endswith("." + watched):
                hits.append(name)
                break
    return hits


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


__all__ = [
    "HostsCheck",
    "HostsEntry",
    "HostsAnalysis",
    "parse_hosts",
    "WATCHED_DOMAINS",
    "BLACKHOLE_IPS",
    "DEFAULT_LOCAL_NAMES",
]
