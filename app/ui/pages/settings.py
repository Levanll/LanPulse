"""设置页 —— 语言、区域、检测策略、数据管理。

设计取向：普通用户只需要改「语言」和「区域」两项；其余是排障用的高级项，
默认折叠。这样既不把界面变成控制面板，也不隐瞒可调参数。
"""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from core import i18n
from core.i18n import t
from core import region as region_mod
from core.settings import (
    ALL_LANGS, LANG_AUTO, LANG_EN, LANG_ZH, Settings,
)
from app.ui.theme import T, mono_font, ui_font
from app.ui.widgets import Card, Panel


class SettingRow(QWidget):
    """一行设置：左侧标题+说明，右侧控件。"""

    def __init__(self, title: str, desc: str, control: QWidget,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(16)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setFont(ui_font(10))
        self.title_label.setStyleSheet(f"color:{T.TEXT};")
        self.desc_label = QLabel(desc)
        self.desc_label.setObjectName("Caption")
        self.desc_label.setWordWrap(True)
        texts.addWidget(self.title_label)
        texts.addWidget(self.desc_label)
        lay.addLayout(texts, 1)

        control.setMinimumWidth(180)
        lay.addWidget(control, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def retranslate(self, title: str, desc: str) -> None:
        self.title_label.setText(title)
        self.desc_label.setText(desc)


class SettingsPage(QWidget):
    language_changed = Signal(str)
    region_changed = Signal(str)
    settings_changed = Signal(str)
    request_open_data_dir = Signal()

    def __init__(self, state, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self.settings = settings
        self._rows: list[tuple[SettingRow, str, str]] = []
        self._build()
        self._sync_from_settings()
        self.retranslate()

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(2, 2, 10, 10)
        lay.setSpacing(12)

        # ---------------- 通用 ----------------
        self.card_general = Card(t("settings.section.general"), "")
        gen = self.card_general.body

        self.lang_combo = QComboBox()
        for code in ALL_LANGS:
            self.lang_combo.addItem("", code)
        self.lang_combo.currentIndexChanged.connect(self._on_language)
        self.row_lang = SettingRow("", "", self.lang_combo)
        gen.addWidget(self.row_lang)

        self.region_combo = QComboBox()
        for code in (region_mod.REGION_AUTO,) + region_mod.ALL_REGIONS:
            self.region_combo.addItem("", code)
        self.region_combo.currentIndexChanged.connect(self._on_region)
        self.row_region = SettingRow("", "", self.region_combo)
        gen.addWidget(self.row_region)

        self.region_hint = QLabel("")
        self.region_hint.setObjectName("Caption")
        self.region_hint.setWordWrap(True)
        gen.addWidget(self.region_hint)

        self.chk_autoscan = QCheckBox()
        self.chk_autoscan.toggled.connect(
            lambda v: self._set("auto_scan_on_start", v))
        self.row_autoscan = SettingRow("", "", self.chk_autoscan)
        gen.addWidget(self.row_autoscan)
        lay.addWidget(self.card_general)

        # ---------------- 检测 ----------------
        self.card_scan = Card(t("settings.section.scan"), "")
        scan = self.card_scan.body

        self.chk_probe = QCheckBox()
        self.chk_probe.toggled.connect(self._on_probe)
        self.row_probe = SettingRow("", "", self.chk_probe)
        scan.addWidget(self.row_probe)

        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.5, 4.0)
        self.timeout_spin.setSingleStep(0.5)
        self.timeout_spin.setDecimals(1)
        self.timeout_spin.valueChanged.connect(
            lambda v: self._set("timeout_scale", round(float(v), 1)))
        self.row_timeout = SettingRow("", "", self.timeout_spin)
        scan.addWidget(self.row_timeout)
        lay.addWidget(self.card_scan)

        # ---------------- 备份 ----------------
        self.card_backup = Card(t("settings.section.backup"), "")
        bk = self.card_backup.body
        self.keep_spin = QSpinBox()
        self.keep_spin.setRange(5, 200)
        self.keep_spin.valueChanged.connect(lambda v: self._set("backup_keep", int(v)))
        self.row_keep = SettingRow("", "", self.keep_spin)
        bk.addWidget(self.row_keep)
        lay.addWidget(self.card_backup)

        # ---------------- 安全 ----------------
        self.card_safety = Card(t("settings.section.safety"), "")
        sf = self.card_safety.body

        self.chk_highrisk = QCheckBox()
        self.chk_highrisk.toggled.connect(
            lambda v: self._set("extra_confirm_high_risk", v))
        self.row_highrisk = SettingRow("", "", self.chk_highrisk)
        sf.addWidget(self.row_highrisk)
        lay.addWidget(self.card_safety)

        # ---------------- 报告 ----------------
        self.card_report = Card(t("settings.section.report"), "")
        rp = self.card_report.body
        self.fmt_combo = QComboBox()
        for fmt in ("html", "json", "text"):
            self.fmt_combo.addItem("", fmt)
        self.fmt_combo.currentIndexChanged.connect(
            lambda _: self._set("report_format", self.fmt_combo.currentData()))
        self.row_fmt = SettingRow("", "", self.fmt_combo)
        rp.addWidget(self.row_fmt)

        self.chk_evidence = QCheckBox()
        self.chk_evidence.toggled.connect(
            lambda v: self._set("report_include_evidence", v))
        self.row_evidence = SettingRow("", "", self.chk_evidence)
        rp.addWidget(self.row_evidence)
        lay.addWidget(self.card_report)

        # ---------------- 数据管理 ----------------
        self.card_data = Card(t("settings.section.data"), "")
        dm = self.card_data.body

        btn_row = QWidget()
        br = QHBoxLayout(btn_row)
        br.setContentsMargins(0, 4, 0, 0)
        br.setSpacing(9)
        self.btn_open_data = QPushButton()
        self.btn_open_data.setObjectName("Ghost")
        self.btn_open_data.clicked.connect(self.request_open_data_dir)
        br.addWidget(self.btn_open_data)

        self.btn_open_settings = QPushButton()
        self.btn_open_settings.setObjectName("Ghost")
        self.btn_open_settings.clicked.connect(self._open_settings_file)
        br.addWidget(self.btn_open_settings)

        self.btn_reset = QPushButton()
        self.btn_reset.setObjectName("Danger")
        self.btn_reset.clicked.connect(self._reset)
        br.addWidget(self.btn_reset)
        br.addStretch(1)
        dm.addWidget(btn_row)

        self.path_label = QLabel(self.settings.path)
        self.path_label.setFont(mono_font(8))
        self.path_label.setStyleSheet(f"color:{T.TEXT_FAINT};")
        self.path_label.setWordWrap(True)
        dm.addWidget(self.path_label)
        lay.addWidget(self.card_data)

        lay.addStretch(1)

    # ------------------------------------------------------------------ #
    def _register(self, row: SettingRow, title_key: str, desc_key: str) -> None:
        self._rows.append((row, title_key, desc_key))

    def _set(self, key: str, value) -> None:
        if self.settings.get(key) == value:
            return
        self.settings.set(key, value)
        self.settings_changed.emit(key)

    def _on_language(self, _index: int) -> None:
        code = self.lang_combo.currentData()
        if not code:
            return
        self._set("language", code)
        effective = code if code in (LANG_ZH, LANG_EN) else self._effective_auto()
        i18n.set_language(effective)
        self.language_changed.emit(effective)

    @staticmethod
    def _effective_auto() -> str:
        from core.settings import effective_language

        class _S:
            def get(self, k, d=None):
                return LANG_AUTO

        return effective_language(_S())  # type: ignore[arg-type]

    def _on_region(self, _index: int) -> None:
        code = self.region_combo.currentData()
        if not code:
            return
        self._set("region", code)
        self.region_changed.emit(code)
        self._update_region_hint()

    def _on_probe(self, value: bool) -> None:
        self._set("allow_network_probe", bool(value))
        # 关闭联网探测时，超时设置失去意义
        self.timeout_spin.setEnabled(bool(value))

    # ------------------------------------------------------------------ #
    def _sync_from_settings(self) -> None:
        self._select_data(self.lang_combo, self.settings.get("language", LANG_AUTO))
        self._select_data(self.region_combo, self.settings.get("region", region_mod.REGION_AUTO))
        self.chk_autoscan.setChecked(self.settings.get_bool("auto_scan_on_start"))
        self.chk_probe.setChecked(self.settings.get_bool("allow_network_probe"))
        self.timeout_spin.setValue(self.settings.get_float("timeout_scale"))
        self.timeout_spin.setEnabled(self.settings.get_bool("allow_network_probe"))
        self.keep_spin.setValue(self.settings.get_int("backup_keep"))
        self.chk_highrisk.setChecked(self.settings.get_bool("extra_confirm_high_risk"))
        self._select_data(self.fmt_combo, self.settings.get("report_format", "html"))
        self.chk_evidence.setChecked(self.settings.get_bool("report_include_evidence"))
        self._update_region_hint()

    @staticmethod
    def _select_data(combo: QComboBox, value) -> None:
        idx = combo.findData(value)
        if idx >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(idx)
            combo.blockSignals(False)

    def _update_region_hint(self) -> None:
        code = self.region_combo.currentData() or region_mod.REGION_AUTO
        if code != region_mod.REGION_AUTO:
            prof = region_mod.get_profile(code)
            self.region_hint.setText(
                t("settings.region.fixed_hint", region=t(prof.name_key))
            )
            return
        # 自动模式下要说清三件事：识别成了哪个区域、凭什么、以及港澳台盲区。
        # 只写"根据时区自动判断"等于什么都没说——用户看不出判得对不对。
        detected, basis = self._detect_region_basis()
        if detected is None:
            self.region_hint.setText(t("settings.region.auto_hint"))
            return
        lines = [
            t("settings.region.detected", region=t(region_mod.region_display_key(detected))),
            t("settings.region.basis", basis=basis),
        ]
        # 大陆 / 香港 / 澳门 共用 China Standard Time，是唯一需要额外说明的盲区
        if detected in (region_mod.REGION_CN, region_mod.REGION_HK, region_mod.REGION_MO):
            lines.append(t("settings.region.shared_tz"))
        self.region_hint.setText("\n".join(lines))

    def _detect_region_basis(self) -> tuple[str | None, str]:
        """返回 (识别到的区域, 依据说明)。失败时返回 (None, "")。

        复用缓存的结果，不在这里重新探测：设置页打开时不该触发一轮网络请求。
        缓存在 AppState 体检时已由 DiagnosticContext 填好；若还没有（用户刚开
        软件就进设置页），就用纯本地推断，明确告诉用户依据只有时区/语言。
        """
        ctx = getattr(self.state, "context", None)
        if ctx is not None:
            try:
                key = ctx.region_key
                ev = ctx.region_evidence or {}
                return key, self._describe_basis(ev)
            except Exception:  # noqa: BLE001 - 提示文案失败不该让设置页崩
                pass
        # 还没有体检上下文：纯本地推断，不发网络请求
        try:
            if self.settings.get("region", region_mod.REGION_AUTO) != region_mod.REGION_AUTO:
                return None, ""
            key, ev = region_mod.detect_region(probe=False)
            return key, self._describe_basis(ev)
        except Exception:  # noqa: BLE001
            return None, ""

    @staticmethod
    def _describe_basis(evidence: dict) -> str:
        """把 reason 字段翻译成一句人话。"""
        reason = str(evidence.get("reason") or "")
        tz = evidence.get("timezone") or ""
        if reason.startswith("latency:cn_faster"):
            cn = evidence.get("cn_anchor_ms")
            return t("settings.region.basis.latency_cn",
                     cn=f"{cn:.0f}" if isinstance(cn, (int, float)) else "—")
        if reason.startswith("latency:not_cn"):
            gl = evidence.get("global_anchor_ms")
            return t("settings.region.basis.latency_not_cn",
                     gl=f"{gl:.0f}" if isinstance(gl, (int, float)) else "—")
        if reason.startswith("timezone:"):
            return t("settings.region.basis.timezone", tz=tz or reason.split(":", 1)[1])
        if reason == "locale":
            return t("settings.region.basis.locale")
        return t("settings.region.basis.none")

    def refresh_region_hint(self) -> None:
        """外部触发刷新区域提示（主窗口在切到设置页时调用）。

        区域识别的依据来自最近一次体检的上下文；用户可能先开设置页（那时
        只有本地推断），体检完再回来时应当看到带实测证据的新提示。
        """
        self._update_region_hint()

    # ------------------------------------------------------------------ #
    def retranslate(self) -> None:
        """语言切换后重刷所有静态文案。"""
        self.card_general.set_title(t("settings.section.general"))
        self.card_scan.set_title(t("settings.section.scan"))
        self.card_backup.set_title(t("settings.section.backup"))
        self.card_safety.set_title(t("settings.section.safety"))
        self.card_report.set_title(t("settings.section.report"))
        self.card_data.set_title(t("settings.section.data"))

        self.row_lang.retranslate(t("settings.language.title"), t("settings.language.desc"))
        self.row_region.retranslate(t("settings.region.title"), t("settings.region.desc"))
        self.row_autoscan.retranslate(t("settings.autoscan.title"), t("settings.autoscan.desc"))
        self.row_probe.retranslate(t("settings.probe.title"), t("settings.probe.desc"))
        self.row_timeout.retranslate(t("settings.timeout.title"), t("settings.timeout.desc"))
        self.row_keep.retranslate(t("settings.backupkeep.title"), t("settings.backupkeep.desc"))
        self.row_highrisk.retranslate(
            t("settings.highrisk.title"), t("settings.highrisk.desc"))
        self.row_fmt.retranslate(t("settings.reportfmt.title"), t("settings.reportfmt.desc"))
        self.row_evidence.retranslate(
            t("settings.evidence.title"), t("settings.evidence.desc"))

        # 下拉框条目
        self._retranslate_combo(self.lang_combo, {
            LANG_AUTO: t("settings.language.auto"),
            LANG_ZH: t("lang.zh"),
            LANG_EN: t("lang.en"),
        })
        region_labels = {region_mod.REGION_AUTO: t("settings.region.auto")}
        for code in region_mod.ALL_REGIONS:
            region_labels[code] = t(region_mod.get_profile(code).name_key)
        self._retranslate_combo(self.region_combo, region_labels)
        self._retranslate_combo(self.fmt_combo, {
            "html": t("settings.reportfmt.html"),
            "json": t("settings.reportfmt.json"),
            "text": t("settings.reportfmt.text"),
        })

        self.btn_open_data.setText(t("settings.open_data"))
        self.btn_open_settings.setText(t("settings.open_settings"))
        self.btn_reset.setText(t("settings.reset"))
        self._update_region_hint()

    @staticmethod
    def _retranslate_combo(combo: QComboBox, labels: dict) -> None:
        combo.blockSignals(True)
        for i in range(combo.count()):
            key = combo.itemData(i)
            if key in labels:
                combo.setItemText(i, labels[key])
        combo.blockSignals(False)

    # ------------------------------------------------------------------ #
    def _open_settings_file(self) -> None:
        try:
            os.startfile(self.settings.path)  # noqa: S606 - 用户显式点击打开自己电脑上的配置文件
        except OSError as exc:
            QMessageBox.warning(self, t("err.open_failed"), f"{self.settings.path}\n\n{exc}")

    def _reset(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(t("settings.reset.confirm.title"))
        box.setText(t("settings.reset.confirm.body"))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText(t("btn.yes"))
        box.button(QMessageBox.StandardButton.No).setText(t("btn.no"))
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        self.settings.reset()
        self._sync_from_settings()
        lang = self._effective_language()
        i18n.set_language(lang)
        self.language_changed.emit(lang)
        self.settings_changed.emit("*")

    def _effective_language(self) -> str:
        from core.settings import effective_language

        return effective_language(self.settings)


__all__ = ["SettingsPage", "SettingRow"]
