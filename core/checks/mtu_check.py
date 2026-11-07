"""检测单元：MTU 与分片。

配置 MTU 与实际路径 MTU 不一致会形成「PMTU 黑洞」：小包（DNS、ping、握手）正常，
一旦传大文件或开 TLS 大包就被静默丢弃，表现为「网页能开一半、下载卡死、SSH 卡住」。

这里用 ping 的 DF（不分片）标志做二分探测，实测路径上能通过的最大 payload，
再加上 28 字节 IP+ICMP 头得到路径 MTU。全部探测有硬预算：单次 ≤1 秒、总共 ≤8 秒、
最多 8 次试探；对方禁 ICMP 或没有外网时直接跳过实测，只报告配置值，
绝不因为「测不出来」就判定网络有问题。
"""
from __future__ import annotations

import time

from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity
from . import _netprobe

# 以太网标准 MTU 1500 → ICMP payload 1472（减去 20 字节 IP 头 + 8 字节 ICMP 头）。
IP_ICMP_OVERHEAD = 28
# PPPoE / 部分 VPN 的实际 MTU 常见 1492 / 1480 / 1420，都在这个探测区间内。
PROBE_MIN_PAYLOAD = 1400
PROBE_MAX_PAYLOAD = 1472
# 确认目标是否回 ICMP 用的小包：远小于任何链路 MTU，只要目标可达必能通过。
REACH_PAYLOAD = 64
MAX_PROBES = 8
TOTAL_BUDGET = 8.0
# 实测值比配置值小 20 字节以上才算「有黑洞风险」；更小的差异落在 MSS 协商能兜住的范围内。
# 注意 ICMP 有约 1% 的随机丢包，探测本身会保留重试来避免把抖动误判成 MTU 上限。
PMTU_GAP_THRESHOLD = 20

# 探测目标：先国内（通常可达），再国际（用来暴露真实 PMTU 差异）。
PROBE_TARGETS = ("223.5.5.5", "8.8.8.8")


class MtuCheck:
    check_id = "mtu"
    title = "check.mtu.title"
    category = "check.mtu.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        primary = ctx.primary
        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        configured = primary.mtu if primary and primary.mtu else 0
        mtu_source = (t("value.mtu_source_adapter", name=primary.name) if configured
                      else t("value.not_from_adapter"))
        if not configured:
            configured, mtu_source = _mtu_from_netsh(ctx, primary.name if primary else "")

        metrics.append(Metric("metric.configured_mtu",
                              str(configured) if configured else t("common.unknown"),
                              mtu_source, ok=bool(configured) if configured else None))

        # ---- 实测 ----
        measured, target, attempts, skip_reason = _probe_path_mtu()
        metrics.append(Metric("metric.measured_mtu",
                              str(measured) if measured else t("status.not_measured"),
                              t("check.mtu.note.probe_target", target=target or t("common.none")),
                              ok=bool(measured)))
        metrics.append(Metric("metric.probe_target", target or t("common.none"),
                              t("check.mtu.note.target_unused")))
        metrics.append(Metric("metric.probe_attempts", str(attempts),
                              t("check.mtu.note.attempts", n=MAX_PROBES,
                                sec=f"{TOTAL_BUDGET:.0f}")))
        if measured is None:
            # 测不出来 = 没有证据，绝不能推断「MTU 有问题」。
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.INFO,
                summary=t("check.mtu.summary_not_measured", reason=skip_reason,
                          value=configured or t("common.unknown")),
                detail=t("check.mtu.detail_not_measured", reason=skip_reason,
                         value=configured or t("common.unknown")),
                metrics=metrics,
                advice=[t("check.mtu.advice.probe")],
                action_ids=[],
                evidence={"configured_mtu": configured, "measured_mtu": None,
                          "attempts": attempts, "target": target,
                          "skip_reason": skip_reason},
            )

        if configured:
            gap = configured - measured
            metrics.append(Metric(
                "metric.mtu_gap", t("value.bytes_signed", n=gap),
                t("check.mtu.note.gap", n=PMTU_GAP_THRESHOLD),
                ok=abs(gap) < PMTU_GAP_THRESHOLD))
            if gap >= PMTU_GAP_THRESHOLD:
                severity = Severity.WARN
                problems.append(t("check.mtu.problem.cfg_gt_pmtu",
                                  cfg=configured, pmtu=measured, gap=gap))
                advice.append(t("check.mtu.advice.optimize"))
                actions.append("mtu.optimize")
            elif gap <= -PMTU_GAP_THRESHOLD:
                severity = Severity.INFO
                problems.append(t("check.mtu.problem.cfg_lt_pmtu",
                                  cfg=configured, pmtu=measured))
                advice.append(t("check.mtu.advice.raise"))
        else:
            severity = Severity.INFO
            problems.append(t("check.mtu.problem.no_cfg", pmtu=measured))

        # 结论文案：有问题时拼接，正常时用带实测值的模板。
        if problems:
            summary = t("sep.summary").join(problems)
            summary_key = ""
            mtu_args = {}
        else:
            mtu_args = {
                "cfg": configured,
                "pmtu": measured,
                "gap": measured - configured,
                "tol": PMTU_GAP_THRESHOLD,
            }
            summary = t("check.mtu.summary_ok", **mtu_args)
            summary_key = "check.mtu.summary_ok"

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            # 记录 key 供渲染层在切换语言后重新翻译；
            # 有 problems 时文案是拼接的，无法用单一 key，保持已翻译文本。
            summary=summary,
            summary_key=summary_key,
            summary_args=mtu_args,
            detail=t("check.mtu.detail.ok", target=target, n=attempts,
                     payload=measured - IP_ICMP_OVERHEAD,
                     overhead=IP_ICMP_OVERHEAD, mtu=measured),
            metrics=metrics,
            advice=advice,
            action_ids=_unique(actions),
            evidence={"configured_mtu": configured, "measured_mtu": measured,
                      "target": target, "attempts": attempts,
                      "payload": measured - IP_ICMP_OVERHEAD},
        )


def _probe_path_mtu() -> tuple[int | None, str, int, str]:
    """用 DF ping 二分探测路径 MTU。

    返回 (实测 MTU 或 None, 目标地址, 探测次数, 跳过原因)。
    预算控制：单次超时 1 秒、总时长 8 秒、最多 8 次探测。

    流程：先用一个小包（REACH_PAYLOAD）确认目标回 ICMP 并确定探测目标，再在
    [1400, 1473) 上二分。小包探测同时承担「目标不可达」的判定，不额外浪费次数。
    """
    started = time.perf_counter()
    attempts = 0
    target = ""
    last_error = ""

    for candidate in PROBE_TARGETS:
        if time.perf_counter() - started > TOTAL_BUDGET:
            last_error = t("check.mtu.skip.budget")
            break
        attempts += 1
        if _df_probe(candidate, REACH_PAYLOAD, deadline=started + TOTAL_BUDGET).received > 0:
            target = candidate
            break
        last_error = t("check.mtu.skip.no_icmp", ip=candidate)

    if not target:
        return None, "", attempts, last_error or t("check.mtu.skip.no_target")

    # ---- 二分：上界取 1473，使标准以太网的 1472 也落在收敛区间内 ----
    low, high = PROBE_MIN_PAYLOAD - 1, PROBE_MAX_PAYLOAD + 1
    best: int | None = None
    deadline = started + TOTAL_BUDGET

    while high - low > 1 and attempts < MAX_PROBES and time.perf_counter() < deadline:
        mid = (low + high) // 2
        attempts += 1
        if _df_probe(target, mid, deadline=deadline).received > 0:
            best = mid
            low = mid
        else:
            high = mid

    if best is None:
        return None, target, attempts, t("check.mtu.skip.too_small", n=PROBE_MIN_PAYLOAD)
    return best + IP_ICMP_OVERHEAD, target, attempts, ""


def _df_probe(target: str, payload: int,
              *, deadline: float | None = None) -> _netprobe.PingStats:
    """带 DF 标志的单次 ping。

    「需要分片」是明确的否定结论，直接返回；而单包丢失既可能是包太大，也可能是链路抖动。
    对这种没有任何回复的情况重试一次，避免把随机丢包误判成路径 MTU 上限——
    误判会把结论压低 20~40 字节，直接影响「是否建议修改 MTU」这个动作。
    重试要占用额外时间，因此仅在时间预算还够时进行。
    """
    stats = _netprobe.ping(target, count=1, wait_ms=900, payload=payload, df=True, timeout=2.0)
    if stats.received == 0 and not stats.frag_blocked:
        if deadline is not None and deadline - time.perf_counter() < 2.4:
            return stats
        retry = _netprobe.ping(target, count=1, wait_ms=900, payload=payload,
                               df=True, timeout=2.0)
        if retry.received > 0 or retry.frag_blocked:
            return retry
    return stats


def _mtu_from_netsh(ctx: DiagnosticContext, iface: str) -> tuple[int, str]:
    """网卡 MTU 读取失败的兜底：解析 `netsh interface ipv4 show subinterfaces`。"""
    rc, out = ctx.cmd(("netsh", "interface", "ipv4", "show", "subinterfaces"), timeout=15)
    if rc != 0 or not out:
        return 0, t("value.not_read")
    for line in out.splitlines():
        if iface and iface in line:
            for token in line.split():
                if token.isdigit() and 500 <= int(token) <= 9000:
                    return int(token), t("value.netsh_subifaces")
    return 0, t("value.not_read")


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


__all__ = ["MtuCheck", "PROBE_TARGETS"]
