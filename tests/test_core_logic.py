"""纯逻辑单元测试。

只测“不碰系统状态”的部分：模型派生、hosts 解析、备份存储、报告渲染。
凡是会修改网络配置的路径都不在此测试——它们在真实环境用 dry-run 验证，
测试里绝不调用 apply 类方法。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import (  # noqa: E402
    ActionResult, ActionState, CheckResult, DiagnosticReport, Metric, Severity,
)


# --------------------------------------------------------------------------- #
# 模型
# --------------------------------------------------------------------------- #
class TestSeverity:
    def test_ordering(self):
        assert Severity.CRITICAL.rank > Severity.WARN.rank > Severity.OK.rank
        assert Severity.SKIP.rank < Severity.OK.rank

    def test_worst(self):
        assert Severity.worst([Severity.OK, Severity.WARN]) is Severity.WARN
        assert Severity.worst([Severity.OK, Severity.CRITICAL, Severity.WARN]) is Severity.CRITICAL
        assert Severity.worst([]) is Severity.SKIP

    def test_worst_ignores_skip_when_others_present(self):
        assert Severity.worst([Severity.SKIP, Severity.INFO]) is Severity.INFO


class TestDiagnosticReport:
    def _mk(self, severities):
        rep = DiagnosticReport(host="TEST", os_name="Windows")
        for i, s in enumerate(severities):
            rep.results.append(CheckResult(
                check_id=f"c{i}", title=f"item{i}", category="test",
                severity=s, summary="sum",
            ))
        return rep

    def test_overall_and_score(self):
        rep = self._mk([Severity.OK, Severity.OK, Severity.OK])
        assert rep.overall is Severity.OK
        assert rep.score == 100

    def test_score_drops_with_problems(self):
        rep = self._mk([Severity.OK, Severity.CRITICAL])
        assert rep.overall is Severity.CRITICAL
        assert rep.score < 60

    def test_problems_excludes_ok_and_skip(self):
        rep = self._mk([Severity.OK, Severity.SKIP, Severity.WARN, Severity.CRITICAL])
        ids = [r.check_id for r in rep.problems()]
        assert ids == ["c2", "c3"]

    def test_skip_not_graded_in_score(self):
        only_ok = self._mk([Severity.OK])
        with_skip = self._mk([Severity.OK, Severity.SKIP])
        assert only_ok.score == with_skip.score

    def test_serialization_roundtrip(self):
        rep = self._mk([Severity.WARN])
        rep.results[0].metrics.append(Metric("m", "v", "n", False))
        data = json.loads(rep.to_json())
        assert data["overall"] == "warn"
        assert data["results"][0]["severity"] == "warn"
        assert data["results"][0]["metrics"][0]["name"] == "m"
        restored = CheckResult.from_dict(data["results"][0])
        assert restored.severity is Severity.WARN
        assert restored.metrics[0].ok is False

    def test_empty_report_safe(self):
        rep = DiagnosticReport()
        assert rep.overall is Severity.SKIP
        assert rep.score == 0
        assert rep.problems() == []


class TestActionResult:
    def test_defaults(self):
        r = ActionResult(action_id="dns.flush_cache")
        assert r.state is ActionState.PENDING
        assert r.to_dict()["state"] == "pending"


# --------------------------------------------------------------------------- #
# HOSTS 解析（核心安全逻辑：清理动作完全依赖它判定删哪几行）
# --------------------------------------------------------------------------- #
class TestHostsParsing:
    @pytest.fixture
    def parse(self):
        from core.checks.hosts_check import parse_hosts

        return parse_hosts

    def test_ignores_comments_and_blanks(self, parse):
        text = "# comment\n\n   \n127.0.0.1 localhost\n"
        a = parse(text)
        assert a.total_lines == 4
        assert len(a.entries) == 1

    def test_detects_blocked(self, parse):
        text = "0.0.0.0 ads.example.com\n127.0.0.1 localhost\n"
        a = parse(text)
        assert len(a.blocked) >= 1
        assert a.entries[1].ip == "127.0.0.1"

    def test_localhost_not_blocked(self, parse):
        text = "127.0.0.1 localhost\n::1 localhost\n"
        a = parse(text)
        assert len(a.blocked) == 0

    def test_detects_hijack_of_critical_domain(self, parse):
        text = "6.6.6.6 www.baidu.com\n"
        a = parse(text)
        assert len(a.hijacked) == 1

    def test_normal_mapping_not_flagged(self, parse):
        text = "192.168.1.10 nas.local\n"
        a = parse(text)
        assert len(a.blocked) == 0
        assert len(a.suspicious) == 0

    def test_inline_comment_stripped(self, parse):
        text = "0.0.0.0 tracker.com  # blocked\n"
        a = parse(text)
        assert a.entries[0].hostnames == ["tracker.com"]

    def test_empty_input(self, parse):
        a = parse("")
        assert a.total_lines == 0
        assert len(a.entries) == 0


# --------------------------------------------------------------------------- #
# 备份存储（这是回滚能力的唯一依赖，必须严格测）
# --------------------------------------------------------------------------- #
class TestBackupStore:
    @pytest.fixture
    def store(self, tmp_path):
        from core.backup import BackupStore

        return BackupStore(root=str(tmp_path))

    def test_begin_creates_dirs(self, store):
        s = store.begin(kind="test")
        assert os.path.isdir(s.path)
        for sub in ("files", "reg", "state"):
            assert os.path.isdir(os.path.join(s.path, sub))

    def test_capture_file_writes_hash(self, store, tmp_path):
        src = tmp_path / "hosts.txt"
        src.write_text("127.0.0.1 localhost\n", encoding="utf-8")
        s = store.begin(kind="test")
        item = store.capture_file(s, str(src), key="hosts", label="HOSTS")
        assert item.payload["size"] > 0
        assert len(item.payload["sha256"]) == 64
        assert os.path.isfile(os.path.join(s.path, item.file_name))

    def test_capture_missing_file_raises(self, store, tmp_path):
        s = store.begin(kind="test")
        with pytest.raises(FileNotFoundError):
            store.capture_file(s, str(tmp_path / "nope"), key="x", label="x")

    def test_capture_state_roundtrip(self, store):
        s = store.begin(kind="test")
        store.capture_state(s, key="dns:1", kind="dns", label="DNS",
                            payload={"servers": ["1.1.1.1"], "was_dhcp": False})
        loaded = store.load(s.session_id)
        assert loaded.items[0].payload["servers"] == ["1.1.1.1"]

    def test_list_sessions_sorted_desc(self, store):
        a = store.begin(kind="A")
        b = store.begin(kind="B")
        b.created_at = a.created_at + 10
        store.save(b)
        sessions = store.list_sessions()
        assert [x.session_id for x in sessions][0] == b.session_id

    def test_corrupt_manifest_skipped_not_crash(self, store):
        s = store.begin(kind="broken")
        store.save(s)
        Path(os.path.join(s.path, "manifest.json")).write_text("{broken", encoding="utf-8")
        assert store.list_sessions() == []

    def test_mark_restored(self, store):
        s = store.begin(kind="test")
        store.save(s)
        store.mark_restored(s)
        assert store.load(s.session_id).restored_at is not None

    def test_prune_keeps_newest(self, store):
        for i in range(5):
            s = store.begin(kind=f"k{i}")
            s.created_at = 1000 + i
            store.save(s)
        removed = store.prune(keep=2)
        assert len(removed) == 3
        assert len(store.list_sessions()) == 2

    # ---- 回归测试：key 中的冒号在 Windows 上会被当成 NTFS 交替数据流 ----
    def test_colon_in_key_does_not_create_ads(self, store, tmp_path):
        """真机缺陷复现：'reg:tcpip.reg' 会变成文件 'reg' 的隐藏流。

        症状极隐蔽：os.path.isfile 返回 True、getsize 也对，但目录里只看到
        一个 0 字节的 'reg'，reg.exe 导入时报"访问注册表时出错"，
        回滚在"备份看起来成功"的情况下彻底失效。
        """
        s = store.begin(kind="test")
        item = store.capture_state(
            s, key="dns:{38AEE8CA-0A51-49DA-9558-01E2D8846CFA}",
            kind="dns", label="DNS", payload={"servers": ["1.1.1.1"]},
        )
        name = os.path.basename(item.file_name)
        assert ":" not in name, f"文件名含冒号，会产生 ADS: {name}"
        full = os.path.join(s.path, item.file_name)
        assert os.path.isfile(full)
        # 内容必须落在普通文件里，而不是长度为 0 的空壳
        assert os.path.getsize(full) > 0, "备份文件为 0 字节，内容可能进了 ADS"

    def test_all_written_files_are_real_files(self, store, tmp_path):
        src = tmp_path / "hosts.txt"
        src.write_text("127.0.0.1 localhost\n", encoding="utf-8")
        s = store.begin(kind="test")
        store.capture_file(s, str(src), key="hosts", label="HOSTS")
        store.capture_state(s, key="tcp:autotuning", kind="tcp", label="TCP",
                            payload={"level": "normal"})
        store.capture_state(s, key="mtu:{GUID}", kind="mtu", label="MTU",
                            payload={"mtu": 1500})
        # 遍历备份目录下所有普通文件，确认没有 0 字节的文件名（即 ADS 空壳）
        for sub in ("files", "state"):
            d = os.path.join(s.path, sub)
            for name in os.listdir(d):
                full = os.path.join(d, name)
                assert os.path.isfile(full)
                assert os.path.getsize(full) > 0, f"{sub}/{name} 为空"
                assert ":" not in name


class TestSafeName:
    def test_strips_colon(self):
        from core.backup import safe_name

        assert safe_name("reg:tcpip") == "reg_tcpip"
        assert ":" not in safe_name("dns:{GUID}")

    def test_strips_path_separators(self):
        from core.backup import safe_name

        for bad in ("a/b", "a\\b", 'a*b', 'a?b', 'a"b', "a<b", "a>b", "a|b"):
            assert "/" not in safe_name(bad)
            assert "\\" not in safe_name(bad)

    def test_reserved_device_names(self):
        from core.backup import safe_name

        for name in ("CON", "PRN", "NUL", "COM1", "LPT9"):
            assert safe_name(name).upper().split(".")[0] not in {
                "CON", "PRN", "AUX", "NUL"
            }, name

    def test_empty_falls_back(self):
        from core.backup import safe_name

        assert safe_name("") == "item"
        assert safe_name("   ") == "item"

    def test_normal_key_unchanged(self):
        from core.backup import safe_name

        assert safe_name("hosts") == "hosts"
        assert safe_name("tcp-autotuning") == "tcp-autotuning"


# --------------------------------------------------------------------------- #
# 报告渲染（转义是真实风险：hosts 内容不可信）
# --------------------------------------------------------------------------- #
class TestReportEscape:
    def test_html_escapes_untrusted_hosts_content(self, tmp_path):
        from app.report import ReportExporter

        rep = DiagnosticReport(host="PC", os_name="Win", elevated=True)
        rep.results.append(CheckResult(
            check_id="hosts", title="HOSTS", category="parse", severity=Severity.WARN,
            summary="suspicious", evidence={"line": "<script>alert(1)</script>"},
        ))
        out = ReportExporter(out_dir=str(tmp_path)).export_html(
            rep, os.path.join(str(tmp_path), "r.html")
        )
        html = Path(out).read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_html_has_no_external_resources(self, tmp_path):
        from app.report import ReportExporter

        rep = DiagnosticReport(host="PC", os_name="Win")
        rep.results.append(CheckResult(check_id="x", title="X", category="Y"))
        out = ReportExporter(out_dir=str(tmp_path)).export_html(
            rep, os.path.join(str(tmp_path), "r2.html")
        )
        html = Path(out).read_text(encoding="utf-8")
        for bad in ("<script src=", '<link rel="stylesheet"', "@import"):
            assert bad not in html


# --------------------------------------------------------------------------- #
# 动作元数据一致性（防止 action_ids 与实现脱节，这是最易腐化的地方）
# --------------------------------------------------------------------------- #
class TestActionRegistry:
    def test_all_metadata_ids_match_keys(self):
        from core.action_ids import ACTIONS

        for key, meta in ACTIONS.items():
            assert meta.action_id == key

    def test_high_risk_not_default_selected(self):
        from core.action_ids import ACTIONS
        from core.models import RiskLevel

        for key, meta in ACTIONS.items():
            if meta.risk is RiskLevel.HIGH:
                assert meta.default_selected is False, f"{key} high-risk must not default"

# --------------------------------------------------------------------------- #
# 更新检测
# --------------------------------------------------------------------------- #
class TestUpdateVersionCompare:
    """版本比较必须按数字分段，不能按字符串。

    字符串比较下 "1.10.0" < "1.9.0" —— 那会让新版本判成旧版本，
    用户永远收不到更新提醒，而且不会有任何报错。这类缺陷只能靠测试锁住。
    """

    def test_dotted_compare(self):
        from core.update import is_newer

        assert is_newer("1.10.0", "1.9.0") is True
        assert is_newer("1.2.10", "1.2.9") is True
        assert is_newer("2.0.0", "1.99.99") is True

    def test_equal_and_older(self):
        from core.update import is_newer

        assert is_newer("1.2.2", "1.2.2") is False
        assert is_newer("1.2.1", "1.2.2") is False

    def test_v_prefix_and_garbage(self):
        from core.update import is_newer, version_tuple

        assert version_tuple("v1.2.3") == (1, 2, 3)
        # 非法输入宁可漏报，不可误报
        assert is_newer("abc", "1.2.2") is False
        assert is_newer("1.2.3", "not-a-version") is False


class TestUpdateManifest:
    def test_valid(self):
        from core.update import parse_manifest

        info = parse_manifest(json.dumps({
            "version": "1.3.0", "url": "https://example.com/x",
            "notes_zh": "中文", "notes_en": "English", "mandatory": False,
        }))
        assert info is not None
        assert info.version == "1.3.0"
        assert info.notes("zh") == "中文"
        assert info.notes("en") == "English"

    def test_notes_fallback(self):
        from core.update import parse_manifest

        info = parse_manifest('{"version":"1.3.0","url":"https://e.com","notes_zh":"只中文"}')
        assert info is not None
        # 英文缺失时回退中文，而不是显示空白
        assert info.notes("en") == "只中文"

    def test_rejects_http_url(self):
        """更新提示会把用户带去下载页，http 等于允许中间人替换页面。"""
        from core.update import parse_manifest

        assert parse_manifest('{"version":"1.3.0","url":"http://e.com"}') is None

    def test_rejects_malformed(self):
        from core.update import parse_manifest

        for bad in ("", "not json", "[]", '{"version":"1.3.0"}',
                    '{"url":"https://e.com"}', '{"version":"x.y","url":"https://e.com"}'):
            assert parse_manifest(bad) is None, bad


class TestUpdateFailureIsSilent:
    """更新检测的任何失败都必须返回 None，绝不抛异常。

    这是网络诊断工具：它自己联网失败时弹错误框是荒谬的，而且会打断体检。
    """

    def test_network_error_returns_none(self):
        from core.update import check_for_update

        def boom(url, *, timeout, current_version):
            raise OSError("network down")

        assert check_for_update("1.2.2", fetch=boom) is None

    def test_bad_payload_returns_none(self):
        from core.update import check_for_update

        assert check_for_update("1.2.2", fetch=lambda u, **k: "<html>404</html>") is None
        assert check_for_update("1.2.2", fetch=lambda u, **k: "") is None

    def test_same_version_is_not_an_update(self):
        from core.update import check_for_update

        payload = '{"version":"1.2.2","url":"https://e.com/x"}'
        assert check_for_update("1.2.2", fetch=lambda u, **k: payload) is None

    def test_newer_version_detected(self):
        from core.update import check_for_update

        payload = '{"version":"1.2.3","url":"https://e.com/x"}'
        info = check_for_update("1.2.2", fetch=lambda u, **k: payload)
        assert info is not None and info.version == "1.2.3"


class TestUpdatePrivacyBoundary:
    """更新检查的请求形态是被写进文档的承诺，这里锁住它。"""

    def test_request_has_no_query_or_identity(self):
        import inspect

        from core import update

        src = inspect.getsource(update._http_get)
        # 必须剥掉注释与 docstring 再断言：函数文档里正写着
        # "不要加主机名/用户名/GUID" 这类禁止性说明，直接搜源码会命中说明本身。
        # （门禁里"注释被当成一节"、测试里"注释被当成代码"，是同一类错误。）
        code_lines = []
        in_doc = False
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.count('"""') % 2 == 1:
                in_doc = not in_doc
                continue
            if in_doc or stripped.startswith("#"):
                continue
            code_lines.append(line.split("#", 1)[0])
        code = "\n".join(code_lines)

        # 不接受调用方拼查询串
        assert "url +" not in code and "?" not in code
        # 请求头里不得出现身份字段
        for banned in ("hostname", "username", "machine", "guid", "token", "email"):
            assert banned not in code.lower(), banned

    def test_updater_url_is_https(self):
        from core.update import UPDATER_URL

        assert UPDATER_URL.startswith("https://")
        assert UPDATER_URL.endswith("latest.json")

    def test_default_is_off(self):
        """默认关闭是产品承诺的一部分，不能被悄悄改成默认开启。"""
        from core.settings import DEFAULTS

        assert DEFAULTS["check_updates"] is False
        assert DEFAULTS["update_prompt_seen"] is False
