"""备份与回滚页。

这一页是整个软件“可信度”的证据：用户能在这里看到软件到底改过什么、
备份在哪、以及一键还原。因此它刻意做得像“系统还原点管理器”而不是设置页。
"""
from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from core.backup import BackupSession
from app.ui.theme import T, mono_font, ui_font
from app.ui.widgets import Panel


class BackupPage(QWidget):
    request_rollback = Signal(str)      # session_id
    request_create = Signal()           # 手工创建备份

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._sessions: list[BackupSession] = []
        self._build()
        self.state.backups_changed.connect(self.refresh)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        head = QHBoxLayout()
        self.count_label = QLabel("")
        self.count_label.setObjectName("Caption")
        head.addWidget(self.count_label)
        head.addStretch(1)

        self.btn_open = QPushButton("打开备份目录")
        self.btn_open.setObjectName("Ghost")
        self.btn_open.clicked.connect(self._open_dir)
        head.addWidget(self.btn_open)

        self.btn_new = QPushButton("手动创建备份")
        self.btn_new.setObjectName("Ghost")
        self.btn_new.setToolTip("在修改任何设置前，先手动存一份当前网络配置快照")
        self.btn_new.clicked.connect(self.request_create)
        head.addWidget(self.btn_new)
        root.addLayout(head)

        split = QHBoxLayout()
        split.setSpacing(12)

        # ---- 左：会话列表 ----
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["时间", "类型", "内容"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self._on_select)
        split.addWidget(self.table, 3)

        # ---- 右：详情 ----
        panel = Panel()
        panel.setMinimumWidth(330)
        panel.body.addWidget(self._title("选择左侧备份查看详情"))
        self.detail = QTextBrowser()
        self.detail.setStyleSheet(
            f"QTextBrowser{{background:rgba(9,14,23,0.65);border:1px solid {T.LINE_SOFT};"
            f"border-radius:8px;padding:10px;font-size:9.5pt;}}"
        )
        panel.body.addWidget(self.detail, 1)

        self.btn_rollback = QPushButton("恢复到此次备份状态")
        self.btn_rollback.setObjectName("Primary")
        self.btn_rollback.setEnabled(False)
        self.btn_rollback.clicked.connect(self._do_rollback)
        panel.body.addWidget(self.btn_rollback)

        warn = QLabel("回滚只会还原备份中记录的项目，不会影响备份之后你对系统做的其它修改。")
        warn.setObjectName("Caption")
        warn.setWordWrap(True)
        panel.body.addWidget(warn)
        split.addWidget(panel, 2)
        root.addLayout(split, 1)

        self.refresh()

    @staticmethod
    def _title(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(ui_font(10.5, QFont.Weight.DemiBold))
        lbl.setStyleSheet(f"color:{T.TEXT};")
        lbl.setWordWrap(True)
        return lbl

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        self._sessions = self.state.store.list_sessions()
        self.table.setRowCount(len(self._sessions))
        self.count_label.setText(f"共 {len(self._sessions)} 个备份会话")
        restorable = {i for i, s in enumerate(self._sessions) if s.items}

        for row, s in enumerate(self._sessions):
            ts = time.strftime("%m-%d %H:%M:%S", time.localtime(s.created_at))
            it = QTableWidgetItem(ts)
            it.setFont(mono_font(8.5))
            self.table.setItem(row, 0, it)

            kind = QTableWidgetItem(s.kind + ("（已还原）" if s.restored_at else ""))
            kind.setForeground(QColor(T.WARN if s.restored_at else T.TEXT_DIM))
            self.table.setItem(row, 1, kind)

            summary = s.note or "、".join(sorted({i.label for i in s.items})) or "（无持久化状态变更）"
            cell = QTableWidgetItem(summary[:90])
            if row not in restorable:
                cell.setToolTip("该会话未记录可恢复的状态，仅作为操作审计留痕")
                cell.setForeground(QColor(T.TEXT_FAINT))
            self.table.setItem(row, 2, cell)
            self.table.setRowHeight(row, 34)

        if not self._sessions:
            self.detail.setHtml(
                f"<p style='color:{T.TEXT_FAINT}'>还没有任何备份。</p>"
                f"<p style='color:{T.TEXT_DIM}'>每次执行修复前系统会自动创建备份；"
                f"你也可以点右上角「手动创建备份」先存一份当前网络配置快照。</p>"
            )
            self.btn_rollback.setEnabled(False)
        else:
            # 默认选中最新一条，避免右侧详情区一片空白
            self.table.selectRow(0)

    def _current_session(self) -> BackupSession | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        idx = rows[0].row()
        if 0 <= idx < len(self._sessions):
            return self._sessions[idx]
        return None

    def _on_select(self) -> None:
        s = self._current_session()
        if s is None:
            return
        self._show(s)
        has_state = bool(s.items)
        self.btn_rollback.setEnabled(has_state)
        if has_state:
            self.btn_rollback.setText(
                f"恢复到 {time.strftime('%m-%d %H:%M', time.localtime(s.created_at))} 的状态"
            )
        else:
            self.btn_rollback.setText("该备份无可恢复内容")

    def _show(self, s: BackupSession) -> None:
        parts = [
            f"<div style='color:{T.TEXT};font-weight:600;font-size:10.5pt'>{s.kind}</div>",
            f"<div style='color:{T.TEXT_FAINT};font-family:Consolas;font-size:8.5pt;"
            f"margin:4px 0 8px'>{s.session_id}</div>",
        ]
        if s.note:
            parts.append(f"<div style='color:{T.TEXT_DIM};margin-bottom:8px'>{s.note}</div>")
        parts.append(
            "<table width='100%' cellpadding='3'>"
            f"<tr><td style='color:{T.TEXT_DIM}'>创建时间</td>"
            f"<td style='font-family:Consolas'>"
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(s.created_at))}</td></tr>"
            f"<tr><td style='color:{T.TEXT_DIM}'>主机</td>"
            f"<td style='font-family:Consolas'>{s.host}</td></tr>"
            f"<tr><td style='color:{T.TEXT_DIM}'>备份时权限</td>"
            f"<td>{'管理员' if s.elevated else '普通用户'}</td></tr>"
            "</table>"
        )
        if s.restored_at:
            parts.append(
                f"<div style='color:{T.WARN};margin-top:8px'>已于 "
                f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(s.restored_at))} 还原过一次</div>"
            )
        parts.append(
            f"<div style='color:{T.TEXT_FAINT};margin-top:10px;font-size:8.5pt;"
            f"letter-spacing:1px'>备份内容（{len(s.items)} 项）</div>"
        )
        if s.items:
            parts.append("<ul style='margin:4px 0 0 16px'>")
            for item in s.items:
                parts.append(f"<li style='color:{T.TEXT_DIM};margin-bottom:2px'>{item.label}</li>")
            parts.append("</ul>")
        else:
            parts.append(
                f"<div style='color:{T.TEXT_DIM};margin-top:4px'>"
                f"本次操作不涉及持久化配置，仅记录审计留痕。</div>"
            )
        parts.append(
            f"<div style='color:{T.TEXT_FAINT};margin-top:10px;font-size:8.5pt;"
            f"word-break:break-all'>目录：{s.path}</div>"
        )
        self.detail.setHtml("".join(parts))

    # ------------------------------------------------------------------ #
    def _do_rollback(self) -> None:
        s = self._current_session()
        if s is None or not s.items:
            return
        box = QMessageBox(self)
        box.setWindowTitle("确认回滚")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            f"将把以下 {len(s.items)} 项配置恢复到 "
            f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(s.created_at))} 的状态：\n\n"
            + "\n".join(f"  • {i.label}" for i in s.items[:10])
            + ("\n  …" if len(s.items) > 10 else "")
            + "\n\n回滚过程中网络可能短暂中断。是否继续？"
        )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText("确认回滚")
        box.button(QMessageBox.StandardButton.No).setText("取消")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self.request_rollback.emit(s.session_id)

    def _open_dir(self) -> None:
        path = self.state.store.root
        try:
            os.startfile(path)  # noqa: S606 - 用户显式点击打开本机目录
        except OSError as exc:
            QMessageBox.warning(self, "无法打开目录", f"{path}\n\n{exc}")


__all__ = ["BackupPage"]
