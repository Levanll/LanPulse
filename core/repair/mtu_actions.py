"""MTU 修正动作。

为什么这条动作必须"带参构造"而不能有默认值：
    MTU 是链路层握手参数。写一个错误的值（比如把 1500 的以太网链路改成 1400）
    会造成 PMTU 黑洞——大包被丢弃且不返回 ICMP，表现为"能解析、能 ping 小包、
    但网页打不开 / 大文件下载卡死"。这比不改更糟，且极难排查。
    所以 target_mtu 只能来自实测（检测项的 evidence.best_mtu），绝不允许引擎
    自己猜一个值。

校验口径（全部硬失败，不做钳位）：
    必须 int（bool 显式排除，因为 isinstance(True, int) 为 True）、
    必须落在 [1200, 1500] 闭区间。
"""
from __future__ import annotations

from typing import Any

from .. import platform_win as pw
from ..models import ActionState, ActionResult, ChangePreview
from .base import BaseAction, adapter_by_guid, netsh_mtu_set, register_action, require_primary

MTU_MIN = 1200
MTU_MAX = 1500
# 常见链路的 MTU 参考值，仅用于 preview 里解释"目标值是否异常"
MTU_COMMON = (1500, 1492, 1480, 1472, 1460, 1400)


@register_action("mtu.optimize")
class MtuOptimizeAction(BaseAction):
    """把主网卡 MTU 改为实测出的最优值。"""

    action_id = "mtu.optimize"

    def __init__(self, target_mtu: int | None) -> None:
        # 注意这里是**必填参数**（无默认值）：注册表据此把本动作标记为
        # "需要构造参数"，从而不会被 all_actions() 无参实例化，也就不会
        # 出现"用默认值偷偷改了 MTU"的可能。
        if target_mtu is None:
            raise ValueError(
                "mtu.optimize 需要 target_mtu 参数（1200-1500），当前为 None；"
                "该参数应由 mtu 检测项的实测结果提供"
            )
        if isinstance(target_mtu, bool) or not isinstance(target_mtu, int):
            raise ValueError(
                f"mtu.optimize 的 target_mtu 必须是整数，收到 "
                f"{type(target_mtu).__name__}: {target_mtu!r}"
            )
        if not (MTU_MIN <= target_mtu <= MTU_MAX):
            raise ValueError(
                f"mtu.optimize 的 target_mtu 必须在 {MTU_MIN}-{MTU_MAX} 之间，"
                f"收到 {target_mtu}；超出该范围会破坏链路，拒绝执行（不做钳位）"
            )
        self.target_mtu = int(target_mtu)

    def preview(self, ctx: Any) -> ChangePreview:
        primary = require_primary(ctx)
        current = primary.mtu or 0
        if current == self.target_mtu:
            after = f"{self.target_mtu}（与当前相同，执行时该动作会被跳过）"
        else:
            after = f"{self.target_mtu}"
            if self.target_mtu not in MTU_COMMON:
                after += "（非典型值，请确认实测过程可靠）"
        return ChangePreview(
            target=f"{primary.name} / MTU",
            before=f"{current}（ifIndex={primary.if_index}）" if current else "读取失败",
            after=after,
            note="使用 store=persistent 写入，重启后保留；原值会备份，可一键还原",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        primary = require_primary(ctx)
        if not primary.mtu:
            # 读不到当前 MTU 就无法回滚，此时改下去是不可逆操作
            raise RuntimeError(
                f"无法读取「{primary.name}」的当前 MTU（读到 {primary.mtu}），"
                f"没有原值就无法回滚，已中止"
            )
        key = f"mtu:{primary.interface_guid}"
        store.capture_state(
            session,
            key=key,
            kind="mtu",
            label=f"{primary.name} 的 MTU",
            payload={
                "interface_guid": primary.interface_guid,
                "interface_index": primary.if_index,
                "alias": primary.name,
                "mtu": int(primary.mtu),
                "target_mtu": self.target_mtu,
            },
        )
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        primary = require_primary(ctx)
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())

        if primary.mtu == self.target_mtu:
            result.state = ActionState.SKIPPED
            result.message = f"当前 MTU 已是 {self.target_mtu}，无需修改"
            result.finished_at = pw.now()
            return result

        # 先把目标网卡的硬标识记下来，verify 才能复核同一块网卡（名字可能重名）
        cache = getattr(ctx, "_cache", None)
        if isinstance(cache, dict):
            cache[f"repair:target_guid:{self.action_id}"] = primary.interface_guid
            cache[f"repair:target_index:{self.action_id}"] = primary.if_index

        out = netsh_mtu_set(primary.name, self.target_mtu)
        result.finished_at = pw.now()
        result.message = f"「{primary.name}」的 MTU 已从 {primary.mtu} 改为 {self.target_mtu}"
        if out:
            result.detail.extend(line for line in out.splitlines() if line.strip())
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        """按 ifIndex/GUID 精确匹配读回，绝不用名字匹配。

        网卡重名在装了虚拟网卡或多 USB 网卡的机器上很常见，按名字匹配会读到
        另一块网卡的 MTU 而误判成功。
        """
        need = self._target_hint(ctx)
        if need is None:
            return False, "无法确定目标网卡（apply 未记录目标网卡）"
        guid, if_index = need
        latest = adapter_by_guid(guid) if guid else None
        if latest is None and if_index:
            from .base import adapter_by_index

            latest = adapter_by_index(if_index)
        if latest is None:
            return False, f"未找到目标网卡（GUID={guid or '无'}，ifIndex={if_index}）"
        if latest.mtu == self.target_mtu:
            return True, f"读回「{latest.name}」MTU={latest.mtu}（ifIndex={latest.if_index}）"
        return False, (
            f"读回「{latest.name}」MTU={latest.mtu}，期望 {self.target_mtu}"
            f"（ifIndex={latest.if_index}）"
        )

    def _target_hint(self, ctx: Any) -> tuple[str, int] | None:
        store = getattr(ctx, "_cache", None)
        if isinstance(store, dict):
            guid = store.get(f"repair:target_guid:{self.action_id}")
            index = store.get(f"repair:target_index:{self.action_id}")
            if guid or index:
                return (str(guid or ""), int(index or 0))
        # 未记录时退化为"取当前主网卡"，但这是 apply 从未执行过的场景
        primary = ctx.primary
        if primary is None:
            return None
        return (primary.interface_guid, primary.if_index)

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="mtu",
                                      action_id=self.action_id)


__all__ = ["MTU_MAX", "MTU_MIN", "MtuOptimizeAction"]
