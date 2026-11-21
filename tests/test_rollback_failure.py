"""回滚失败路径测试。

存在理由：回滚是全软件最后一道兜底。它平时只有一种表现（成功），
所以它坏掉的方式也很难被看见——备份文件被删、被别的程序改坏、
备份格式与回滚实现不匹配，这些都不会让软件崩溃，只会让"回滚成功"
这句话变成谎话。HANDOFF 的「已知限制 4」长期写着"回滚失败路径未测试"，
本文件就是那条限制的消除。

覆盖的四类真实故障（都可在用户机器上自然发生）：

1. 备份文件被删（磁盘清理、用户手工删了备份目录）
2. 备份文件被改坏（同步盘回写、编辑器保存、杀软隔离后还原）
3. 备份类型与回滚实现不匹配（升级/降级版本后读旧会话）
4. 部分项失败（前一项失败不得中断后面的项）

第 3 类曾是真缺陷：`rollback_item()` 只在 `_dispatch()` 之后判断了
SKIPPED，没判断 ROLLBACK_FAILED，于是"未知类型"被下面两行统一改写为
ROLLED_BACK —— `ok_count=1`、`verified=True`、会话被标记已还原，
而实际上什么都没恢复。这与 ADS 事故是同一形态：备份看着没问题，
回滚在"成功"的假象下彻底失效。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.backup import BackupStore  # noqa: E402
from core.models import ActionState  # noqa: E402
from core.repair import engine as E  # noqa: E402
from core.repair import rollback as RB  # noqa: E402


@pytest.fixture
def store(tmp_path):
    return BackupStore(root=str(tmp_path / "backups"))


@pytest.fixture
def hosts_source(tmp_path):
    """假的 hosts 文件。回滚会写它，所以必须指向临时目录，不能碰系统文件。"""
    path = tmp_path / "hosts"
    path.write_text("127.0.0.1 localhost\n", encoding="utf-8")
    return str(path)


@pytest.fixture
def elevated(monkeypatch):
    """让回滚层以为自己是管理员。

    真实的回滚需要提权，测试机上的 pytest 不是管理员；不提权的话
    每一项都会被 `_elevation_gate()` 判成 SKIPPED，失败路径根本走不到。
    """
    monkeypatch.setattr("core.platform_win.is_elevated", lambda: True)
    return True


def _hosts_item(store, session, source):
    return store.capture_file(session, source, key="hosts", label="HOSTS")


# --------------------------------------------------------------------------- #
# 1. 备份文件被删
# --------------------------------------------------------------------------- #
class TestMissingBackupFile:
    def test_missing_file_fails_with_path(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        item = _hosts_item(store, s, hosts_source)
        os.unlink(os.path.join(s.path, item.file_name))

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert report.ok_count == 0
        assert report.fail_count == 1
        result = report.results[0]
        assert result.state is ActionState.ROLLBACK_FAILED
        assert "FileNotFoundError" in result.error
        # 提示必须含具体路径，否则用户不知道去哪找
        assert item.file_name in result.error

    def test_source_file_untouched(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        item = _hosts_item(store, s, hosts_source)
        before = Path(hosts_source).read_text(encoding="utf-8")
        os.unlink(os.path.join(s.path, item.file_name))

        E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert Path(hosts_source).read_text(encoding="utf-8") == before


# --------------------------------------------------------------------------- #
# 2. 备份文件被改坏
# --------------------------------------------------------------------------- #
class TestCorruptedBackupFile:
    def test_sha_mismatch_refuses_to_restore(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        item = _hosts_item(store, s, hosts_source)
        backup_path = os.path.join(s.path, item.file_name)
        # 模拟"文件还在，但内容被别的程序改过"
        with open(backup_path, "ab") as fh:
            fh.write(b"203.0.113.9 evil.example\n")

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert report.fail_count == 1
        result = report.results[0]
        assert result.state is ActionState.ROLLBACK_FAILED
        assert "sha256" in result.error
        # 关键：宁可回滚失败，也不能拿损坏的备份覆盖用户的 hosts
        assert Path(hosts_source).read_text(encoding="utf-8") == "127.0.0.1 localhost\n"

    def test_empty_backup_is_corruption_not_empty_restore(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        item = _hosts_item(store, s, hosts_source)
        Path(os.path.join(s.path, item.file_name)).write_bytes(b"")

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert report.fail_count == 1
        assert Path(hosts_source).read_text(encoding="utf-8") == "127.0.0.1 localhost\n"


# --------------------------------------------------------------------------- #
# 3. 备份类型与回滚实现不匹配（回归：曾被改写成"成功"）
# --------------------------------------------------------------------------- #
class TestUnknownKind:
    def test_unknown_kind_is_failure_not_success(self, store, elevated):
        """真实缺陷复现：未知 kind 曾返回 ROLLED_BACK + verified=True。"""
        s = store.begin(kind="test")
        store.capture_state(s, key="brandnew:thing", kind="brandnewkind",
                            label="未知类型备份项", payload={"x": 1})

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        result = report.results[0]
        assert result.state is ActionState.ROLLBACK_FAILED, \
            "未知备份类型被当成了成功恢复，回滚会在'什么都没恢复'时上报成功"
        assert result.verified is not True, "未恢复的项不得标记 verified"
        assert report.ok_count == 0
        assert report.fail_count == 1
        assert "brandnewkind" in result.message
        assert "拒绝猜测" in result.error

    def test_unknown_kind_does_not_mark_session_restored(self, store, elevated):
        s = store.begin(kind="test")
        store.capture_state(s, key="brandnew:thing", kind="brandnewkind",
                            label="未知类型备份项", payload={"x": 1})

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert report.marked_restored is False
        assert store.load(s.session_id).restored_at is None

    def test_skip_kinds_still_count_as_handled(self, store, elevated):
        """按设计不自动回滚的类型（dhcp/winhttp）仍是 SKIPPED，不是失败。"""
        s = store.begin(kind="test")
        store.capture_state(s, key="dhcp:eth0", kind=RB.KIND_DHCP, label="DHCP 地址",
                            payload={"ipv4": "192.0.2.42", "gateway": "192.0.2.1"})

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert report.fail_count == 0
        assert report.results[0].state is ActionState.SKIPPED
        assert "192.0.2.42" in report.results[0].message


# --------------------------------------------------------------------------- #
# 4. 中途失败不中断后续项
# --------------------------------------------------------------------------- #
class TestPartialFailureDoesNotAbort:
    def test_later_items_still_attempted(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        # 先放一个必然失败的未知类型，再放一个可正常恢复的 HOSTS。
        # 回滚按反序执行，所以实际顺序是 HOSTS（成功）→ 未知类型（失败）。
        store.capture_state(s, key="brandnew:thing", kind="brandnewkind",
                            label="未知类型备份项", payload={"x": 1})
        _hosts_item(store, s, hosts_source)
        before = Path(hosts_source).read_text(encoding="utf-8")
        Path(hosts_source).write_text("127.0.0.1 localhost\n0.0.0.0 blocked\n",
                                      encoding="utf-8")

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        states = [r.state for r in report.results]
        assert ActionState.ROLLED_BACK in states, "一项失败后其余项必须继续执行"
        assert ActionState.ROLLBACK_FAILED in states
        assert report.ok_count == 1 and report.fail_count == 1
        assert Path(hosts_source).read_text(encoding="utf-8") == before

    def test_failure_keeps_session_retryable(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        item = _hosts_item(store, s, hosts_source)
        backup_path = os.path.join(s.path, item.file_name)
        good = Path(backup_path).read_bytes()
        Path(backup_path).write_bytes(good + b"tampered\n")

        eng = E.RepairEngine(store=store)
        first = eng.rollback(s.session_id, ctx=None)

        assert first.fail_count == 1
        assert first.marked_restored is False
        # 未能全部还原的会话必须仍然可回滚——用户修好后能再试一次，
        # 而不是被误标为"已完成"而失去重试入口。
        assert not store.load(s.session_id).restored_at
        assert store.load(s.session_id).items


# --------------------------------------------------------------------------- #
# 5. 修好之后重试成功
# --------------------------------------------------------------------------- #
class TestRetryAfterRepair:
    def test_retry_succeeds_once_backup_restored(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        item = _hosts_item(store, s, hosts_source)
        backup_path = os.path.join(s.path, item.file_name)
        good = Path(backup_path).read_bytes()

        Path(backup_path).write_bytes(good + b"tampered\n")
        Path(hosts_source).write_text("0.0.0.0 blocked\n", encoding="utf-8")

        eng = E.RepairEngine(store=store)
        first = eng.rollback(s.session_id, ctx=None)
        assert first.fail_count == 1

        # 用户从别处恢复出正确备份（例如手工把文件改回原样）
        Path(backup_path).write_bytes(good)
        second = eng.rollback(s.session_id, ctx=None)

        assert second.fail_count == 0
        assert second.ok_count == 1
        assert second.marked_restored is True
        assert Path(hosts_source).read_text(encoding="utf-8") == "127.0.0.1 localhost\n"
        assert store.load(s.session_id).restored_at is not None


# --------------------------------------------------------------------------- #
# 6. 会话本身就读不出来
# --------------------------------------------------------------------------- #
class TestUnreadableSession:
    def test_missing_session_reports_error(self, store, elevated):
        report = E.RepairEngine(store=store).rollback("20260101-000000_ffffff", ctx=None)

        assert report.fail_count == 0
        assert report.ok_count == 0
        assert "不存在" in report.error
        assert report.marked_restored is False

    def test_session_without_items_reports_error(self, store, elevated):
        s = store.begin(kind="test")
        store.save(s)

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert "没有备份项" in report.error
        assert report.marked_restored is False


# --------------------------------------------------------------------------- #
# 7. 回滚汇总提示
# --------------------------------------------------------------------------- #
class TestRollbackSummary:
    """失败的提示必须说清"哪一项、为什么"，否则用户无法补救。

    曾经的表现：`_render_rollback` 只拼"成功 N 项，失败 M 项"，
    具体错误躺在 ActionResult 里没人看；非管理员整轮被跳过时更是
    "成功 0 项"就结束，界面看起来像什么都没发生。
    """

    def test_lists_each_failed_item_with_reason(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        item = _hosts_item(store, s, hosts_source)
        os.unlink(os.path.join(s.path, item.file_name))

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)
        text = "\n".join(E.rollback_summary_lines(report))

        assert "失败 1 项" in text
        assert f"rollback:{item.key}" in text, "必须点出是哪一项"
        assert "FileNotFoundError" in text, "必须带上具体原因"

    def test_counts_skipped_items(self, store, monkeypatch):
        """非管理员回滚：所有项被跳过，提示必须体现"未还原"而不是静默成功。"""
        monkeypatch.setattr("core.platform_win.is_elevated", lambda: False)
        s = store.begin(kind="test")
        store.capture_state(s, key="tcp:autotuning", kind=RB.KIND_TCP,
                            label="TCP 自动调优", payload={"level": "normal"})

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)
        text = "\n".join(E.rollback_summary_lines(report))

        assert report.fail_count == 0
        assert report.skipped_count == 1
        assert "未还原 1 项" in text
        assert "管理员权限" in text, "必须告诉用户怎么补救"

        # 非管理员时 mark_restored 本就不会执行（前置条件含 elevated），
        # 因此这里只能验文案。"有跳过就不能标已还原"由下面
        # test_all_skipped_does_not_mark_session_restored 覆盖——
        # 那条用例必须是**管理员**身份才测得到真实分支。

    def test_all_skipped_does_not_mark_session_restored(self, store, elevated):
        """管理员身份下回滚"按设计不自动回滚"的会话：不得标记为已还原。

        这是 P2 的实际形态：dhcp / winhttp 类项在管理员下同样返回 SKIPPED，
        因为它们是**设计上不自动回滚**，不是权限问题。此时报告写
        「回滚完成：成功 0 项，未还原 1 项」，若仍写入 restored_at，
        备份列表会显示「（已还原）」、详情页写「已于 … 还原过一次」——
        两处直接矛盾，用户会以为 DHCP 地址已经还原而不去手工核对。

        必须用 elevated fixture：非管理员时 mark_restored 的前置条件
        本就不成立，那样测不到真实分支（第一版用例正是因此没有抓住缺陷）。
        """
        s = store.begin(kind="test")
        store.capture_state(s, key="dhcp:eth", kind=RB.KIND_DHCP, label="DHCP 地址",
                            payload={"ipv4": "192.0.2.42", "gateway": "192.0.2.1"})

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)

        assert report.fail_count == 0
        assert report.skipped_count == 1          # 确认真的走了 SKIPPED 分支
        assert report.marked_restored is False, \
            "一项都没还原的会话被标记为已还原，备份列表会显示「（已还原）」"
        assert store.load(s.session_id).restored_at is None

    def test_clean_rollback_has_no_problem_section(self, store, hosts_source, elevated):
        s = store.begin(kind="test")
        _hosts_item(store, s, hosts_source)

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)
        lines = E.rollback_summary_lines(report)

        assert lines == ["回滚完成：成功 1 项"]

    def test_summary_never_claims_success_when_nothing_restored(self, store, elevated):
        """一行都不能说"成功"以外的误导话术：什么都没恢复时必须全列出来。"""
        s = store.begin(kind="test")
        store.capture_state(s, key="brandnew:thing", kind="brandnewkind",
                            label="未知类型", payload={})

        report = E.RepairEngine(store=store).rollback(s.session_id, ctx=None)
        text = "\n".join(E.rollback_summary_lines(report))

        assert "成功 0 项" in text
        assert "失败 1 项" in text
        assert "brandnewkind" in text


# --------------------------------------------------------------------------- #
# 8. 单条回滚通道（动作自己的 rollback()）
# --------------------------------------------------------------------------- #
class TestSingleActionRollback:
    """`rollback_items_of_kind()` 是 13 个动作单条回滚的唯一入口。

    它曾把 SKIPPED 和 ROLLED_BACK 一起计入 `applied`，然后无条件返回
    ROLLED_BACK + verified=True。于是"非管理员点单条回滚"、"dhcp 按设计
    不自动回滚"这两类什么都没做的情况，都会显示"已恢复 N 项备份"。
    与整轮回滚里 `rollback_item()` 被覆盖是同一模式：聚合层没有尊重
    分派层已定的状态。
    """

    def test_all_skipped_reports_skipped_not_success(self, store, elevated, monkeypatch):
        """全部被跳过（权限不足）时必须是 SKIPPED，不能是 ROLLED_BACK。"""
        monkeypatch.setattr("core.platform_win.is_elevated", lambda: False)
        s = store.begin(kind="test")
        store.capture_state(s, key="tcp:autotuning", kind=RB.KIND_TCP,
                            label="TCP 自动调优", payload={"level": "normal"})

        result = RB.rollback_items_of_kind(store, s, None, kind=RB.KIND_TCP,
                                           action_id="tcp.autotuning")

        assert result.state is ActionState.SKIPPED, \
            "什么都没恢复却上报 ROLLED_BACK，用户会以为配置已经还原"
        assert result.verified is False
        assert "未恢复任何备份项" in result.message
        assert "管理员权限" in result.error

    def test_design_skip_is_not_success(self, store, elevated):
        """dhcp 按设计不自动回滚：同样不能算成功。"""
        s = store.begin(kind="test")
        store.capture_state(s, key="dhcp:eth", kind=RB.KIND_DHCP, label="DHCP 地址",
                            payload={"ipv4": "192.0.2.42", "gateway": "192.0.2.1"})

        result = RB.rollback_items_of_kind(store, s, None, kind=RB.KIND_DHCP,
                                           action_id="adapter.renew_dhcp")

        assert result.state is ActionState.SKIPPED
        assert result.verified is False
        assert "192.0.2.42" in result.error

    def test_failure_and_skip_are_both_reported(self, store, monkeypatch):
        """同批次里既有失败又有跳过：两者都必须出现在原因里。

        构造方式：非管理员回滚 registry 类。HKCU 项不需要提权（不被 gate 拦），
        但它的 .reg 备份文件被删 → 真实失败；HKLM 项被权限 gate 跳过。
        （早先的用例用 hosts + dhcp 两个不同 kind 构造"混合"，但
        `kind="hosts"` 的筛选根本取不到 dhcp 项，等于没测到。）
        """
        monkeypatch.setattr("core.platform_win.is_elevated", lambda: False)
        s = store.begin(kind="test")
        store.capture_state(s, key="reg:hkcu", kind=RB.KIND_REGISTRY,
                            label="HKCU 项", payload={"hive_path": r"HKCU\Software\Test"})
        for item in s.items:
            if item.key == "reg:hkcu":
                fp = os.path.join(s.path, item.file_name)
                if os.path.exists(fp):
                    os.unlink(fp)
        store.capture_state(s, key="reg:hklm", kind=RB.KIND_REGISTRY,
                            label="HKLM 项", payload={"hive_path": r"HKLM\Software\Test"})

        result = RB.rollback_items_of_kind(store, s, None, kind=RB.KIND_REGISTRY,
                                           action_id="proxy.reset")

        assert result.state is ActionState.ROLLBACK_FAILED
        assert result.verified is False
        # 失败原因在
        assert "FileNotFoundError" in result.error
        # 跳过项的条数与原因也在——丢了用户就不知道还有项没尝试还原
        assert "跳过 1 项" in result.message
        assert "管理员权限" in result.error
        assert "[失败]" in result.error and "[跳过]" in result.error

    def test_real_restore_still_reports_success(self, store, hosts_source, elevated):
        """修复不能误伤正常路径：真恢复了就必须报 ROLLED_BACK + verified。"""
        s = store.begin(kind="test")
        _hosts_item(store, s, hosts_source)
        Path(hosts_source).write_text("0.0.0.0 blocked\n", encoding="utf-8")

        result = RB.rollback_items_of_kind(store, s, None, kind=RB.KIND_HOSTS,
                                           action_id="hosts.clean_bad_lines")

        assert result.state is ActionState.ROLLED_BACK
        assert result.verified is True
        assert "已恢复 1 项备份" in result.message
        assert Path(hosts_source).read_text(encoding="utf-8") == "127.0.0.1 localhost\n"

    def test_partial_restore_is_not_reported_as_full_success(self, store, hosts_source, elevated):
        """恢复一半、跳过一半：不能声称全部复原。"""
        s = store.begin(kind="test")
        _hosts_item(store, s, hosts_source)
        # 同 kind 再塞一个必然被跳过的项（kind=hosts 但缺备份文件 → 会失败；
        # 这里用 winhttp 那种"仅记录展示文本"的跳过语义不合适，故构造两个 hosts 项：
        # 一个正常、一个文件被删，验证失败优先于部分成功）。
        item2 = store.capture_file(s, hosts_source, key="hosts2", label="HOSTS 副本")
        os.unlink(os.path.join(s.path, item2.file_name))

        result = RB.rollback_items_of_kind(store, s, None, kind=RB.KIND_HOSTS,
                                           action_id="hosts.clean_bad_lines")

        assert result.state is ActionState.ROLLBACK_FAILED
        assert result.verified is False
        assert "成功 1 项" in result.message


# --------------------------------------------------------------------------- #
# 9. 修复结果汇总（同源问题：全部跳过时像什么都没发生）
# --------------------------------------------------------------------------- #
class TestRepairSummary:
    def _report(self, *states):
        from core.models import ActionResult, ActionState as S
        r = E.RepairReport(session_id="20260101-000000_abcdef")
        r.results = [ActionResult(action_id=f"a{i}", state=s) for i, s in enumerate(states)]
        r.partial = any(s is S.FAILED for s in states)
        return r

    def test_all_skipped_says_skipped(self):
        """全部 SKIPPED（系统不支持/无需修改）不能被显示成"成功 0 项"就完了。"""
        from core.models import ActionState as S
        text = "\n".join(E.repair_summary_lines(self._report(S.SKIPPED, S.SKIPPED)))

        assert "成功 0 项" in text
        assert "跳过 2 项" in text, "跳过必须单独说明，否则用户以为程序没做事"

    def test_skip_count_not_mixed_into_failure(self):
        from core.models import ActionState as S
        lines = E.repair_summary_lines(self._report(S.APPLIED, S.SKIPPED))

        text = "\n".join(lines)
        assert "成功 1 项" in text
        assert "跳过 1 项" in text
        assert "失败" not in text, "跳过不是失败，不能出现失败字样"

    def test_failure_still_warns_rollback(self):
        from core.models import ActionState as S
        text = "\n".join(E.repair_summary_lines(self._report(S.APPLIED, S.FAILED)))

        assert "失败 1 项" in text
        assert "回滚" in text
