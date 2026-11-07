"""检测单元：DNS 服务器配置。

只看「配了没配、配得合不合理」，不发任何查询。真正的解析速度由 dns_resolve 负责，
两者分工明确，避免同一个失败被两处重复报错。

判定口径：
  * 没有 DNS 服务器 → CRITICAL（域名一个都解析不了，网页全打不开）；
  * DNS 指向回环 / 0.0.0.0 但没有本机 DNS 服务在监听 → WARN（典型残留配置）；
  * 只配了境外公共 DNS → INFO（国内直连 8.8.8.8 常见 100~300ms，能通但慢）。
"""
from __future__ import annotations

import socket

from .. import platform_win as pw
from ..context import DiagnosticContext
from ..i18n import t
from ..i18n_args import resolve_args as _resolve_args
from ..models import CheckResult, Metric, Severity

# 已知公共 DNS → i18n key。归属名用于报告里说人话：
# 用户看到「阿里 223.5.5.5」比看到一串数字更踏实。
KNOWN_DNS: dict[str, str] = {
    "223.5.5.5": "dns.owner.aliyun",
    "223.6.6.6": "dns.owner.aliyun",
    "119.29.29.29": "dns.owner.tencent",
    "182.254.116.116": "dns.owner.tencent",
    "114.114.114.114": "dns.owner.dns114",
    "114.114.115.115": "dns.owner.dns114",
    "180.76.76.76": "dns.owner.baidu",
    "8.8.8.8": "dns.owner.google",
    "8.8.4.4": "dns.owner.google",
    "1.1.1.1": "dns.owner.cloudflare",
    "1.0.0.1": "dns.owner.cloudflare",
    "9.9.9.9": "dns.owner.quad9",
    "149.112.112.112": "dns.owner.quad9",
    "208.67.222.222": "dns.owner.opendns",
    "208.67.220.220": "dns.owner.opendns",
    "101.226.4.6": "dns.owner.chinatelecom",
    "218.30.118.6": "dns.owner.ct",
    "180.184.1.1": "dns.owner.bytedance",
    "180.184.2.2": "dns.owner.bytedance",
    "117.50.10.10": "dns.owner.onedns",
    "52.80.66.66": "dns.owner.onedns",
}

#: 自定义/运营商归属的 key，供「是否是已知公共 DNS」判定使用。
OWNER_CUSTOM = "dns.owner.custom"
OWNER_LOOPBACK = "dns.owner.loopback"

# 境外 DNS：国内直连时单次解析常在 100ms 以上，仅作提示不判故障。
OVERSEAS_DNS = {"8.8.8.8", "8.8.4.4", "1.1.1.1", "1.0.0.1",
                "9.9.9.9", "149.112.112.112", "208.67.222.222", "208.67.220.220"}

# DNS 服务器数量：1 个没有冗余，>4 个多为软件乱写，都会降低排障效率。
DNS_COUNT_OK_MAX = 4
DNS_PROBE_TIMEOUT = 1.0


class DnsServerCheck:
    check_id = "dns_server"
    title = "check.dns_server.title"
    category = "check.dns_server.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        primary = ctx.primary
        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        adapters = ctx.adapters
        # 以 CIM 采集结果为主（同一次快照），netsh 结果用于交叉验证与「静态/自动」判定。
        netsh_map, netsh_static = _netsh_servers(ctx)
        cim_servers = list(primary.dns_v4) if primary else []
        interface = primary.name if primary else t("value.no_primary_adapter")
        servers = cim_servers or netsh_map.get(interface, [])
        static = netsh_static.get(interface, not (primary.dhcp if primary else True))

        metrics.append(Metric("metric.interface", interface,
                              primary.description if primary else t("common.none")))
        metrics.append(Metric("metric.dns_count", str(len(servers)),
                              t("sep.summary").join(servers) if servers
                              else t("status.not_configured"),
                              ok=0 < len(servers) <= DNS_COUNT_OK_MAX))
        metrics.append(Metric("metric.config_mode",
                              t("value.static_manual") if static else t("value.dhcp_issued")))

        # ---- 无 DNS ----
        if not servers:
            severity = Severity.CRITICAL
            problems.append(t("check.dns_server.problem.no_dns", interface=interface))
            advice.append(t("check.dns_server.advice.restore_dhcp"))
            actions.append("dns.restore_dhcp")
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=severity,
                summary=t("sep.summary").join(problems),
        summary_key="" if problems else "check.dns_server.summary_ok",
                detail="\n".join(
                    t("check.dns_server.detail.iface", name=a.name,
                      servers=", ".join(a.dns_v4) or t("value.no_dns"))
                    for a in adapters[:10]),
                metrics=metrics,
                advice=advice,
                action_ids=actions,
                evidence={"servers": [], "interface": interface,
                          "adapters": [a.to_dict() for a in adapters]},
            )

        # ---- 归属识别（存 key，渲染时翻译）----
        labeled: list[tuple[str, str]] = [(s, KNOWN_DNS.get(s) or _guess_owner_key(s))
                                          for s in servers]
        overseas_only = all(s in OVERSEAS_DNS for s in servers)
        custom = [s for s, owner in labeled if owner == OWNER_CUSTOM]

        # ---- 回环 / 无效地址 ----
        for ip in servers:
            if ip in ("0.0.0.0", "::", "255.255.255.255"):
                severity = _worse(severity, Severity.WARN)
                problems.append(t("check.dns_server.problem.invalid_addr", ip=ip))
                advice.append(t("check.dns_server.advice.invalid_addr"))
                actions.append("dns.restore_dhcp")
            elif ip.startswith("127.") or ip == "::1":
                listening = _loopback_dns_listening()
                if listening:
                    severity = _worse(severity, Severity.INFO)
                    metrics.append(Metric("metric.loopback_dns", t("status.yes"),
                                          t("check.dns_server.note.loopback_on", ip=ip), ok=True))
                else:
                    severity = _worse(severity, Severity.WARN)
                    problems.append(t("check.dns_server.problem.loopback", ip=ip))
                    advice.append(t("check.dns_server.advice.loopback"))
                    actions.append("dns.restore_dhcp")
                    metrics.append(Metric("metric.loopback_dns", t("status.no"),
                                          t("check.dns_server.note.loopback_off", ip=ip),
                                          ok=False))

        # ---- 数量 ----
        if len(servers) > DNS_COUNT_OK_MAX:
            severity = _worse(severity, Severity.INFO)
            problems.append(t("check.dns_server.problem.too_many", n=len(servers)))
            advice.append(t("check.dns_server.advice.too_many"))

        # ---- 只有境外 DNS ----
        if overseas_only:
            severity = _worse(severity, Severity.INFO)
            problems.append(t("check.dns_server.problem.overseas"))
            metrics.append(Metric("metric.dns_route", t("value.overseas_only"),
                                  t("check.dns_server.note.overseas"), ok=False))
            advice.append(t("check.dns_server.advice.overseas"))

        metrics.append(Metric(
            "metric.dns_owner",
            t("sep.summary").join(
                t("check.dns_server.owner_pair", ip=s, owner=t(owner))
                for s, owner in labeled),
            t("check.dns_server.note.owner_custom", n=len(custom)) if custom
            else t("check.dns_server.note.owner_known"),
            ok=True))
        if not static:
            metrics.append(Metric("metric.dhcp_issued", t("status.yes"),
                                  t("check.dns_server.note.dhcp"), ok=True))

        detail_lines = [t("check.dns_server.detail.owner", ip=ip, owner=t(owner))
                        for ip, owner in labeled]
        detail_lines += [
            t("check.dns_server.detail.iface", name=a.name,
              servers=", ".join(a.dns_v4) or t("value.no_dns"))
            for a in adapters[:8]
        ]
        ok_key, ok_args = _ok_summary(labeled, static)
        summary_text = (t("sep.summary").join(problems) if problems
                        else t(ok_key, **_resolve_args(ok_args)))
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
            action_ids=actions,
            evidence={
                "interface": interface,
                "servers": servers,
                "static": static,
                "labeled": [{"ip": s, "owner": o} for s, o in labeled],
                "netsh": {k: v for k, v in netsh_map.items()},
            },
        )


def _netsh_servers(ctx: DiagnosticContext) -> tuple[dict[str, list[str]], dict[str, bool]]:
    """解析 `netsh interface ipv4 show dnsservers`（不带网卡名，一次看全部）。

    返回 (网卡名 → DNS 列表, 网卡名 → 是否静态)。命令失败时返回空表，由 CIM 数据兜底。
    """
    rc, out = ctx.cmd(("netsh", "interface", "ipv4", "show", "dnsservers"), timeout=15)
    if rc != 0 or not out:
        return {}, {}
    return parse_netsh_dnsservers(out)


def parse_netsh_dnsservers(text: str) -> tuple[dict[str, list[str]], dict[str, bool]]:
    """解析 netsh dnsservers 输出。中英文表头都兼容。

    实际排版（中文 Windows 10/11）：
        接口 "以太网" 的配置
            静态配置的 DNS 服务器:            223.5.5.5
                                                  223.6.6.6
    英文版：
        Configuration for interface "Ethernet"
            Statically Configured DNS Servers:    223.5.5.5

    注意网卡名本身可能含空格并带引号，因此用引号定位而不是按空格切分；
    续行是无表头的纯 IP 行，靠「缩进 + 全为 IP」识别。
    """
    servers: dict[str, list[str]] = {}
    static: dict[str, bool] = {}
    current: str | None = None
    collecting = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        head = line.strip()
        if not head:
            collecting = False
            continue
        if _is_interface_header(head):
            current = _interface_name(head)
            servers.setdefault(current, [])
            collecting = False
            continue
        if current is None:
            continue
        low = head.lower()
        if "dns" in low and ("服务器" in head or "server" in low):
            collecting = True
            static[current] = ("静态" in head) or ("static" in low)
            body = head.split(":", 1)[1].strip() if ":" in head else head
            if body.lower() in ("none", "无") or body.rstrip("。.") == "无":
                continue
            for ip in pw.IPV4_RE.findall(body):
                if pw.is_valid_ipv4(ip) and ip not in servers[current]:
                    servers[current].append(ip)
            continue
        if collecting and line.startswith((" ", "\t")):
            ips = [ip for ip in pw.IPV4_RE.findall(head) if pw.is_valid_ipv4(ip)]
            if ips:
                for ip in ips:
                    if ip not in servers[current]:
                        servers[current].append(ip)
                continue
            collecting = False
        else:
            collecting = False
    return servers, static


def _is_interface_header(head: str) -> bool:
    low = head.lower()
    return (
        ('"' in head and ("的配置" in head or "configuration" in low))
        or low.startswith("configuration for interface")
        or (head.startswith("接口") and "配置" in head)
    )


def _interface_name(head: str) -> str:
    if '"' in head:
        parts = head.split('"')
        if len(parts) >= 3:
            return parts[1]
    return head.split(":", 1)[0].strip()


def _loopback_dns_listening() -> bool:
    """本机 127.0.0.1:53 是否有服务监听。只做一次 TCP 探测，1 秒超时。"""
    try:
        with socket.create_connection(("127.0.0.1", 53), timeout=DNS_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def _guess_owner_key(ip: str) -> str:
    """未知地址的粗略归属，返回 i18n key：内网 → loopback，其余 → custom。"""
    parts = ip.split(".")
    if len(parts) == 4 and parts[0].isdigit():
        first = int(parts[0])
        second = int(parts[1])
        if first == 10 or (first == 172 and 16 <= second <= 31) or (first == 192 and second == 168):
            return OWNER_LOOPBACK
    return OWNER_CUSTOM


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


def _ok_summary(labeled: list[tuple[str, str]], static: bool) -> tuple[str, dict]:
    """返回 (key, args)。

    head 是"IP + 归属"的拼接串，其片段本身也要按语言生成，
    因此不在这里拼好——若在此拼成中文，英文界面会出现
    「DNS configuration is healthy (手动指定): 223.5.5.5（阿里公共 DNS）」这种混排。
    改为传出 (ip, owner_key)，由渲染层按当前语言拼。
    """
    mode_key = "value.manual_specified" if static else "value.dhcp_issued"
    return (
        "check.dns_server.summary_ok",
        {
            "mode": mode_key,
            "head_parts": [
                {"key": "check.dns_server.owner_pair_full",
                 "args": {"ip": ip, "owner": owner}}
                for ip, owner in labeled[:3]
            ],
        },
    )


__all__ = ["DnsServerCheck", "parse_netsh_dnsservers", "KNOWN_DNS"]
