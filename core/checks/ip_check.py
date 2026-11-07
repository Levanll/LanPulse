"""检测单元：IP 地址配置。

回答两个问题：
  1. 当前上网网卡拿到的 IPv4 是否可用（APIPA / 无地址都不行）；
  2. 地址、子网、网关三者是否自洽（静态 IP 配错掩码或网关时，内网通、外网断）。

私有地址判定走真实网段计算（ipaddress 模块），不做字符串前缀硬匹配——
`172.16.0.0/12` 是 172.16–172.31，字符串 `startswith("172.")` 会把 172.32.x.x
这种公网地址误判为内网。
"""
from __future__ import annotations

import ipaddress

from ..context import DiagnosticContext
from ..i18n import t
from ..i18n_args import resolve_args as _resolve_args
from ..models import CheckResult, Metric, Severity

# 手工静态 IP 且与网关不同网段时，能否上网完全取决于是否有额外路由；
# 这不是「一定坏」，因此是 WARN 而不是 CRITICAL。
APIPA_PREFIX = "169.254."

PRIVATE_NETS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"),  # CGNAT / 运营商大内网，校园网与宽带常见
)


def is_private(addr: str) -> bool:
    """是否为 RFC1918 私有地址（含运营商 CGNAT 段）。非法地址返回 False。"""
    try:
        ip = ipaddress.IPv4Address(addr)
    except ipaddress.AddressValueError:
        return False
    return any(ip in net for net in PRIVATE_NETS)


def host_network(addr: str, prefix_len: int) -> ipaddress.IPv4Network | None:
    """按「地址 + 前缀长度」还原主机所在网段。前缀非法时返回 None。"""
    try:
        iface = ipaddress.IPv4Interface(f"{addr}/{prefix_len}")
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
        return None
    return iface.network


class IpConfigCheck:
    check_id = "ip"
    title = "check.ip.title"
    category = "check.ip.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        adapters = ctx.adapters
        primary = ctx.primary
        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        up = [a for a in adapters if a.up]
        if primary is None:
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.CRITICAL,
                summary=t("check.ip.summary_none"),
                summary_key="check.ip.summary_none",
                detail=t("check.ip.detail_none"),
                metrics=[Metric("metric.up_adapters", str(len(up)),
                                t("check.ip.note.up_adapters", n=len(adapters)))],
                advice=[t("check.ip.advice.connect")],
                action_ids=["adapter.renew_dhcp"],
                evidence={"adapters": [a.to_dict() for a in adapters], "primary": None},
            )

        ip = primary.primary_ipv4
        prefix = primary.prefix_len
        metrics.append(Metric("metric.current_adapter", primary.name, primary.description))
        metrics.append(Metric("metric.acquire_mode",
                              t("value.dhcp_auto") if primary.dhcp else t("value.static_manual"),
                              ok=True))

        # ---- 无 IPv4 / APIPA ----
        if not ip:
            severity = Severity.CRITICAL
            problems.append(t("check.ip.problem.no_ipv4", name=primary.name))
            advice.append(t("check.ip.advice.regain"))
            actions.append("adapter.renew_dhcp")
            metrics.append(Metric("metric.ipv4", t("common.none"), ok=False))
        elif ip.startswith(APIPA_PREFIX):
            severity = Severity.CRITICAL
            problems.append(t("check.ip.problem.apipa", ip=ip))
            advice.append(t("check.ip.advice.apipa"))
            actions.append("adapter.renew_dhcp")
            metrics.append(Metric("metric.ipv4", f"{ip}/{prefix}",
                                  t("check.ip.note.apipa"), ok=False))
        else:
            net = host_network(ip, prefix)
            metrics.append(Metric(
                "metric.ipv4", f"{ip}/{prefix}",
                t("check.ip.note.network", net=net) if net else t("check.ip.note.prefix_invalid"),
                ok=net is not None))
            metrics.append(Metric(
                "metric.address_type",
                t("value.private") if is_private(ip) else t("value.public"),
                t("check.ip.note.nat") if is_private(ip) else t("check.ip.note.public_direct"),
                ok=True))
            if net is None:
                severity = Severity.WARN
                problems.append(t("check.ip.problem.invalid_prefix", n=prefix))
                advice.append(t("check.ip.advice.invalid_prefix"))

        # ---- IP 与网关是否同网段 ----
        if ip and not ip.startswith(APIPA_PREFIX) and primary.gateway:
            net = host_network(ip, prefix)
            metrics.append(Metric("metric.gateway", primary.gateway, primary.name,
                                  ok=True))
            if net is not None:
                gw_is_local = _contains(net, primary.gateway)
                metrics.append(Metric("metric.gateway_same_subnet",
                                      t("status.yes") if gw_is_local else t("status.no"),
                                      t("check.ip.note.network", net=net), ok=gw_is_local))
                if not gw_is_local:
                    severity = _worse(severity, Severity.WARN)
                    problems.append(t("check.ip.problem.gw_diff",
                                      gw=primary.gateway, ip=ip, prefix=prefix, net=net))
                    advice.append(t("check.ip.advice.gw_diff"))
        elif not primary.gateway and ip and not ip.startswith(APIPA_PREFIX):
            metrics.append(Metric("metric.gateway", t("common.none"), ok=False))

        # ---- IPv6 只做信息展示 ----
        dns_count = len(primary.dns_v4)
        metrics.append(Metric("metric.ipv4_dns_count", str(dns_count), ok=dns_count > 0))

        detail_lines = [
            t("check.ip.detail.line",
              name=a.name,
              status=a.status,
              ip=a.primary_ipv4 or t("value.no_ip"),
              prefix=a.prefix_len or "-",
              mode=t("value.dhcp") if a.dhcp else t("value.static"),
              gw=a.gateway or t("common.none"))
            for a in _ordered(adapters)[:10]
        ]
        ok_key, ok_args = _ok_summary(primary.dhcp, ip, prefix)
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
            evidence={"adapters": [a.to_dict() for a in adapters],
                      "primary": primary.to_dict(),
                      "private": is_private(ip),
                      "network": str(host_network(ip, prefix)) if ip else ""},
        )


def _ordered(adapters: list) -> list:
    """详情展示顺序：先已连接的，再按接口序号，避免列表被断开的虚拟网卡占满。"""
    return sorted(adapters, key=lambda a: (not a.up, a.is_virtual, a.if_index))


def _contains(net: ipaddress.IPv4Network, addr: str) -> bool:
    try:
        return ipaddress.IPv4Address(addr) in net
    except ipaddress.AddressValueError:
        return False


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


def _ok_summary(dhcp: bool, ip: str, prefix: int) -> tuple[str, dict]:
    """返回 (i18n key, 格式化参数)。

    不直接返回译文：体检在后台线程执行，若此处就翻译，用户切换语言后
    旧结果会停留在旧语言。渲染层用 key + args 现翻，才能跟随语言切换。
    """
    # mode 传 value.* 的 key 而不是译文：渲染时会用当前语言解析，
    # 这样英文界面不会出现中文的「静态」。
    mode_key = "value.dhcp_auto" if dhcp else "value.static"
    return "check.ip.summary_ok", {"ip": ip, "prefix": prefix, "mode": mode_key}


__all__ = ["IpConfigCheck", "is_private", "host_network"]
