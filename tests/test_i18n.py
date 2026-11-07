"""i18n 与设置的单元测试。

锁住三件事：
  1. 两个语言包的 key 集合完全一致、无空值、占位符一致（否则运行时会抛异常或错位）
  2. 检测结果的文案能在切换语言后真的跟随（这是整项改造的目标）
  3. 设置能持久化、损坏文件不导致崩溃
"""
from __future__ import annotations

import json
import os
import string
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.i18n as i18n  # noqa: E402
from app import i18n_en, i18n_zh  # noqa: E402


# --------------------------------------------------------------------------- #
class TestCatalogIntegrity:
    def test_key_sets_identical(self):
        zh, en = set(i18n_zh.CATALOG), set(i18n_en.CATALOG)
        assert zh == en, (
            f"仅中文有: {sorted(zh - en)[:10]}  仅英文有: {sorted(en - zh)[:10]}"
        )

    def test_no_empty_values(self):
        for name, cat in (("zh", i18n_zh.CATALOG), ("en", i18n_en.CATALOG)):
            empty = [k for k, v in cat.items() if not str(v).strip()]
            assert not empty, f"{name} 有空文案: {empty[:10]}"

    def test_placeholders_match(self):
        """同一 key 的 {placeholder} 集合必须一致，否则 .format() 会行为不一致。"""
        def ph(text: str) -> set[str]:
            return {
                name
                for _, name, _, _ in string.Formatter().parse(text)
                if name
            }

        bad = []
        for k, zh_text in i18n_zh.CATALOG.items():
            en_text = i18n_en.CATALOG.get(k, "")
            if ph(zh_text) != ph(en_text):
                bad.append((k, ph(zh_text), ph(en_text)))
        assert not bad, f"占位符不一致: {bad[:5]}"

    def test_catalog_not_trivially_small(self):
        assert len(i18n_zh.CATALOG) > 500


class TestRuntimeLookup:
    def test_switch_changes_result(self):
        orig = i18n.get_language()
        try:
            i18n.set_language("zh")
            zh = i18n.t("nav.overview")
            i18n.set_language("en")
            en = i18n.t("nav.overview")
            assert zh != en
            assert zh and en
        finally:
            i18n.set_language(orig)

    def test_missing_key_is_visible(self):
        """缺失必须显式暴露，不能静默退回英文——否则漏翻永远发现不了。"""
        out = i18n.t("__definitely_not_a_key__")
        assert out.startswith("\u27e6")

    def test_format_args_applied(self):
        text = i18n.t("settings.cleaned", n=3)
        assert "3" in text


# --------------------------------------------------------------------------- #
class TestResultRetranslation:
    """检测结果在切换语言后要能跟随——这是本次改造的核心命题。"""

    def _result(self):
        from core.models import CheckResult

        return CheckResult(
            check_id="demo",
            title="check.adapter.title",
            category="check.adapter.category",
            summary="静态文案",
            summary_key="check.ip.summary_ok",
            summary_args={"ip": "1.2.3.4", "prefix": 24, "mode": "value.static"},
        )

    def test_summary_follows_language(self):
        from app.ui.i18n_ui import tr_result_summary

        orig = i18n.get_language()
        try:
            i18n.set_language("zh")
            zh = tr_result_summary(self._result())
            i18n.set_language("en")
            en = tr_result_summary(self._result())
        finally:
            i18n.set_language(orig)
        assert zh != en
        assert "1.2.3.4/24" in zh and "1.2.3.4/24" in en
        # 嵌套的 value.* key 必须被翻译，不能露出原始 key
        assert "value.static" not in zh
        assert "value.static" not in en

    def test_no_placeholder_leaks(self):
        from app.ui.i18n_ui import tr_result_summary

        orig = i18n.get_language()
        try:
            for lang in ("zh", "en"):
                i18n.set_language(lang)
                out = tr_result_summary(self._result())
                assert "{" not in out, f"{lang} 出现未填充占位符: {out}"
        finally:
            i18n.set_language(orig)


class TestArgResolver:
    def test_plain_values_pass_through(self):
        from core.i18n_args import resolve_args

        out = resolve_args({"ip": "10.0.0.1", "n": 3})
        assert out == {"ip": "10.0.0.1", "n": 3}

    def test_key_values_translated(self):
        from core.i18n_args import resolve_args

        orig = i18n.get_language()
        try:
            i18n.set_language("en")
            out = resolve_args({"mode": "value.static"})
            assert out["mode"] == i18n_en.CATALOG["value.static"]
        finally:
            i18n.set_language(orig)

    def test_parts_joined(self):
        from core.i18n_args import resolve_args

        out = resolve_args({"profiles_parts": ["profile.domain", "profile.public"]})
        assert "profiles" in out
        assert out["profiles"]


# --------------------------------------------------------------------------- #
class TestSettings:
    @pytest.fixture
    def settings(self, tmp_path):
        from core.settings import load_settings

        return load_settings(str(tmp_path / "settings.json"))

    def test_defaults_when_missing(self, settings):
        assert settings.get("language") == "auto"
        assert settings.get_int("backup_keep") == 30

    def test_persist_roundtrip(self, settings, tmp_path):
        from core.settings import load_settings

        settings.set("language", "en")
        again = load_settings(str(tmp_path / "settings.json"))
        assert again.get("language") == "en"

    def test_corrupt_file_does_not_crash(self, tmp_path):
        from core.settings import load_settings

        p = tmp_path / "settings.json"
        p.write_text("{ this is not json", encoding="utf-8")
        s = load_settings(str(p))
        assert s.get("language") == "auto"
        # 损坏文件应被备份，避免用户无感知地丢失原设置
        assert (tmp_path / "settings.json.invalid").is_file()

    def test_change_listener_fires(self, settings):
        seen = []
        settings.on_change(lambda k, v: seen.append((k, v)))
        settings.set("language", "en")
        assert seen == [("language", "en")]

    def test_unknown_keys_preserved(self, settings):
        settings.set("future_option", 42)
        assert settings.get("future_option") == 42
