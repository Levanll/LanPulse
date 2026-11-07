"""检测单元：Windows 防火墙。

防火墙被关不是「网络故障」，而是安全问题：家庭/公共网络下等于对所有入站连接敞开。
所以全关只给 WARN 而不是 CRITICAL——它不会导致上不了网，排障优先级也不同。

非管理员运行时 `netsh advfirewall show allprofiles` 多数情况下仍能读，但受组策略
或安全软件影响可能返回「拒绝访问」。这种情况必须落到 SKIP 并说明需要管理员权限，
不能编一个「防火墙正常」的结论。
"""
from __future__ import annotations

import re

from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity

# (配置键, i18n key, 输出中的识别片段)。profile 标签是展示文案，因此存 key。
PROFILE_KEYS = (
    ("domain", "profile.domain", ("domain profile", "域配置文件", "域配置")),
    ("private", "profile.private", ("private profile", "专用配置文件", "专用配置")),
    ("public", "profile.public", ("public profile", "公用配置文件", "公用配置")),
)

# 英文版是 `State : ON`（键值间有冒号），中文版是 `状态               关闭`（纯空格对齐），
# 因此冒号必须可选，值按「冒号后或连续空白后」取，两种排版都能解析。
_SEP = r"\s*(?:[:：]\s*|\s{2,})"
_STATE_RE = re.compile(rf"^\s*(?:State|状态){_SEP}(\S.*?)\s*$", re.I)
_POLICY_RE = re.compile(rf"^\s*(?:Firewall Policy|防火墙策略){_SEP}(.+?)\s*$", re.I)
_DENIED_HINTS = ("access is denied", "拒绝访问", "requires elevation", "权限不足",
                 "insufficient", "error:", "错误:")


class FirewallCheck:
    check_id = "firewall"
    title = "check.firewall.title"
    category = "check.firewall.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        rc, out = ctx.cmd(("netsh", "advfirewall", "show", "allprofiles"), timeout=20)
        metrics: list[Metric] = []
        lower = out.lower()

        denied = (rc != 0 or not out.strip()
                  or any(hint in lower for hint in _DENIED_HINTS))
        if denied:
            reason = (t("check.firewall.reason.denied")
                      if any(h in lower for h in _DENIED_HINTS)
                      else t("check.firewall.reason.rc", rc=rc))
            hint = (t("check.firewall.hint.user") if not ctx.elevated
                    else t("check.firewall.hint.admin"))
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.SKIP,
                summary=t("check.firewall.summary_denied"),
            summary_key="check.firewall.summary_denied",
                detail=t("check.firewall.detail_denied", reason=reason, hint=hint,
                         out=out[:300] or t("common.empty")),
                metrics=[Metric("metric.return_code", str(rc)),
                         Metric("metric.is_admin",
                                t("status.yes") if ctx.elevated else t("status.no"),
                                ok=ctx.elevated)],
                advice=[t("check.firewall.advice.denied")],
                evidence={"returncode": rc, "elevated": ctx.elevated, "output": out[:1500]},
            )

        profiles = parse_firewall_profiles(out)
        if not profiles:
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.SKIP,
                summary=t("check.firewall.summary_unparsed"),
            summary_key="check.firewall.summary_unparsed",
                detail=t("check.firewall.detail_unparsed", out=out[:300]),
                metrics=[Metric("metric.return_code", str(rc))],
                evidence={"returncode": rc, "output": out[:1500]},
            )

        off: list[str] = []
        for key, label_key, _ in PROFILE_KEYS:
            info = profiles.get(key)
            if not info or not info.get("state"):
                # 该配置文件没有可识别的 State 行（少见，多为组策略精简输出），不参与判定。
                continue
            enabled = info["state"].strip().lower() in ("on", "enable", "enabled",
                                                        "打开", "启用")
            metrics.append(Metric(
                t("metric.profile_firewall", profile=t(label_key)),
                t("status.on") if enabled else t("status.off"),
                info.get("policy", ""), ok=enabled))
            if not enabled:
                off.append(label_key)  # 存 key，渲染时再翻译

        total = len(profiles)
        actions: list[str] = []
        advice: list[str] = []
        if not metrics:
            # 三个配置文件全部没有可识别的 State 行（组策略精简输出等），无判定依据。
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.SKIP,
                summary=t("check.firewall.summary_no_state"),
            summary_key="check.firewall.summary_no_state",
                detail=t("check.firewall.detail_no_state", out=out[:300]),
                metrics=[Metric("metric.return_code", str(rc))],
                evidence={"returncode": rc, "profiles": profiles, "output": out[:1500]},
            )
        if len(off) == total and total > 0:
            severity = Severity.WARN
            summary_key = "check.firewall.summary_all_off"
            # profiles 传 key 列表，由渲染层按当前语言翻译后再拼接，
            # 否则英文界面会出现「off for all three profiles: 域网络、专用网络、公用网络」
            summary_args = {"profiles_parts": list(off)}
            summary = t("check.firewall.summary_all_off",
                        profiles=t("sep.list").join(t(k) for k in off))
            advice.append(t("check.firewall.advice.all_off"))
            actions.append("firewall.ensure_enabled")
        elif off:
            severity = Severity.INFO
            summary_key = "check.firewall.summary_part_off"
            summary_args = {"profiles": t("sep.list").join(off)}
            summary = t("check.firewall.summary_part_off",
                        profiles=t("sep.list").join(t(k) for k in off))
            advice.append(t("check.firewall.advice.part_off",
                            profiles=t("sep.list").join(t(k) for k in off)))
        else:
            severity = Severity.OK
            summary_key = "check.firewall.summary_ok"
            summary_args = {}
            summary = t("check.firewall.summary_ok")

        detail_lines = [
            t("check.firewall.detail.line",
              label=t(label_key),
              state=profiles[key]["state"],
              policy=profiles[key].get("policy", t("value.inbound_unknown")))
            for key, label_key, _ in PROFILE_KEYS
            if profiles.get(key, {}).get("state")
        ]
        detail_lines.append(t("check.firewall.detail.note"))

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            summary=summary,
            summary_key=summary_key,
            summary_args=summary_args,
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=actions,
            evidence={"profiles": profiles, "returncode": rc,
                      "elevated": ctx.elevated, "output": out[:2500]},
        )


def parse_firewall_profiles(text: str) -> dict[str, dict[str, str]]:
    """解析 show allprofiles 输出，返回 {domain/private/public: {state, policy}}。

    输出随语言变化，因此靠「Profile Settings 块」分段，再在块内找 State 行。
    """
    profiles: dict[str, dict[str, str]] = {}
    current: str | None = None
    for line in text.splitlines():
        low = line.lower()
        matched = None
        for key, _label_key, hints in PROFILE_KEYS:
            if any(h in low for h in hints):
                matched = key
                break
        if matched and ("settings" in low or "配置" in line
                        or line.strip().lower().endswith(":")):
            current = matched
            profiles.setdefault(current, {})
            continue
        if current is None:
            continue
        m = _STATE_RE.match(line)
        if m:
            profiles[current]["state"] = m.group(1)
            continue
        m = _POLICY_RE.match(line)
        if m:
            profiles[current]["policy"] = m.group(1)
    return profiles


__all__ = ["FirewallCheck", "parse_firewall_profiles"]
