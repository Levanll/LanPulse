"""修复引擎。

模块导入即完成动作注册（每个动作文件用 @register_action 自登记）。
新增修复能力只需：在 core/action_ids.py 登记元数据 -> 在 core/repair/ 里实现 ->
在本文件加一行 import。UI 与 engine 不需要任何改动。
"""
from __future__ import annotations

# --- 导入即注册：顺序无关，但 import 必须在导出前完成 ---
from . import (  # noqa: F401
    adapter_actions,
    dns_actions,
    firewall_actions,
    hosts_actions,
    mtu_actions,
    netbios_actions,
    proxy_actions,
    tcp_actions,
)
from .base import REGISTRY, ActionRegistry, ActionSpec, RepairAction, register_action
from .engine import (
    RepairEngine,
    RepairPlan,
    RepairReport,
    RollbackReport,
    create_manual_backup,
)
from .hosts_actions import save_hosts_text
from .rollback import rollback_item, rollback_items_of_kind

# 权威清单与已实现清单的交集，供 UI 直接展示"哪些能被修复"
from ..action_ids import ACTIONS

SUPPORTED_ACTION_IDS: tuple[str, ...] = tuple(
    aid for aid in ACTIONS if REGISTRY.spec(aid) is not None
)

# 未实现的动作 id（正常情况下应为空；留作自检与 UI 降级展示）
UNSUPPORTED_ACTION_IDS: tuple[str, ...] = tuple(
    aid for aid in ACTIONS if REGISTRY.spec(aid) is None
)


def get_action(action_id: str, params: dict | None = None) -> RepairAction:
    """按 id 取动作实例。带参动作必须给 params（如 mtu.optimize）。"""
    return REGISTRY.get(action_id, params)


def all_actions() -> list[RepairAction]:
    """全部无需构造参数的动作实例。"""
    return REGISTRY.all_actions()


def parameterized_action_ids() -> list[str]:
    """需要构造参数的动作 id（目前只有 mtu.optimize）。"""
    return REGISTRY.parameterized_action_ids()


__all__ = [
    "REGISTRY",
    "SUPPORTED_ACTION_IDS",
    "UNSUPPORTED_ACTION_IDS",
    "ActionRegistry",
    "ActionSpec",
    "RepairAction",
    "RepairEngine",
    "RepairPlan",
    "RepairReport",
    "RollbackReport",
    "all_actions",
    "create_manual_backup",
    "get_action",
    "parameterized_action_ids",
    "register_action",
    "rollback_item",
    "rollback_items_of_kind",
    "save_hosts_text",
]
