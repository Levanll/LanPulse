"""检测单元：外网连通性与延迟。

前面几项分别验证了「地址 / 网关 / DNS / 代理」各自的配置，本项回答最后一个问题：
**现在到底能不能上网，有多快。**

三个层次由内到外，任何一层失败都能定位问题边界：
  1. IPv4 直连公网地址（ping 223.5.5.5）—— 绕过 DNS，验证 IP 层出口是否通；
  2. TCP 443 握手（www.baidu.com:443 / www.qq.com:443）—— 验证真实应用流量路径，
     顺带验证 DNS；只握手不发送任何应用层数据；
  3. getaddrinfo 解析 —— 验证域名解析本身是否可用。

所有探测都有超时，整项预算 ≤10 秒；不下载内容、不上传任何数据。
"""
from __future__ import annotations

import time

from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity
from . import _netprobe

# 公网直连目标：阿里 DNS 的 223.5.5.5 全国可 ping，是常用的「IP 层是否通」探针。
PING_TARGET = "223.5.5.5"
PING_COUNT = 2
PING_WAIT_MS = 1200

# TCP 目标：两个不同 CDN 阵营的大站，避免单站点故障导致整体误判。
TCP_TARGETS = (("www.baidu.com", 443), ("www.qq.com", 443))
TCP_TIMEOUT = 3.0

DNS_PROBE_NAME = "www.baidu.com"
DNS_PROBE_TIMEOUT = 2.0

# RTT 分级（ICMP 平均 RTT）：国内直连公共 DNS 通常 <50ms。
RTT_EXCELLENT = 50.0
RTT_NORMAL = 120.0
RTT_SLOW = 300.0

# TCP 握手分级：同城/邻近机房一般 <80ms，跨境 150ms 以上很常见。
HANDSHAKE_GOOD = 200.0
HANDSHAKE_SLOW = 800.0

TOTAL_BUDGET = 10.0


class ConnectivityCheck:
    check_id = "connectivity"
    title = "check.connectivity.title"
    category = "check.connectivity.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        # 探测目标与阈值全部来自区域剖面：中国用 223.5.5.5 / 百度，
        # 欧美用 1.1.1.1 / Google。硬编码任一地区的目标都会在跨地域时误判。
        #
        # **必须先取 profile，再开计时器。** 首次取 profile 会触发区域自动识别，
        # 它会 TCP 握手测 cn / global / apac 三组锚点；在 8.8.8.8 / 9.9.9.9 不可达
        # 的网络上（国内很常见）实测耗时 12s 以上，远超本项 10s 的 TOTAL_BUDGET。
        # 若把这段共享的准备时间算进来，预算会在第一个 TCP 探测之前就被判超时，
        # 于是每次冷启动首次体检都输出"结论不完整"的 SKIP——而网络其实是好的。
        # 区域识别是一次性的全局准备，不属于本检测项的探测开销。
        profile = ctx.profile
        ping_target = profile.ping_targets[0][0]
        tcp_targets = profile.tcp_targets
        dns_probe_name = profile.resolve_domains[0]

        started = time.perf_counter()
        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        severity = Severity.OK

        # ---- 1. IP 层 ----
        ping_stats = _netprobe.ping(ping_target, count=PING_COUNT,
                                    wait_ms=PING_WAIT_MS, timeout=6)
        metrics.append(Metric(
            t("metric.ping_target", target=ping_target),
            t("value.ms", n=f"{ping_stats.rtt_avg_ms:.0f}")
            if ping_stats.ok and ping_stats.rtt_avg_ms is not None
            else t("status.unreachable"),
            t("check.connectivity.note.ping", loss=ping_stats.loss_pct,
              grade=_ping_grade(ping_stats, profile)),
            ok=ping_stats.ok))
        if ping_stats.ok:
            metrics.append(Metric("metric.loss_rate", f"{ping_stats.loss_pct}%",
                                  ok=ping_stats.loss_pct == 0))
            if ping_stats.loss_pct >= 50:
                severity = _worse(severity, Severity.WARN)
                problems.append(t("check.connectivity.problem.ping_loss",
                                  loss=ping_stats.loss_pct))
                advice.append(t("check.connectivity.advice.wifi"))

        # ---- 2. TCP 443 ----
        tcp_results: list[_netprobe.TcpProbe] = []
        for host, port in tcp_targets:
            if time.perf_counter() - started > TOTAL_BUDGET:
                break
            probe = _netprobe.tcp_connect(host, port, timeout=TCP_TIMEOUT)
            tcp_results.append(probe)
            metrics.append(Metric(
                t("metric.tcp_target", host=host, port=port),
                t("status.success") if probe.ok else t("status.failed"),
                t("check.connectivity.handshake_ms", ms=f"{probe.connect_ms:.0f}")
                if probe.ok else probe.error[:80],
                ok=probe.ok))

        ok_tcp = [p for p in tcp_results if p.ok]
        failed_tcp = [p for p in tcp_results if not p.ok]

        # ---- 3. DNS 解析 ----
        dns_probe = _netprobe.resolve_timed(dns_probe_name, timeout=DNS_PROBE_TIMEOUT)
        metrics.append(Metric(
            "metric.dns_resolve",
            t("status.available") if dns_probe.ok else t("status.failed"),
            t("check.connectivity.note.dns", name=dns_probe_name, ms=f"{dns_probe.ms:.0f}")
            if dns_probe.ok and dns_probe.ms is not None
            else dns_probe.error[:80],
            ok=dns_probe.ok))

        # ---- 判定 ----
        if not tcp_results:
            # 时间预算在 TCP 阶段就被耗尽（例如 IP 层探测占满），没有应用层样本。
            severity = Severity.SKIP
            problems.append(t("check.connectivity.problem.budget"))
        elif not ok_tcp:
            severity = Severity.CRITICAL
            problems.append(t("check.connectivity.problem.tcp_all_fail", n=len(tcp_results)))
            if ping_stats.ok:
                advice.append(t("check.connectivity.advice.proxy_firewall"))
            else:
                advice.append(t("check.connectivity.advice.wan"))
        elif failed_tcp:
            severity = _worse(severity, Severity.WARN)
            names = t("sep.list").join(f"{p.host}:{p.port}" for p in failed_tcp)
            problems.append(t("check.connectivity.problem.tcp_partial", names=names))
        elif ok_tcp:
            # 只取「最慢」会放大单次抖动：某个 CDN 边缘节点偶发慢握手很常见。
            # 因此慢的判定要求**所有**成功目标都慢，单点慢只给 INFO。
            slowest = max((p.connect_ms or 0) for p in ok_tcp)
            fastest = min((p.connect_ms or 0) for p in ok_tcp)
            hs_slow = max(400.0, profile.rtt_slow_ms * 2.5)
            all_slow = all((p.connect_ms or 0) > hs_slow for p in ok_tcp)
            hs_good = max(120.0, profile.rtt_normal_ms * 1.6)
            all_fair = all((p.connect_ms or 0) > hs_good for p in ok_tcp)
            avg_ping = ping_stats.rtt_avg_ms
            if avg_ping is not None:
                if avg_ping > profile.rtt_slow_ms:
                    severity = _worse(severity, Severity.WARN)
                    problems.append(t("check.connectivity.problem.latency_high",
                                      ms=f"{avg_ping:.0f}"))
                elif avg_ping > profile.rtt_normal_ms:
                    severity = _worse(severity, Severity.INFO)
                    problems.append(t("check.connectivity.problem.latency_mid",
                                      ms=f"{avg_ping:.0f}"))
            if all_slow:
                severity = _worse(severity, Severity.WARN)
                problems.append(t("check.connectivity.problem.handshake_slow",
                                  fast=f"{fastest:.0f}", slow=f"{slowest:.0f}"))
            elif all_fair and severity.rank < Severity.INFO.rank:
                severity = Severity.INFO
                problems.append(t("check.connectivity.problem.handshake_fair",
                                  fast=f"{fastest:.0f}", slow=f"{slowest:.0f}"))

        if not dns_probe.ok:
            severity = _worse(severity, Severity.WARN)
            problems.append(t("check.connectivity.problem.dns_fail"))
            advice.append(t("check.connectivity.advice.dns"))

        if severity is Severity.OK:
            summary_key = "check.connectivity.summary_ok"
            # ping / handshake 是已翻译的动态描述（含 ms 数值），
            # 保持为文本而非 key——数值部分无法用模板表达。
            summary_args = {
                "ping": _ping_text(ping_stats, profile),
                "handshake": _handshake_text(ok_tcp),
            }
            summary = t("check.connectivity.summary_ok", **summary_args)
        else:
            summary_key = ""
            summary_args = {}
            summary = t("sep.summary").join(problems)

        detail_lines = [t("check.connectivity.detail.ping", target=ping_target,
                          text=_fmt_ping(ping_stats))]
        for p in tcp_results:
            if p.ok:
                detail_lines.append(t("check.connectivity.detail.tcp_ok",
                                      host=p.host, port=p.port,
                                      ms=f"{p.connect_ms:.0f}"))
            else:
                detail_lines.append(t("check.connectivity.detail.tcp_fail",
                                      host=p.host, port=p.port, err=p.error[:60]))
        if dns_probe.ok:
            detail_lines.append(t(
                "check.connectivity.detail.dns_ok",
                name=dns_probe_name, ms=f"{dns_probe.ms:.0f}",
                addrs=t("sep.list").join(dns_probe.addresses[:3])
                or t("check.connectivity.no_a_record")))
        else:
            detail_lines.append(t("check.connectivity.detail.dns_fail",
                                  name=dns_probe_name, err=dns_probe.error[:60]))
        detail_lines.append(t("check.connectivity.detail.elapsed",
                              sec=f"{time.perf_counter() - started:.1f}",
                              budget=f"{TOTAL_BUDGET:.0f}"))

        action_ids: list[str] = []
        if not dns_probe.ok:
            action_ids.append("dns.flush_cache")

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            # 记录 key 供渲染层在切换语言后重新翻译；
            # 有 problems 时文案是拼接的，无法用单一 key，保持已翻译文本。
            summary=summary,
            summary_key=(summary_key if not problems else ""),
            summary_args=(summary_args if not problems else {}),
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=action_ids,
            evidence={
                "ping": ping_stats.to_dict(),
                "tcp": [p.to_dict() for p in tcp_results],
                "dns": dns_probe.to_dict(),
                "region": ctx.region_key,
                               "ping_target": ping_target,
                               "thresholds": {
                                   "rtt_excellent": profile.rtt_excellent_ms,
                                   "rtt_normal": profile.rtt_normal_ms,
                                   "rtt_slow": profile.rtt_slow_ms,
                               "total_budget": TOTAL_BUDGET},
                "elapsed_s": round(time.perf_counter() - started, 2),
            },
        )


def _ping_text(stats: _netprobe.PingStats, profile=None) -> str:
    """摘要用的简短 ping 描述，避免在 f-string 里做条件格式化。

    目标不回 ICMP 是常见策略，此时应用层（HTTPS）仍然可以正常，
    摘要要讲清这一点，不能写成「ping 不通」让人误以为外网断。
    profile 用于按区域阈值分级：跨境 200ms 属正常，国内 200ms 就偏慢。
    """
    if not stats.ok or stats.rtt_avg_ms is None:
        return t("check.connectivity.ping_no_icmp")
    return t("check.connectivity.ping_text", ms=f"{stats.rtt_avg_ms:.0f}",
             grade=_ping_grade(stats, profile))


def _handshake_text(results: list[_netprobe.TcpProbe]) -> str:
    times = [p.connect_ms for p in results if p.ok and p.connect_ms is not None]
    return (t("check.connectivity.handshake_text", ms=f"{max(times):.0f}") if times
            else t("check.connectivity.handshake_none"))


def _ping_grade(stats: _netprobe.PingStats, profile=None) -> str:
    """按区域阈值分级。

    阈值必须来自区域剖面：跨境 200ms 属正常，国内 200ms 就偏慢。
    用同一把尺子量全球会把正常的跨国链路报成「高延迟」。
    """
    if not stats.ok:
        return t("grade.icmp_blocked")
    ms = stats.rtt_avg_ms or 0
    excellent = profile.rtt_excellent_ms if profile else RTT_EXCELLENT
    normal = profile.rtt_normal_ms if profile else RTT_NORMAL
    slow = profile.rtt_slow_ms if profile else RTT_SLOW
    if ms < excellent:
        return t("grade.excellent")
    if ms < normal:
        return t("grade.normal")
    if ms < slow:
        return t("grade.slow")
    return t("grade.high_latency")


def _fmt_ping(stats: _netprobe.PingStats) -> str:
    if not stats.ok:
        return t("check.connectivity.ping_detail_fail", loss=stats.loss_pct)
    return t("check.connectivity.ping_detail",
             avg=f"{stats.rtt_avg_ms:.0f}",
             min=f"{stats.rtt_min_ms:.0f}",
             max=f"{stats.rtt_max_ms:.0f}",
             loss=stats.loss_pct)


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


__all__ = ["ConnectivityCheck"]
