"""检测单元：TCP/IP 协议栈参数。

「重装系统前网速正常，现在下载只有几百 KB/s」这类问题，很多是被人按网上的
『优化教程』改过 netsh 参数：把接收窗口自动调节关掉（autotuning=disabled / restricted），
在高延迟链路上吞吐会直接掉一个数量级。

这里读两个地方：
  * `netsh int tcp show global` —— 全局参数（autotuning / ECN / RSS / 时间戳）；
  * `netsh int tcp show heuristics` —— 窗口缩放启发式（disabled 才是推荐值）；
  * `netsh int ip show global` —— 判断协议栈本身是否还能正常汇报状态。

命令输出随系统语言变化（中文「接收窗口自动调节级别」/ 英文「Receive Window
Auto-Tuning Level」），因此统一按「冒号 + 值」解析，键名做中英文关键字匹配。
"""
from __future__ import annotations

import re

from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity

# autotuning 只有 normal / experimental 是健康值；其余都会限制窗口增长。
AUTOTUNING_GOOD = {"normal", "experimental"}
AUTOTUNING_BAD = {"disabled", "restricted", "highlyrestricted"}

_KV_RE = re.compile(r"^\s*([^:：]+?)\s*[:：]\s*(.+?)\s*$")

# 键名匹配规则：值取自 (英文键, 中文键片段)。中文 Windows 的实际用词是
# 「接收方缩放状态」「接收窗口自动调节级别」「窗口缩放启发」，与英文直译并不一致，
# 这里按实际输出校准，避免中文环境下取不到值。
_KEY_AUTOTUNING = ("receive window auto-tuning level", "接收窗口自动调节")
_KEY_ECN = ("ecn capability", "ecn")
_KEY_RSS = ("receive-side scaling", "接收方缩放", "接收端缩放")
_KEY_TIMESTAMPS = ("rfc 1323 timestamps", "时间戳")
_KEY_SCALING = ("window scaling heuristics", "窗口缩放")


class TcpParamCheck:
    check_id = "tcp"
    title = "check.tcp.title"
    category = "check.tcp.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        rc_global, out_global = ctx.cmd(("netsh", "int", "tcp", "show", "global"), timeout=20)
        rc_ip, out_ip = ctx.cmd(("netsh", "int", "ip", "show", "global"), timeout=20)
        rc_heur, out_heur = ctx.cmd(("netsh", "int", "tcp", "show", "heuristics"), timeout=20)

        params = parse_tcp_global(out_global)
        heur = parse_tcp_global(out_heur)

        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        # ---- 协议栈是否可用（最先判断，读不到就别谈参数优化）----
        stack_broken = rc_ip != 0 or not out_ip.strip() or not params
        if stack_broken:
            reason = (t("check.tcp.reason.cmd_rc", rc=rc_ip) if rc_ip != 0
                      else t("check.tcp.reason.parse_fail"))
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.CRITICAL,
                summary=t("check.tcp.summary_broken"),
                detail=t("check.tcp.detail_broken", reason=reason),
                metrics=[Metric("metric.tcp_global_rc", str(rc_global)),
                         Metric("metric.ip_global_rc", str(rc_ip))],
                advice=[t("check.tcp.advice.reset")],
                action_ids=["tcp.reset_stack"],
                evidence={"tcp_global_rc": rc_global, "ip_global_rc": rc_ip,
                          "tcp_global": out_global[:2000], "ip_global": out_ip[:2000]},
            )

        autotuning = _pick(params, _KEY_AUTOTUNING)
        ecn = _pick(params, _KEY_ECN)
        rss = _pick(params, _KEY_RSS)
        timestamps = _pick(params, _KEY_TIMESTAMPS)
        scaling = _pick(heur, _KEY_SCALING)

        norm_auto = (autotuning or "").strip().lower()
        if autotuning is None:
            auto_ok: bool | None = None
            auto_note = t("check.tcp.note.autotuning_unknown")
        else:
            auto_ok = norm_auto in AUTOTUNING_GOOD
            auto_note = (t("check.tcp.note.autotuning_ok") if auto_ok
                         else t("check.tcp.note.autotuning_bad"))
        metrics.append(Metric("metric.autotuning", autotuning or t("common.unknown"),
                              auto_note, ok=auto_ok))
        metrics.append(Metric("metric.ecn", ecn or t("common.unknown"),
                              t("check.tcp.note.ecn"), ok=None))
        metrics.append(Metric("metric.rss", rss or t("common.unknown"),
                              t("check.tcp.note.rss") if rss else t("value.not_read"),
                              ok=None if not rss else rss.strip().lower() == "enabled"))
        metrics.append(Metric("metric.timestamps", timestamps or t("common.unknown"),
                              t("check.tcp.note.timestamps"), ok=None))
        if scaling is not None:
            metrics.append(Metric("metric.scaling_heuristics", scaling,
                                  t("check.tcp.note.scaling"),
                                  ok=scaling.strip().lower() == "disabled"))
        metrics.append(Metric("metric.param_count", str(len(params)),
                              t("check.tcp.note.param_count")))

        # ---- autotuning 被关 ----
        if norm_auto in AUTOTUNING_BAD:
            severity = _worse(severity, Severity.WARN)
            problems.append(t("check.tcp.problem.autotuning_bad", value=autotuning))
            advice.append(t("check.tcp.advice.autotuning"))
            actions.append("tcp.autotuning")
        elif autotuning is None:
            severity = _worse(severity, Severity.INFO)
            problems.append(t("check.tcp.problem.autotuning_unknown"))

        # ---- heuristics：仅作信息展示，不产出修复建议 ----
        #
        # Windows 10 1803 之后，窗口缩放启发式已被系统废弃。本机执行
        # `netsh int tcp set heuristics ?` 明确返回：
        #   "Window scaling heuristics are not supported in this version of Windows.
        #    Changing window scaling heuristics settings will have no effect."
        # 因此无论 show 出来是 enabled 还是 disabled，改它都不会有任何效果。
        # 检测侧若仍建议执行 tcp.heuristics，用户点了只会得到"已跳过"，
        # 属于给用户制造困惑的死建议，故此处只记录数值、不挂 action。
        if scaling is not None:
            value_l = scaling.strip().lower()
            metrics[-1].ok = value_l in ("disabled", "enabled")
            if value_l == "enabled":
                advice.append(t("check.tcp.advice.heuristics"))

        # ---- RSS 关闭（仅提示，笔记本省电场景常见）----
        if rss and rss.strip().lower() != "enabled":
            severity = _worse(severity, Severity.INFO)
            advice.append(t("check.tcp.advice.rss"))

        detail_lines = [t("check.tcp.detail.kv", key=key, value=value)
                        for key, value in params.items()]
        if heur:
            detail_lines.append(t("check.tcp.detail.heuristics"))
            detail_lines += [t("check.tcp.detail.kv", key=key, value=value)
                             for key, value in heur.items()]

        ok_key, ok_args = _ok_summary(autotuning, scaling)
        summary_text = t(ok_key, **ok_args)
        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            # 记录 key 供渲染层在切换语言后重新翻译；
            # 有 problems 时文案是拼接的，无法用单一 key，保持已翻译文本。
            summary=summary_text,
            summary_key="" if problems else ok_key,
            summary_args={} if problems else ok_args,
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=_unique(actions),
            evidence={
                "tcp_global": params,
                "heuristics": heur,
                "tcp_global_rc": rc_global,
                "ip_global_rc": rc_ip,
                "heuristics_rc": rc_heur,
                "raw_tcp_global": out_global[:3000],
                "raw_heuristics": out_heur[:1500],
            },
        )


def parse_tcp_global(text: str) -> dict[str, str]:
    """把 `Key : Value` 形式的 netsh 输出解析成有序字典。表头与说明行自动跳过。"""
    out: dict[str, str] = {}
    for line in text.splitlines():
        m = _KV_RE.match(line)
        if not m:
            continue
        key, value = m.group(1).strip(), m.group(2).strip()
        if not key or not value or len(key) > 60:
            continue
        out[key] = value
    return out


def _pick(params: dict[str, str], keys: tuple[str, ...]) -> str | None:
    """按候选中英文键名取第一个命中的值。"""
    for name, value in params.items():
        low = name.lower()
        for key in keys:
            if key in low:
                return value
    return None


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


def _ok_summary(autotuning: str | None, scaling: str | None) -> tuple[str, dict]:
    auto = autotuning or t("value.not_read")
    if scaling:
        return "check.tcp.summary_ok_scaling", {"auto": auto, "scaling": scaling}
    return "check.tcp.summary_ok", {"auto": auto}


__all__ = ["TcpParamCheck", "parse_tcp_global"]
