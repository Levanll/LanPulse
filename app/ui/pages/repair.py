"""一键修复页 —— 软件安全性的门面。

设计原则（必须体现在 UI 上，不是嘴上说说）：
  1. **不由软件替用户决定改什么**：列出每个动作的标题、风险等级、具体改动（before → after），
     用户逐项勾选。高危项默认不勾选。
  2. **执行前二次确认**：弹窗展示完整清单 + 备份说明，用户点“确认执行”才继续。
  3. **演练模式**：提供「先演练」按钮，完整走备份流程但不改系统。
  4. **执行中逐条可见**：每个动作显示 备份→执行→验证 三阶段状态。
  5. **事后可回滚**：报告页与备份页都能一键回到执行前状态。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QVBoxLayout, QWidget,
)

from core.action_ids import ACTIONS, ActionMeta
from core.models import ActionResult, ActionState, ChangePreview, RiskLevel
from app.ui.theme import T, mono_font, ui_font
from app.ui.widgets import Panel
from app.ui.i18n_ui import risk_label


RISK_COLOR = {
    RiskLevel.LOW: T.ACCENT,
    RiskLevel.MEDIUM: T.WARN,
    RiskLevel.HIGH: T.DANGER,
}


def action_meta_safe(action_id: str) -> ActionMeta:
    """取动作元数据。未登记的动作按高风险处理并显式暴露 id，便于定位版本不一致。"""
    meta = ACTIONS.get(action_id)
    if meta is not None:
        return meta
    return ActionMeta(
        action_id=action_id,
        title=f"未知动作（{action_id}）",
        risk=RiskLevel.HIGH,
        description="该动作未在 core/action_ids.py 中登记，可能为版本不一致，请勿执行。",
        default_selected=False,
    )


def localized_meta(meta: ActionMeta) -> ActionMeta:
    """返回标题与说明已按当前语言翻译的副本。

    `core/action_ids.py` 里的 title/description 是中文硬编码（供日志与
    非 UI 场景读取）；UI 展示必须走 t()，否则英文界面会出现中文动作名。
    语言包中每个动作都有 `action.<id>.title` 与 `.description`。
    """
    from core.i18n import t

    title_key = f"action.{meta.action_id}.title"
    desc_key = f"action.{meta.action_id}.description"
    title = t(title_key)
    desc = t(desc_key)
    if title.startswith("\u27e6"):      # 缺 key 时保留原文
        title = meta.title
    if desc.startswith("\u27e6"):
        desc = meta.description
    return ActionMeta(
        action_id=meta.action_id,
        title=title,
        risk=meta.risk,
        description=desc,
        requires_elevation=meta.requires_elevation,
        default_selected=meta.default_selected,
        conflicts_with=meta.conflicts_with,
    )


class ActionRow(QWidget):
    """一个可勾选的修复动作。含风险、说明、改动预览与执行状态。"""

    def __init__(self, meta: ActionMeta, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # 展示用的标题与说明必须已按当前语言翻译；
        # 保留原始 action_id 用于派发，避免翻译后丢失定位能力。
        self.meta = localized_meta(meta)
        self._preview: ChangePreview | None = None
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 9, 10, 9)
        lay.setSpacing(10)

        self.check = QCheckBox()
        self.check.setChecked(meta.default_selected)
        self.check.setToolTip(meta.description)
        lay.addWidget(self.check, 0, Qt.AlignmentFlag.AlignTop)

        body = QVBoxLayout()
        body.setSpacing(3)

        title_row = QHBoxLayout()
        title_row.setSpacing(7)
        self.title = QLabel(meta.title)
        self.title.setFont(ui_font(10, QFont.Weight.DemiBold))
        self.title.setStyleSheet(f"color:{T.TEXT};")
        title_row.addWidget(self.title)

        self.risk = QLabel(risk_label(meta.risk.value))
        c = RISK_COLOR[meta.risk]
        self.risk.setStyleSheet(
            f"color:{c};border:1px solid {c};border-radius:8px;padding:0px 6px;font-size:8pt;"
        )
        self.risk.setFixedHeight(18)
        title_row.addWidget(self.risk)
        title_row.addStretch(1)
        self.state_label = QLabel("")
        self.state_label.setFont(mono_font(8))
        self.state_label.setStyleSheet(f"color:{T.TEXT_FAINT};")
        title_row.addWidget(self.state_label)
        body.addLayout(title_row)

        self.desc = QLabel(meta.description)
        self.desc.setObjectName("Caption")
        self.desc.setWordWrap(True)
        body.addWidget(self.desc)

        self.preview_label = QLabel("")
        self.preview_label.setFont(mono_font(8))
        self.preview_label.setStyleSheet(f"color:{T.CYAN};")
        self.preview_label.setWordWrap(True)
        self.preview_label.setVisible(False)
        body.addWidget(self.preview_label)

        lay.addLayout(body, 1)

    # ---- 状态 ----
    def set_preview(self, p: ChangePreview) -> None:
        self._preview = p
        if not p.before and not p.after:
            self.preview_label.setVisible(False)
            return
        self.preview_label.setText(f"{p.target}：{p.before or '—'}  →  {p.after or '—'}")
        self.preview_label.setVisible(True)

    def set_state(self, action: ActionResult) -> None:
        mapping = {
            ActionState.PENDING: ("待执行", T.TEXT_FAINT),
            ActionState.APPLIED: ("✓ 已生效", T.ACCENT),
            ActionState.SKIPPED: ("已跳过", T.TEXT_DIM),
            ActionState.FAILED: ("✗ 失败", T.DANGER),
            ActionState.ROLLED_BACK: ("已回滚", T.WARN),
            ActionState.ROLLBACK_FAILED: ("回滚失败", T.DANGER),
        }
        text, color = mapping.get(action.state, ("", T.TEXT_FAINT))
        if action.state == ActionState.APPLIED and action.verified is False:
            text, color = "已执行（校验未通过）", T.WARN
        if action.message:
            text = f"{text}｜{action.message}"
        self.state_label.setText(text)
        self.state_label.setStyleSheet(f"color:{color};")
        self.state_label.setToolTip(action.error or action.message)

    def selected(self) -> bool:
        return self.check.isChecked()

    def set_selected(self, on: bool) -> None:
        self.check.setChecked(on)

    def set_enabled_row(self, on: bool) -> None:
        self.check.setEnabled(on)


class RepairPage(QWidget):
    request_execute = Signal(list, bool)    # action_ids, dry_run

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._rows: dict[str, ActionRow] = {}
        self._row_params: dict[str, dict] = {}
        self._build()
        self.state.report_changed.connect(self.on_report)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        head = QHBoxLayout()
        self.sub = QLabel("根据体检结果自动勾选，你可以逐项调整；高危项默认不勾选")
        self.sub.setObjectName("Caption")
        self.sub.setWordWrap(True)
        head.addWidget(self.sub, 1)
        root.addLayout(head)

        # 安全承诺条
        pledge = QLabel(
            "🔒 执行前会自动备份所有将被修改的配置，备份位置与内容完全对本机可见。"
            "任一步骤失败都不会中断其它步骤，且随时可在「备份与回滚」还原到本次执行前。"
        )
        pledge.setWordWrap(True)
        pledge.setStyleSheet(
            f"background:rgba(0,229,160,0.08);border:1px solid rgba(0,229,160,0.3);"
            f"border-radius:9px;padding:10px 13px;color:{T.ACCENT};font-size:9pt;"
        )
        root.addWidget(pledge)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(2, 2, 10, 10)
        self.list_lay.setSpacing(8)
        scroll.setWidget(self.list_host)
        root.addWidget(scroll, 1)

        self.empty_hint = QLabel("先做一次网络体检，系统会在这里列出建议的修复项。")
        self.empty_hint.setObjectName("Caption")
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setMinimumHeight(60)
        self.list_lay.addWidget(self.empty_hint)
        self.list_lay.addStretch(1)

        # 底部执行区
        bar = Panel()
        self.phase_label = QLabel("")
        self.phase_label.setObjectName("Caption")
        self.phase_label.setWordWrap(True)
        bar.body.addWidget(self.phase_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        bar.body.addWidget(self.progress)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.info_label = QLabel("")
        self.info_label.setObjectName("Caption")
        self.info_label.setWordWrap(True)
        row.addWidget(self.info_label, 1)

        self.btn_select_none = QPushButton("全不选")
        self.btn_select_none.setObjectName("Ghost")
        self.btn_select_none.clicked.connect(lambda: self._select_all(False))
        row.addWidget(self.btn_select_none)

        self.btn_select_safe = QPushButton("只选低风险")
        self.btn_select_safe.setObjectName("Ghost")
        self.btn_select_safe.clicked.connect(self._select_safe)
        row.addWidget(self.btn_select_safe)

        self.btn_dry = QPushButton("先演练")
        self.btn_dry.setObjectName("Ghost")
        self.btn_dry.setToolTip("完整走一遍备份与预览流程，但不会修改任何系统设置")
        self.btn_dry.clicked.connect(lambda: self._emit(True))
        row.addWidget(self.btn_dry)

        self.btn_run = QPushButton("执行修复")
        self.btn_run.setObjectName("Primary")
        self.btn_run.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_run.clicked.connect(lambda: self._emit(False))
        row.addWidget(self.btn_run)
        bar.body.addLayout(row)
        root.addWidget(bar)

        self._refresh_info()

    # ------------------------------------------------------------------ #
    def _select_all(self, on: bool) -> None:
        for row in self._rows.values():
            row.set_selected(on)
        self._refresh_info()

    def _select_safe(self) -> None:
        for row in self._rows.values():
            row.set_selected(row.meta.risk is not RiskLevel.HIGH)
        self._refresh_info()

    def selected_ids(self) -> list[str]:
        return [aid for aid, row in self._rows.items() if row.selected()]

    def _refresh_info(self) -> None:
        ids = self.selected_ids()
        if not ids:
            self.info_label.setText("尚未选择任何修复项")
            self.btn_run.setEnabled(False)
            self.btn_dry.setEnabled(False)
            return
        high = [i for i in ids if action_meta_safe(i).risk is RiskLevel.HIGH]
        txt = f"已选 {len(ids)} 项"
        if high:
            txt += f"，其中 {len(high)} 项为高风险"
        self.info_label.setText(txt)
        self.btn_run.setEnabled(True)
        self.btn_dry.setEnabled(True)
        self.btn_run.setText("执行修复" if not high else f"执行修复（含 {len(high)} 项高风险）")

    def _emit(self, dry: bool) -> None:
        ids = self.selected_ids()
        if not ids:
            return
        if not dry and not self._confirm(ids):
            return
        self.request_execute.emit(ids, dry)

    def _confirm(self, ids: list[str]) -> bool:
        """二次确认：把将要做什么、备份到哪、怎么还原，一次讲清。"""
        high = [i for i in ids if action_meta_safe(i).risk is RiskLevel.HIGH]
        lines = [f"即将执行 {len(ids)} 项修复：", ""]
        for i in ids:
            m = action_meta_safe(i)
            lines.append(f"  • [{risk_label(m.risk.value)}] {m.title}")
        lines.append("")
        lines.append(f"执行前会自动创建备份会话（位置：{self.state.store.root}）。")
        if high:
            lines.append("")
            lines.append(f"注意：其中 {len(high)} 项为高风险操作，可能需要重启计算机才能完全生效。")
        lines.append("")
        lines.append("是否继续？")

        box = QMessageBox(self)
        box.setWindowTitle("确认执行修复")
        box.setIcon(QMessageBox.Icon.Warning if high else QMessageBox.Icon.Question)
        box.setText("\n".join(lines))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText("确认执行")
        box.button(QMessageBox.StandardButton.No).setText("取消")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------------ #
    def on_report(self, report) -> None:
        """体检后重建动作列表，默认勾选检测结果建议的动作。"""
        suggested = self.state.suggested_actions()
        self._rebuild(suggested)

    def _rebuild(self, action_ids: list[str], params: dict[str, dict] | None = None) -> None:
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        if not action_ids:
            hint = QLabel("本次体检未发现需要修复的问题，无需执行修复 ✓")
            hint.setStyleSheet(f"color:{T.ACCENT};")
            hint.setWordWrap(True)
            self.list_lay.addWidget(hint)
            self.list_lay.addStretch(1)
            self._refresh_info()
            return

        params = params or {}
        for aid in action_ids:
            row = ActionRow(action_meta_safe(aid))
            row.check.stateChanged.connect(lambda _=0: self._refresh_info())
            self._rows[aid] = row
            self.list_lay.addWidget(row)
        self._row_params = dict(params)
        self.list_lay.addStretch(1)
        self._refresh_info()

    def show_actions(self, action_ids: list[str], params: dict[str, dict] | None = None) -> None:
        """供主窗口在用户点「一键修复」时按体检建议重建列表。"""
        self._rebuild(action_ids, params)

    def set_previews(self, previews: list[ChangePreview]) -> None:
        """把引擎算出的 before/after 回填到对应行。preview.target 形如 "action_id:对象"。"""
        by_id = {p.target.split(":")[0]: p for p in previews}
        for aid, row in self._rows.items():
            p = by_id.get(aid)
            if p is not None:
                row.set_preview(p)

    def set_running(self, running: bool, label: str = "") -> None:
        self.btn_run.setEnabled(not running)
        self.btn_dry.setEnabled(not running)
        self.btn_select_none.setEnabled(not running)
        self.btn_select_safe.setEnabled(not running)
        for row in self._rows.values():
            row.set_enabled_row(not running)
        self.progress.setVisible(running)
        if running:
            self.progress.setValue(0)
        self.phase_label.setText(label)

    def set_progress(self, done: int, total: int, text: str) -> None:
        if total > 0:
            self.progress.setValue(int(done * 100 / total))
        self.phase_label.setText(text)

    def update_result(self, action: ActionResult) -> None:
        row = self._rows.get(action.action_id)
        if row is not None:
            row.set_state(action)


__all__ = ["RepairPage", "ActionRow", "action_meta_safe"]
