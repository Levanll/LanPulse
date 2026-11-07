"""诊断详情页：完整检测项列表 + 单行展开查看证据。

交互设计：表格只显示“结论级”信息（检测项 / 状态 / 说明 / 耗时），
点击任意一行在右侧展开该检测项的指标、建议与原始证据。
普通用户看左表就够，排障的人看右侧证据。
"""
from __future__ import annotations

import html
import json
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QSplitter, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from core.models import CheckResult, DiagnosticReport, Severity
from core.i18n import t
from app.ui.theme import T, mono_font, sev_color, ui_font
from app.ui.widgets import Panel, SeverityBadge
from app.ui.i18n_ui import (
    tr_metric, tr_or_raw, tr_result_advice, tr_result_category,
    tr_result_detail, tr_result_summary, tr_result_title,
)


class DiagnosePage(QWidget):
    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._results: list[CheckResult] = []
        self._build()
        self.state.report_changed.connect(self.on_report)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        head = QHBoxLayout()
        self.meta = QLabel("")
        self.meta.setObjectName("Caption")
        head.addWidget(self.meta)
        head.addStretch(1)
        self.summary_chips = QHBoxLayout()
        self.summary_chips.setSpacing(6)
        head.addLayout(self.summary_chips)
        root.addLayout(head)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        # ---- 左：检测项表格 ----
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([t("diagnose.col_check"), t("diagnose.col_state"),
                                             t("diagnose.col_result"), t("diagnose.col_time")])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 70)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 66)
        self.table.itemSelectionChanged.connect(self._on_select)
        split.addWidget(self.table)

        # ---- 右：详情 ----
        detail_panel = Panel()
        detail_panel.setMinimumWidth(380)
        self.detail_title = QLabel(t("diagnose.pick_one"))
        self.detail_title.setFont(ui_font(11, QFont.Weight.DemiBold))
        self.detail_title.setStyleSheet(f"color:{T.TEXT};")
        self.detail_title.setWordWrap(True)
        detail_panel.body.addWidget(self.detail_title)

        self.detail_badge_row = QHBoxLayout()
        self.detail_badge = SeverityBadge("skip")
        self.detail_badge_row.addWidget(self.detail_badge)
        self.detail_badge_row.addStretch(1)
        detail_panel.body.addLayout(self.detail_badge_row)

        self.detail_view = QTextBrowser()
        self.detail_view.setOpenExternalLinks(False)
        self.detail_view.setStyleSheet(
            f"QTextBrowser{{background:rgba(9,14,23,0.65);border:1px solid {T.LINE_SOFT};"
            f"border-radius:8px;padding:10px;font-size:9.5pt;}}"
        )
        detail_panel.body.addWidget(self.detail_view, 1)
        split.addWidget(detail_panel)
        split.setSizes([620, 440])
        root.addWidget(split, 1)

    # ------------------------------------------------------------------ #
    def on_report(self, report: DiagnosticReport) -> None:
        self._results = report.results
        self._fill_table(report)
        self._fill_chips(report)
        if report.results:
            self.table.selectRow(0)

    def _fill_chips(self, report: DiagnosticReport) -> None:
        while self.summary_chips.count():
            item = self.summary_chips.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        counts = report.by_severity()
        for sev in (Severity.OK, Severity.INFO, Severity.WARN, Severity.CRITICAL, Severity.SKIP):
            n = counts.get(sev.value, 0)
            if n == 0:
                continue
            chip = SeverityBadge(sev.value)
            chip.setToolTip(f"{sev.label} {n} 项")
            lbl = QLabel(f"×{n}")
            lbl.setStyleSheet(f"color:{sev_color(sev.value)};font-size:9pt;")
            self.summary_chips.addWidget(chip)
            self.summary_chips.addWidget(lbl)
        ts = ""
        if report.finished_at:
            ts = time.strftime("%H:%M:%S", time.localtime(report.finished_at))
        self.meta.setText(t("diagnose.meta", n=len(report.results), host=report.host, ts=ts))

    def _fill_table(self, report: DiagnosticReport) -> None:
        self.table.setRowCount(len(report.results))
        for row, r in enumerate(report.results):
            name = QTableWidgetItem(tr_result_title(r))
            name.setFont(ui_font(9.5))
            name.setData(Qt.ItemDataRole.UserRole, row)
            self.table.setItem(row, 0, name)

            self.table.setItem(row, 1, QTableWidgetItem(""))
            self.table.setCellWidget(row, 1, self._badge_cell(r.severity.value))

            summ = QTableWidgetItem(tr_result_summary(r) or "—")
            summ.setForeground(QColor(T.TEXT_DIM))
            self.table.setItem(row, 2, summ)

            dur = QTableWidgetItem(f"{r.duration_ms} ms")
            dur.setFont(mono_font(8))
            dur.setForeground(QColor(T.TEXT_FAINT))
            dur.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, dur)
            self.table.setRowHeight(row, 44)

    @staticmethod
    def _badge_cell(sev: str) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.addWidget(SeverityBadge(sev))
        lay.addStretch(1)
        return w

    # ------------------------------------------------------------------ #
    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if not (0 <= idx < len(self._results)):
            return
        self._show_detail(self._results[idx])

    def _show_detail(self, r: CheckResult) -> None:
        self.detail_title.setText(tr_result_title(r))
        self.detail_badge.set_severity(r.severity.value)
        self.detail_view.setHtml(self._render_html(r))

    def _render_html(self, r: CheckResult) -> str:
        c = sev_color(r.severity.value)
        parts: list[str] = []
        parts.append(
            f"<div style='color:{c};font-weight:600;font-size:10.5pt;margin-bottom:6px'>"
            f"{html.escape(tr_result_summary(r) or '—')}</div>"
        )
        if r.detail:
            parts.append(
                f"<div style='color:{T.TEXT_DIM};white-space:pre-wrap;line-height:1.6'>"
                f"{html.escape(tr_result_detail(r))}</div>"
            )
        if r.metrics:
            parts.append(f"<div style='margin-top:10px;color:{T.TEXT_FAINT};"
                         f"font-size:8.5pt;letter-spacing:1px'>{html.escape(t('diagnose.metrics'))}</div>")
            parts.append("<table width='100%' cellspacing='0' cellpadding='4'>")
            for m in r.metrics:
                col = T.ACCENT if m.ok is True else (T.DANGER if m.ok is False else T.TEXT)
                metric_name, metric_note = tr_metric(m)
                note = (f"<span style='color:{T.TEXT_FAINT}'>{html.escape(metric_note)}</span>"
                        if metric_note else "")
                parts.append(
                    f"<tr><td style='color:{T.TEXT_DIM};width:42%'>{html.escape(tr_metric(m)[0])}</td>"
                    f"<td style='color:{col};font-family:Consolas'>{html.escape(m.value)}"
                    f"&nbsp;&nbsp;{note}</td></tr>"
                )
            parts.append("</table>")
        if r.advice:
            parts.append(f"<div style='margin-top:10px;color:{T.TEXT_FAINT};"
                         f"font-size:8.5pt;letter-spacing:1px'>{html.escape(t('diagnose.advice'))}</div>"
                         f"<ul style='margin:4px 0 0 16px'>")
            for a in tr_result_advice(r):
                parts.append(f"<li style='color:{T.TEXT_DIM};margin-bottom:3px'>"
                             f"{html.escape(a)}</li>")
            parts.append("</ul>")
        if r.evidence:
            raw = json.dumps(r.evidence, ensure_ascii=False, indent=2)
            if len(raw) > 4000:
                raw = raw[:4000] + "\n…（已截断）"
            parts.append(f"<div style='margin-top:10px;color:{T.TEXT_FAINT};"
                         f"font-size:8.5pt;letter-spacing:1px'>{html.escape(t('diagnose.evidence'))}</div>")
            parts.append(
                f"<pre style='background:rgba(0,0,0,0.35);color:{T.TEXT_DIM};"
                f"font-family:Consolas;font-size:8.5pt;padding:8px;border-radius:6px;"
                f"white-space:pre-wrap'>{html.escape(raw)}</pre>"
            )
        if r.error:
            parts.append(f"<div style='margin-top:8px;color:{T.DANGER}'>执行异常："
                         f"{html.escape(r.error[:600])}</div>")
        return "".join(parts)


__all__ = ["DiagnosePage"]
