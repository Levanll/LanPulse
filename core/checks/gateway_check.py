"""检测单元：默认网关与路由表。

「能上内网、上不了外网」最常见的原因就是默认路由缺失，或被 VPN / 虚拟网卡抢走。
这里只读地解析 `route print -4`，再用 ping 量一次网关 RTT。

关于 ping 网关失败：大量家用路由器与安全网关默认禁 ICMP，ping 不通不代表链路坏。
因此网关 ping 失败只给 INFO，绝不给 WARN——把「路由器不回 ping」误报成故障，
是这类工具最容易被骂的地方。
"""
from __future__ import annotations

import re

from .. import platform_win as pw
from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity
from . import _netprobe

# 网关 RTT 分级：有线内网通常 <2ms，Wi-Fi 5~20ms，>100ms 说明无线链路或网关有异常。
GW_RTT_GOOD_MS = 10.0
GW_RTT_SLOW_MS = 100.0
# 单条默认路由的 metric 越大越不优先；>100 说明存在更优先的其它出口。
ROUTE_METRIC_HIGH = 100

_DEFAULT_DEST = "0.0.0.0"
_ROW_RE = re.compile(
    r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+(\d{1,3}(?:\.\d{1,3}){3})\s+(\S+)\s+(\S+)\s+(\d+)\s*$")


class GatewayCheck:
    check_id = "gateway"
    title = "check.gateway.title"
    category = "check.gateway.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        primary = ctx.primary
        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        severity = Severity.OK

        rc, out = ctx.cmd(("route", "print", "-4"), timeout=15)
        routes = parse_default_routes(out)
        metrics.append(Metric(
            "metric.route_count", str(len(routes)),
            t("check.gateway.note.route_count") if rc == 0
            else t("check.gateway.note.route_count_fail"),
            ok=bool(routes) and rc == 0))

        if primary is not None:
            metrics.append(Metric("metric.adapter_gateway",
                                  primary.gateway or t("common.none"),
                                  primary.name, ok=bool(primary.gateway)))

        if rc != 0:
            severity = Severity.SKIP
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=severity,
                summary=t("check.gateway.summary_skip"),
                summary_key="check.gateway.summary_skip",
                detail=t("check.gateway.detail_skip", rc=rc, out=out[:300]),
                metrics=metrics,
                evidence={"route_print_rc": rc, "route_print": out[:2000]},
            )

        # ---- 默认路由缺失 ----
        if not routes and not (primary and primary.gateway):
            severity = Severity.CRITICAL
            problems.append(t("check.gateway.problem.no_route"))
            advice.append(t("check.gateway.advice.no_route"))
            evidence_gw = ""
        else:
            best = min(routes, key=lambda r: r["metric"]) if routes else None
            gateway = (best or {}).get("gateway") or (primary.gateway if primary else "")
            evidence_gw = gateway
            if best is not None:
                metrics.append(Metric(
                    "metric.active_gateway", best["gateway"],
                    t("check.gateway.note.route", metric=best["metric"],
                      interface=best["interface"]),
                    ok=True))
                if best["metric"] >= ROUTE_METRIC_HIGH:
                    severity = Severity.INFO
                    metrics[-1].ok = False
                    advice.append(t("check.gateway.advice.high_metric"))

            # ---- 多条默认路由 ----
            if len(routes) > 1:
                severity = _worse(severity, Severity.WARN)
                problems.append(t("check.gateway.problem.multi_route", n=len(routes)))
                advice.append(t("check.gateway.advice.multi_route"))
                metrics.append(Metric(
                    "metric.multi_gateway", t("status.yes"),
                    t("sep.list").join(
                        t("check.gateway.note.multi", gw=r["gateway"], metric=r["metric"])
                        for r in routes[:4]),
                    ok=False))

            # ---- 网关 RTT ----
            if gateway and pw.is_valid_ipv4(gateway):
                stats = _netprobe.ping(gateway, count=2, wait_ms=1000, timeout=6)
                rtt = stats.rtt_avg_ms
                latency = Metric(
                    "metric.gateway_latency",
                    t("value.ms", n=f"{rtt:.0f}") if (stats.ok and rtt is not None)
                    else t("status.no_response"),
                    t("check.gateway.note.loss", loss=stats.loss_pct),
                    ok=None if not stats.ok else rtt < GW_RTT_SLOW_MS)
                metrics.append(latency)
                metrics.append(Metric("metric.gateway_loss", f"{stats.loss_pct}%",
                                      ok=stats.loss_pct == 0))
                if stats.ok and rtt is not None and rtt > GW_RTT_SLOW_MS:
                    severity = _worse(severity, Severity.WARN)
                    problems.append(t("check.gateway.problem.gw_slow", ms=f"{rtt:.0f}"))
                    advice.append(t("check.gateway.advice.gw_slow"))
                elif stats.ok and rtt is not None and rtt > GW_RTT_GOOD_MS:
                    severity = _worse(severity, Severity.INFO)
                    problems.append(t("check.gateway.problem.gw_mid", ms=f"{rtt:.0f}"))
                elif not stats.ok:
                    # 网关禁 ICMP 很常见（大量家用路由器默认丢弃 echo），ping 不通不构成故障证据：
                    # 只给 INFO 并在说明里讲清「这不代表链路坏」，绝不升级为 WARN。
                    severity = _worse(severity, Severity.INFO)
                    problems.append(t("check.gateway.problem.gw_icmp", gw=gateway))
                    latency.note = t("check.gateway.note.icmp")

        detail_lines = [
            t("check.gateway.detail.route", gw=r["gateway"],
              interface=r["interface"], metric=r["metric"])
            for r in routes
        ] or [t("check.gateway.detail.no_route")]
        ok_key, ok_args = _ok_summary(evidence_gw, len(routes))
        summary_text = (t("sep.summary").join(problems) if problems
                        else t(ok_key, **ok_args))
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
            action_ids=[],
            evidence={
                "default_routes": routes,
                "gateway": evidence_gw,
                "route_print_rc": rc,
                "route_print": out[:4000],
            },
        )


def parse_default_routes(text: str) -> list[dict]:
    """从 route print -4 输出里抽取默认路由（0.0.0.0/0.0.0.0）。

    输出可能是中文表头（网络目标/网络掩码/网关/接口/跃点数），但数据行格式固定，
    因此按列解析而不依赖表头文字。
    """
    routes: list[dict] = []
    for line in text.splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        dest, mask, gateway, interface, metric = m.groups()
        if dest != _DEFAULT_DEST or mask != "0.0.0.0":
            continue
        if gateway.lower() in ("on-link", "在链路上"):
            continue
        if not pw.is_valid_ipv4(gateway):
            continue
        routes.append({
            "gateway": gateway,
            "interface": interface,
            "metric": int(metric),
        })
    routes.sort(key=lambda r: r["metric"])
    return routes


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


def _ok_summary(gateway: str, count: int) -> tuple[str, dict]:
    if not gateway:
        return "check.gateway.summary_ok_nogw", {}
    if count > 1:
        return "check.gateway.summary_ok_extra", {"gw": gateway, "n": count - 1}
    return "check.gateway.summary_ok", {"gw": gateway}


__all__ = ["GatewayCheck", "parse_default_routes"]
