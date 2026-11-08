"""防火墙开关修复动作。

现实场景：装了某个"安全优化"工具或游戏加速器后，Windows 防火墙的三个 profile
被静默关掉，用户既没察觉也没有提示。这条动作把被关掉的 profile 全部打开。

只做开启方向，不做"按检测结果随意开关"：把防火墙关掉永远不该是本软件的建议，
哪怕用户觉得它挡了某个程序。
"""
from __future__ import annotations

from typing import Any

from .. import platform_win as pw
from ..models import ActionState, ActionResult, ChangePreview
from .base import (
    BaseAction,
    FIREWALL_PROFILES,
    netsh_firewall_set,
    read_firewall_profiles,
    register_action,
)

_PROFILE_LABEL = {key: zh for key, zh, _ in FIREWALL_PROFILES}


def _label(profile: str) -> str:
    return _PROFILE_LABEL.get(profile, profile)


@register_action("firewall.ensure_enabled")
class FirewallEnsureEnabledAction(BaseAction):
    """把三个防火墙配置文件全部置为开启。"""

    action_id = "firewall.ensure_enabled"

    def preview(self, ctx: Any) -> ChangePreview:
        profiles = read_firewall_profiles()
        off = [p for p, state in profiles.items() if state != "ON"]
        before = "；".join(f"{_label(p)}={profiles[p]}" for p in profiles)
        if not off:
            return ChangePreview(
                target="Windows 防火墙（域 / 专用 / 公用）",
                before=before,
                after="保持全部开启，无需修改",
                note="三个配置文件都已开启时不会执行任何命令",
            )
        return ChangePreview(
            target="Windows 防火墙（域 / 专用 / 公用）",
            before=before,
            after="；".join(f"{_label(p)}=ON" for p in profiles),
            note=f"当前关闭的是 {'、'.join(_label(p) for p in off)}；"
                 f"开启后可能需要在防火墙里为特定程序放行",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        profiles = read_firewall_profiles()
        key = "firewall:profiles"
        store.capture_state(
            session,
            key=key,
            kind="firewall",
            label="防火墙配置文件开关状态",
            payload={"profiles": profiles},
        )
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        before = read_firewall_profiles()
        already_on = [p for p, state in before.items() if state == "ON"]

        if len(already_on) == len(before):
            result.state = ActionState.SKIPPED
            result.message = "三个防火墙配置文件均已开启，无需修改"
            result.finished_at = pw.now()
            return result

        # 逐个 profile 设置而不是 `set allprofiles`：单个 profile 失败时，
        # 其余两个仍能生效，且能准确报告是哪个失败。
        for profile in before:
            if before[profile] == "ON":
                continue
            out = netsh_firewall_set(profile, True)
            result.detail.append(f"{_label(profile)}: {before[profile]} -> ON")
            if out:
                result.detail.extend(line for line in out.splitlines() if line.strip())
        result.finished_at = pw.now()
        result.message = (
            "防火墙已开启：" + "、".join(_label(p) for p in before if before[p] != "ON")
        )
        result.detail.append("提示：如有程序被防火墙拦下，可在「允许应用通过防火墙」中放行")
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        profiles = read_firewall_profiles()
        off = [p for p, state in profiles.items() if state != "ON"]
        if off:
            return False, f"仍有配置文件未开启：{'、'.join(_label(p) for p in off)}"
        return True, "域 / 专用 / 公用 三个配置文件均为 ON"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="firewall",
                                      action_id=self.action_id)


__all__ = ["FirewallEnsureEnabledAction"]
