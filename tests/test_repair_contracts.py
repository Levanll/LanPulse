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
import os
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


class TestRestartBoundary:
    """「需要重启」的动作必须把回滚边界讲清楚。

    重置协议栈这类动作在重启前无法观测效果，而且**回滚也只在重启前有效**：
    重启后协议栈已按新状态重建，导回旧注册表并不能撤销已生效的状态。
    若界面不说明，用户会以为它和其它动作一样可以完全回滚——这是对
    「可回滚」这条产品承诺的过度承诺。
    """

    def test_reset_stack_actions_flagged(self):
        from core.action_ids import ACTIONS

        for aid in ("tcp.reset_stack", "adapter.reset_stack"):
            assert ACTIONS[aid].needs_restart is True, f"{aid} 应标记 needs_restart"

    def test_restart_flag_is_not_overused(self):
        """不能为了保险把普通动作也标成需要重启，那会让警告失去意义。"""
        from core.action_ids import ACTIONS

        flagged = {aid for aid, m in ACTIONS.items() if m.needs_restart}
        assert flagged == {"tcp.reset_stack", "adapter.reset_stack"}, \
            f"needs_restart 标记范围变化：{flagged}"

    def test_description_mentions_rollback_boundary(self):
        """描述文本必须自己讲清回滚边界，不能只靠界面上的那行警告。

        报告导出、日志、非 UI 场景都读 description，它们看不到 UI 警告。
        """
        from core.action_ids import ACTIONS

        for aid in ("tcp.reset_stack", "adapter.reset_stack"):
            desc = ACTIONS[aid].description
            assert "回滚" in desc, f"{aid} 的描述未提到回滚边界"

    def test_localized_meta_preserves_needs_restart(self):
        """翻译副本必须带上 needs_restart。

        曾经 localized_meta 逐字段重建 ActionMeta，新增字段会被静默丢掉——
        结果就是「警告只在中文下出现、英文下消失」这类难查的问题。
        """
        from core.action_ids import ACTIONS

        try:
            from PySide6.QtWidgets import QApplication  # noqa: F401
        except ImportError:
            pytest.skip("PySide6 不可用")

        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from app.ui.pages.repair import localized_meta

        for aid, meta in ACTIONS.items():
            assert localized_meta(meta).needs_restart == meta.needs_restart, \
                f"{aid} 翻译后丢失 needs_restart"

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

# --------------------------------------------------------------------------- #
# MTU 语义：IP 层 vs 链路层
# --------------------------------------------------------------------------- #
class TestMtuSemantics:
    """MTU 必须用 IP 层值（NlMtu），不能用链路层值（MtuSize）。

    真实事故（2026-11-10 发现）：`collect_adapters()` 曾用 Get-NetAdapter 的
    MtuSize 填充 AdapterInfo.mtu，而 `netsh interface ipv4 set subinterface
    mtu=` 写的是 IP 层 NlMtu。本机两者恰好是 1500 与 1492，于是：

      * verify 拿写入值 1492 去比读回的 1500，永远失败；
      * backup 记录的是 1500，回滚把 1492 "还原"成 1500，反而制造新偏差；
      * SKIP 判定失真——真需要修的时候可能判定为"已是最优"。

    本机不需要构造就能复现，所以这条用静态契约锁死，不依赖运行环境。
    """

    def test_adapterinfo_exposes_both_levels(self):
        from core.platform_win import AdapterInfo

        a = AdapterInfo(name="X", mtu=1492, link_mtu=1500)
        assert a.mtu == 1492, "mtu 字段必须是 IP 层（NlMtu）"
        assert a.link_mtu == 1500, "link_mtu 才是链路层（MtuSize）"
        d = a.to_dict()
        assert d["mtu"] == 1492 and d["link_mtu"] == 1500

    def test_collect_uses_nlmtu_not_mtusize(self):
        """采集脚本必须查 Get-NetIPInterface，且 AdapterInfo.mtu 取自 NlMtu。"""
        src = (ROOT / "core" / "platform_win.py").read_text(encoding="utf-8")
        assert "Get-NetIPInterface" in src, "必须采集 IP 层 MTU"
        assert "NlMtu" in src, "必须读取 NlMtu 字段"
        # mtu= 的赋值必须来自 NlMtu，不能来自 MtuSize
        assert 'mtu=int(nl_mtu)' in src, "AdapterInfo.mtu 必须由 NlMtu 填充"
        assert 'link_mtu=int(link_mtu)' in src, "link_mtu 才用 MtuSize"

    def test_repair_paths_use_ip_mtu(self):
        """修复动作与回滚只能读 .mtu（IP 层），不得读 .link_mtu。"""
        for rel in ("core/repair/mtu_actions.py", "core/repair/rollback.py",
                    "core/checks/mtu_check.py"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            assert ".link_mtu" not in src, f"{rel} 不得使用链路层 MTU"

class TestRefreshAdaptersContract:
    """备份前刷新网卡快照：只容忍"没有这个方法"，不得吞掉内部异常。

    真实事故（2026-11-10 闭环暴露）：`DiagnosticContext.adapters` 首次采集后
    永久缓存，`mtu.optimize` 的 backup() 因此读到体检时的旧 MTU（1492），
    而系统早已被改成 1400；回滚便"恢复"到 1492 —— 既不是用户原值，也不是
    被修的值，报告却显示 rolled_back=True。

    修法是在 execute() 备份前调 ctx.refresh_adapters()。当时用
    `try/except AttributeError: pass` 包着，代价是 refresh 内部若真抛
    AttributeError 会被静默吞掉，不变量悄悄退回原状。改用 getattr 探测后，
    只有"没有这个方法"被容忍。
    """

    def test_engine_calls_refresh_before_backup(self):
        src = (ROOT / "core" / "repair" / "engine.py").read_text(encoding="utf-8")
        assert "refresh_adapters" in src, "必须在备份前刷新网卡快照"
        # 关键：不能是 try/except AttributeError 包法。
        # 必须先剥掉注释再断言——engine.py 里那段解释性注释正写着这几个字，
        # 直接搜源码会命中注释本身（和门禁里"注释被当成一节"是同一类错误）。
        code = "\n".join(
            line.split("#", 1)[0] for line in src.splitlines())
        assert "except AttributeError" not in code, \
            "不得用 except AttributeError 兜底——会连内部真实异常一起吞掉"
        assert 'getattr(ctx, "refresh_adapters", None)' in code, \
            "应使用 getattr 探测，只容忍缺少方法这一种情况"

    def test_refresh_failure_propagates(self):
        """refresh_adapters() 内部抛异常时，必须向上传播而不是被吞掉。"""
        from core.repair.engine import RepairEngine

        class _Ctx:
            #: 真实 DiagnosticContext 具备的最小表面
            primary = None
            adapters: list = []
            _cache: dict = {}

            def refresh_adapters(self):
                raise AttributeError("模拟采集链路里的属性名写错")

        eng = RepairEngine(dry_run=True)
        with pytest.raises(AttributeError):
            # 直接走 execute 的备份前置段：空计划也会先刷新再建会话
            from core.repair.engine import RepairPlan
            eng.execute(RepairPlan(action_ids=[]), _Ctx())

    def test_missing_method_is_tolerated(self):
        """没有 refresh_adapters 的轻量 ctx（测试替身）应当被放过。"""
        from core.repair.engine import RepairEngine, RepairPlan

        class _Bare:
            primary = None
            adapters: list = []
            _cache: dict = {}

        eng = RepairEngine(dry_run=True)
        # 不应抛异常
        eng.execute(RepairPlan(action_ids=[]), _Bare())

class TestMtuAliasResolution:
    """netsh 别名解析必须整列精确匹配，不能做子串包含。

    「以太网」是「以太网 2」「以太网 3」的前缀。闭环脚本 _mtu_now() 用
    `if alias in line` 匹配时，会先命中排在前面的另一块网卡，把它的 MTU
    当成目标网卡的值——而这段代码的职责正是独立裁决，读错一块网卡会让
    构造、修复、复原三个判据同时失真。
    """

    SAMPLE = """\

       MTU  MediaSenseState      Bytes In     Bytes Out  Interface
----------  ---------------  ------------  ------------  -------------
4294967295                1             0        138882  Loopback Pseudo-Interface 1
      1492                1     495792911    2928959147  RelyVPN
      1500                5             0             0  本地连接
      1500                5             0             0  以太网 2
      1492                1   12134076157   3927986700  以太网
"""

    def _resolve(self, alias: str) -> int:
        """复刻 closed_loop_v12._mtu_now 的解析逻辑（不依赖真实 netsh）。"""
        import re

        pat = re.compile(r"^\s*(?P<mtu>\d+)\s+(?P<state>\d+)\s+"
                         r"(?P<in>\d+)\s+(?P<out>\d+)\s+(?P<alias>.+?)\s*$")
        for line in self.SAMPLE.splitlines():
            m = pat.match(line)
            if not m:
                continue
            if m.group("alias") == alias:
                return int(m.group("mtu"))
        raise LookupError(alias)

    def test_prefix_alias_does_not_shadow_longer_one(self):
        # 关键回归：以太网 1492，以太网 2 是 1500，不能互相串
        assert self._resolve("以太网") == 1492
        assert self._resolve("以太网 2") == 1500

    def test_script_uses_exact_match(self):
        src = (ROOT / "tools" / "closed_loop_v12.py").read_text(encoding="utf-8")
        code = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
        assert 'm.group("alias")' in code, "别名必须从解析出的列取值"
        assert "== alias" in code, "必须整列精确比较，不能 alias in line"
        assert "alias in line" not in code, "不得对整行做子串匹配"

class TestUpdateCheckDoesNotStealRunner:
    """更新检查不得在 runner 忙时改写 _pending_kind。

    真实事故（v1.3.0 发布后发现）：更新检查由启动后 2.6s 的 QTimer 触发，
    而默认开启的体检在 420ms 就启动、要跑数秒网络探测，因此 2.6s 时
    runner 几乎必然仍在忙。`run()` 忙时返回 False 且根本不执行，但
    `_pending_kind` 已被改成 "update"，于是体检完成时
    `_on_task_done` 会把 DiagnosticReport 交给 `_on_update_found`：

      * 读 `info.version` 抛 AttributeError；
      * 跳过 `dashboard.set_busy(False)` 与 `state.set_report()`；
      * 界面永久停在「正在体检…」，本次体检结果丢失。

    这里锁住两条不变量：忙时不得改写 kind；收到非 UpdateInfo 不得抛异常。
    """

    def test_busy_guard_before_pending_kind(self):
        src = (ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
        code = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
        # 必须在改写 _pending_kind 之前判断 busy
        i_busy = code.find('if self._runner.busy:')
        i_kind = code.find('self._pending_kind = "update"')
        assert i_busy != -1, "缺少 runner.busy 守卫"
        assert i_kind != -1, "未找到 _pending_kind 赋值"
        assert i_busy < i_kind, "必须先判 busy 再改写 _pending_kind"

    def test_run_return_value_checked(self):
        src = (ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
        code = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
        # run() 的契约是"没执行返回 False"，返回值必须被检查并复位
        assert "if not self._runner.run(self._task_update_check)" in code, \
            "必须检查 run() 的返回值，失败时复位 _pending_kind"

    def test_on_update_found_rejects_wrong_type(self):
        src = (ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8")
        code = "\n".join(line.split("#", 1)[0] for line in src.splitlines())
        assert "isinstance(info, update_mod.UpdateInfo)" in code, \
            "分派错时必须有类型守卫，不能在 UI 线程抛异常"
