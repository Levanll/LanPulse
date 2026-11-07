"""检测单元：网络适配器状态。

判断“本机是否有一块真正在承载上网流量的网卡”，并暴露链路速率、
虚拟网卡占比等事实。所有结论必须能由 evidence 里的原始数据复现。

i18n 约定：`title` / `category` / `Metric.name` 存 key（UI 与报告渲染时翻译），
含动态数据的 summary / detail / note 在检测时用 t(key, **fmt) 渲染。
"""
from __future__ import annotations

from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity


class AdapterCheck:
    check_id = "adapter"
    title = "check.adapter.title"
    category = "check.adapter.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        adapters = ctx.adapters
        metrics: list[Metric] = []
        if not adapters:
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.CRITICAL,
                summary=t("check.adapter.summary_none"),
                summary_key="check.adapter.summary_none",
                detail=t("check.adapter.detail_none"),
                advice=[t("check.adapter.advice.device_manager")],
                evidence={"adapters": []},
            )

        up = [a for a in adapters if a.up]
        physical_up = [a for a in up if not a.is_virtual]
        primary = ctx.primary

        severity = Severity.OK
        problems: list[str] = []
        advice: list[str] = []

        if not up:
            severity = Severity.CRITICAL
            problems.append(t("check.adapter.problem.all_down"))
            advice.append(t("check.adapter.advice.check_cable"))
        elif not physical_up:
            severity = Severity.WARN
            problems.append(t("check.adapter.problem.virtual_only"))
            advice.append(t("check.adapter.advice.physical_disabled"))
        elif primary is None:
            severity = Severity.WARN
            problems.append(t("check.adapter.problem.no_ipv4"))

        # 链路速率过低提示（仅提示，不是错误：百兆网络本身正常）
        if primary and primary.link_speed:
            metrics.append(Metric("metric.link_speed", primary.link_speed, primary.name,
                                  ok=_speed_ok(primary.link_speed)))

        metrics.append(Metric(
            "metric.adapter_count", str(len(adapters)),
            t("check.adapter.note.adapter_count", up=len(up),
              virtual=sum(1 for a in adapters if a.is_virtual))))
        if primary:
            metrics.append(Metric("metric.primary_adapter", primary.name, primary.description))
            metrics.append(Metric("metric.ipv4",
                                  f"{primary.primary_ipv4}/{primary.prefix_len}"
                                  if primary.ipv4 else t("common.none"),
                                  ok=bool(primary.ipv4)))
            metrics.append(Metric("metric.gateway", primary.gateway or t("common.none"),
                                  ok=bool(primary.gateway)))
            if primary.primary_ipv4.startswith("169.254."):
                severity = Severity.CRITICAL
                problems.append(t("check.adapter.problem.apipa", ip=primary.primary_ipv4))
                advice.append(t("check.adapter.advice.apipa"))

        detail_lines = [
            t("check.adapter.detail.line",
              name=a.name,
              status=a.status,
              ip=a.primary_ipv4 or t("value.no_ip"),
              virtual=t("check.adapter.detail.virtual") if a.is_virtual else "")
            for a in adapters[:12]
        ]
        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            # 问题态文案由多条具体事实拼接而成，不含固定模板，
            # 因此仅在正常态挂 key（切换语言时正常结论会跟随，问题详情保持原文）。
            summary_key=("check.adapter.summary_ok" if not problems else ""),
            summary=t("sep.summary").join(problems) if problems else t("check.adapter.summary_ok"),
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=["adapter.renew_dhcp"] if severity is Severity.CRITICAL else [],
            evidence={"adapters": [a.to_dict() for a in adapters],
                      "primary": primary.to_dict() if primary else None},
        )


def _speed_ok(speed: str) -> bool:
    """链路速率 >= 100 Mbps 视为正常；无法解析时返回 True（不误报）。"""
    digits = "".join(ch for ch in speed if ch.isdigit())
    if not digits:
        return True
    value = int(digits)
    if "gbps" in speed.lower():
        value *= 1000
    return value >= 100


__all__ = ["AdapterCheck"]
