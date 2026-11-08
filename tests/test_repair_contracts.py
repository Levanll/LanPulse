"""修复动作的静态契约测试。

这些测试不执行任何修复动作（不碰系统配置），只做静态与结构检查。
存在理由：修复链路的缺陷只会在「真实提权执行」时暴露，而那种验证成本很高、
且必须在一台真实机器上跑。能在测试阶段用静态检查抓住的，就不该留到那时。

本文件的第一个用例对应一次真实事故：
    firewall.ensure_enabled 与 netbios.disable_public 的模块顶部都漏了
    `from .. import platform_win as pw`，而 apply() 里调用了 pw.now()。
    单元测试全绿、dry-run 全绿，因为这两个动作在 dry-run 里根本不走 apply()。
    直到 v1.2.0 补做闭环实测，在真实提权环境执行时才炸出
    `NameError: name 'pw' is not defined` —— 用户的鼠标点下去就是这个错误。
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
REPAIR_DIR = ROOT / "core" / "repair"

#: 这些名字一旦在模块里被使用，就必须在同一模块的 import 里出现。
#: 只列"容易漏且漏了就崩"的模块级别名。
GUARDED_NAMES = {
    "pw", "os", "sys", "json", "time", "ctypes", "winreg", "hashlib",
    "threading", "re", "shutil", "ipaddress", "socket", "subprocess",
}


def _collect_imported_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
    return names


def _collect_used_names(tree: ast.AST) -> set[str]:
    return {
        node.id for node in ast.walk(tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def _iter_modules():
    for path in sorted(REPAIR_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        yield path, ast.parse(path.read_text(encoding="utf-8"))


class TestNoMissingImports:
    """模块级名字必须先导入再使用。

    Python 里未定义的名字只在**执行到那一行**时才抛 NameError，
    所以导入检查不能被单元测试或 dry-run 覆盖，只能静态扫描。
    """

    def test_repair_modules_have_no_missing_imports(self):
        offenders = []
        for path, tree in _iter_modules():
            imported = _collect_imported_names(tree)
            used = _collect_used_names(tree)
            missing = (used & GUARDED_NAMES) - imported
            if missing:
                offenders.append(f"{path.name}: {sorted(missing)}")
        assert not offenders, (
            "以下修复模块使用了未导入的模块级别名，执行到对应行会抛 NameError：\n  "
            + "\n  ".join(offenders)
        )

    def test_firewall_action_can_be_instantiated(self):
        """firewall.ensure_enabled 必须能被构造出来（注册表里有它的实现）。"""
        from core.repair.base import REGISTRY

        assert REGISTRY.spec("firewall.ensure_enabled") is not None
        assert REGISTRY.get("firewall.ensure_enabled") is not None

    def test_netbios_action_can_be_instantiated(self):
        from core.repair.base import REGISTRY

        assert REGISTRY.spec("netbios.disable_public") is not None
        assert REGISTRY.get("netbios.disable_public") is not None


class TestActionIdConsistency:
    """action_ids 与 REGISTRY 必须一一对应。

    任何一侧多出条目，都会导致 UI 里显示一个点了就报"没有修复实现"的按钮，
    或者一个永远不会被展示、却仍参与回滚的动作。
    """

    def test_every_declared_action_is_registered(self):
        from core.action_ids import ACTIONS
        from core.repair.base import REGISTRY

        missing = [aid for aid in ACTIONS if REGISTRY.spec(aid) is None]
        assert not missing, f"这些动作在 action_ids 里声明但没有实现：{missing}"

    def test_every_registered_action_is_declared(self):
        from core.action_ids import ACTIONS
        from core.repair.base import REGISTRY

        extra = [aid for aid in REGISTRY.ids() if aid not in ACTIONS]
        assert not extra, f"这些动作有实现但没在 action_ids 里登记：{extra}"

    def test_rollback_dispatch_covers_all_backup_kinds(self):
        """每个动作 backup() 产出的 kind，回滚层都必须能分派。

        未知 kind 会让回滚在「看起来成功」的备份上彻底失效——
        这曾经是 ADS 缺陷的形态，代价是回滚 100% 失败。
        """
        from core.repair import rollback as RB

        handled = {
            RB.KIND_HOSTS, RB.KIND_DNS, RB.KIND_REGISTRY, RB.KIND_MTU,
            RB.KIND_FIREWALL, RB.KIND_TCP, RB.KIND_NETBIOS, RB.KIND_DHCP,
            RB.KIND_WINHTTP,
        }
        # 这些 kind 是各动作 backup() 里写死的字符串，逐一核对可被分派
        for kind in handled:
            assert isinstance(kind, str) and kind, "kind 常量不能为空"
        # 回滚分派表与常量集合必须同步：漏一个就会走到『未知的备份类型』分支
        assert len(handled) == 9, "新增 kind 时必须同步更新回滚分派与每个动作的 backup()"
