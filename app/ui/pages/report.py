"""诊断报告页：导出 + 审计流水。

把"软件对我电脑做了什么"变成可带走、可核对的证据链：
  * 上半区：导出本机体检报告（HTML / JSON / TXT）；
  * 下半区：操作审计流水（每次修复、回滚都有一条），支持按类型过滤。
"""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from core.models import DiagnosticReport
from app.logging_setup import read_audit
from core.i18n import t
from app.ui.theme import T, mono_font, ui_font
from app.ui.widgets import Card, Panel


class ReportPage(QWidget):
    request_export = Signal(str)        # fmt: html / json / text

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._audit: list[dict] = []
        self._build()
        self.state.report_changed.connect(self.on_report)
        self.refresh_audit()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        head = QHBoxLayout()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("Caption")
        self.summary_label.setWordWrap(True)
        head.addWidget(self.summary_label, 1)
        root.addLayout(head)

        # ---- 报告导出 ----
        card = Card(t("report.export_title"),
                    "报告仅包含本机网络配置与检测结论，不含任何个人数据，可安全分享给维修人员")
        self.report_summary = QLabel(t("dashboard.not_scanned"))
        self.report_summary.setObjectName("Caption")
        self.report_summary.setWordWrap(True)
        card.body.addWidget(self.report_summary)

        btns = QHBoxLayout()
        btns.setSpacing(9)
        for fmt, label, tip in (
            ("html", t("btn.export_html"), "单文件网页，含完整证据，适合发给他人"),
            ("json", t("btn.export_json"), "结构化数据，适合程序处理或存档"),
            ("text", t("btn.export_text"), "纯文本，适合粘贴进工单"),
        ):
            b = QPushButton(label)
            b.setObjectName("Ghost")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, f=fmt: self.request_export.emit(f))
            btns.addWidget(b)
        btns.addStretch(1)
        card.body.addLayout(btns)
        root.addWidget(card)

        # ---- 审计流水 ----
        audit_card = Panel()
        top = QHBoxLayout()
        title = QLabel(t("report.audit_title"))
        title.setFont(ui_font(11, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color:{T.TEXT};")
        top.addWidget(title)
        self.audit_count = QLabel("")
        self.audit_count.setObjectName("Caption")
        top.addWidget(self.audit_count)
        top.addStretch(1)

        self.filter = QComboBox()
        self.filter.addItems(["全部事件", "修复执行", "回滚", "备份"])
        self.filter.currentIndexChanged.connect(self._apply_filter)
        top.addWidget(self.filter)

        self.btn_refresh = QPushButton(t("btn.refresh"))
        self.btn_refresh.setObjectName("Ghost")
        self.btn_refresh.clicked.connect(self.refresh_audit)
        top.addWidget(self.btn_refresh)
        audit_card.body.addLayout(top)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["时间", "事件", "操作", "结果"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_audit_select)
        audit_card.body.addWidget(self.table, 1)

        self.audit_detail = QTextBrowser()
        self.audit_detail.setMaximumHeight(150)
        self.audit_detail.setStyleSheet(
            f"QTextBrowser{{background:rgba(9,14,23,0.65);border:1px solid {T.LINE_SOFT};"
            f"border-radius:8px;padding:8px;font-size:9pt;}}"
        )
        audit_card.body.addWidget(self.audit_detail)
        root.addWidget(audit_card, 1)

    # ------------------------------------------------------------------ #
    def on_report(self, report: DiagnosticReport) -> None:
        problems = len(report.problems())
        ts = time.strftime("%Y-%m-%d %H:%M:%S",
                           time.localtime(report.finished_at or report.started_at))
        self.report_summary.setText(
            f"最近一次体检：{ts}｜主机 {report.host}｜共 {len(report.results)} 项检测｜"
            f"健康分 {report.score}｜发现 {problems} 个问题"
            + ("" if report.elevated else "｜以普通权限运行，部分项目未检测")
        )

    def refresh_audit(self) -> None:
        self._audit = read_audit(300)
        self._apply_filter()

    def _apply_filter(self) -> None:
        mode = self.filter.currentText()
        data = self._audit
        if mode == "修复执行":
            data = [r for r in data if r.get("event") in ("repair", "action")]
        elif mode == "回滚":
            data = [r for r in data if r.get("event") == "rollback"]
        elif mode == "备份":
            data = [r for r in data if r.get("event") in ("backup", "hosts_edit")]

        self.table.setRowCount(len(data))
        self.audit_count.setText(f"｜{len(data)} 条记录")
        for row, rec in enumerate(data):
            it = QTableWidgetItem(str(rec.get("ts_text", ""))[5:])
            it.setFont(mono_font(8))
            it.setData(Qt.ItemDataRole.UserRole, rec)
            self.table.setItem(row, 0, it)

            ev = QTableWidgetItem(str(rec.get("event", "")))
            ev.setForeground(QColor(T.CYAN))
            self.table.setItem(row, 1, ev)

            desc = rec.get("target") or rec.get("detail") or rec.get("action_id", "")
            self.table.setItem(row, 2, QTableWidgetItem(str(desc)[:120]))

            ok = rec.get("ok")
            label = "成功" if ok is True else ("失败" if ok is False else "—")
            res = QTableWidgetItem(label)
            res.setForeground(QColor(T.ACCENT if ok is True
                                     else (T.DANGER if ok is False else T.TEXT_FAINT)))
            self.table.setItem(row, 3, res)
            self.table.setRowHeight(row, 28)

    def _on_audit_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return
        rec = item.data(Qt.ItemDataRole.UserRole)
        if not rec:
            return
        self.audit_detail.setPlainText(json.dumps(rec, ensure_ascii=False, indent=2))


__all__ = ["ReportPage"]
