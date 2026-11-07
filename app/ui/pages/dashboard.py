"""仪表盘：软件的默认首页，一眼看到"电脑现在网络怎么样"。

布局（上→下 / 左→右）：
  左侧  健康度环形仪表 + 总体结论 + 两个主按钮（立即体检 / 一键修复）
  右侧  关键指标卡（网卡 / IP / 网关 / DNS / 延迟）与问题清单
  底部  功能入口卡（DNS 优化、HOSTS 管理、备份回滚、诊断报告）
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.i18n import t
from core.models import DiagnosticReport, Severity
from app.ui.theme import T, sev_color, ui_font
from app.ui.widgets import Card, HealthGauge, ModuleCard, Panel, SeverityBadge, kv_row
from app.ui.i18n_ui import tr_metric, tr_result_summary, tr_result_title


class DashboardPage(QWidget):
    request_scan = Signal()
    request_repair = Signal()
    goto_dns = Signal()
    goto_hosts = Signal()
    goto_backup = Signal()
    goto_report = Signal()

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._build()
        self.state.report_changed.connect(self.on_report)

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        lay = QVBoxLayout(inner)
        lay.setContentsMargins(2, 2, 10, 10)
        lay.setSpacing(14)

        # ---------------- 顶部：仪表 + 结论 ----------------
        top = QHBoxLayout()
        top.setSpacing(14)

        left_panel = Panel()
        left_panel.setFixedWidth(292)
        self.gauge = HealthGauge()
        left_panel.body.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignHCenter)
        self.headline = QLabel(t("dashboard.not_scanned"))
        self.headline.setFont(ui_font(11, QFont.Weight.DemiBold))
        self.headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet(f"color:{T.TEXT_DIM};")
        left_panel.body.addWidget(self.headline)

        self.btn_scan = QPushButton(t("btn.scan"))
        self.btn_scan.setObjectName("Primary")
        self.btn_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_scan.clicked.connect(self.request_scan)
        left_panel.body.addWidget(self.btn_scan)

        self.btn_fix = QPushButton(t("btn.one_click_fix"))
        self.btn_fix.setObjectName("Ghost")
        self.btn_fix.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_fix.setToolTip("根据体检结果执行修复；执行前会展示完整改动清单并自动备份")
        self.btn_fix.clicked.connect(self.request_repair)
        self.btn_fix.setEnabled(False)
        left_panel.body.addWidget(self.btn_fix)
        top.addWidget(left_panel)

        # 右侧关键指标
        right = QVBoxLayout()
        right.setSpacing(14)
        self.metrics_card = Card(t("dashboard.metrics_title"), t("dashboard.metrics_desc"))
        self.metrics_body = self.metrics_card.body
        right.addWidget(self.metrics_card)

        self.problems_card = Card(t("dashboard.problems_title"))
        self.problems_card.body.addWidget(self._empty_hint("体检后这里会列出需要处理的项"))
        right.addWidget(self.problems_card, 1)
        top.addLayout(right, 1)
        lay.addLayout(top)

        # ---------------- 功能入口 ----------------
        entry_title = QLabel(t("dashboard.entries_title"))
        entry_title.setObjectName("SectionLabel")
        lay.addWidget(entry_title)

        grid = QGridLayout()
        grid.setSpacing(11)
        entries = [
            (t("dashboard.entry_dns"), t("dashboard.entry_dns_desc"),
             "◈", T.CYAN, self.goto_dns),
            (t("dashboard.entry_hosts"), t("dashboard.entry_hosts_desc"),
             "☰", T.INFO, self.goto_hosts),
            (t("dashboard.entry_backup"), t("dashboard.entry_backup_desc"),
             "⏱", T.WARN, self.goto_backup),
            (t("dashboard.entry_report"), t("dashboard.entry_report_desc"),
             "◧", T.ACCENT, self.goto_report),
        ]
        for i, (title, desc, icon, accent, sig) in enumerate(entries):
            card = ModuleCard(title, desc, icon, accent)
            card.clicked.connect(sig)
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)

        # ---------------- 底部提示 ----------------
        foot = QLabel(
            t("dashboard.footer")
        )
        foot.setObjectName("Caption")
        foot.setWordWrap(True)
        lay.addWidget(foot)
        lay.addStretch(1)

    @staticmethod
    def _empty_hint(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("Caption")
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        lbl.setMinimumHeight(48)
        return lbl

    # ------------------------------------------------------------------ #
    def set_busy(self, busy: bool) -> None:
        self.btn_scan.setEnabled(not busy)
        self.btn_scan.setText(t("dashboard.scanning") if busy else t("btn.scan"))
        if busy:
            self.btn_fix.setEnabled(False)

    # ------------------------------------------------------------------ #
    def on_report(self, report: DiagnosticReport) -> None:
        sev = report.overall
        captions = {
            Severity.OK: t("dashboard.severity_ok"),
            Severity.INFO: t("dashboard.severity_info"),
            Severity.WARN: t("dashboard.severity_warn"),
            Severity.CRITICAL: t("dashboard.severity_critical"),
            Severity.SKIP: t("dashboard.severity_skip"),
        }
        self.gauge.set_result(report.score, captions.get(sev, "—"), sev.value)

        problems = report.problems()
        if not problems:
            self.headline.setText(t("dashboard.all_ok", n=len(report.results)))
            self.headline.setStyleSheet(f"color:{T.ACCENT};")
        else:
            self.headline.setText(t("dashboard.with_problems", n=len(report.results), m=len(problems)))
            self.headline.setStyleSheet(f"color:{sev_color(sev.value)};")

        self.btn_fix.setEnabled(bool(self.state.suggested_actions()))
        self._render_metrics(report)
        self._render_problems(report)

    # ------------------------------------------------------------------ #
    def _render_metrics(self, report: DiagnosticReport) -> None:
        while self.metrics_body.count():
            item = self.metrics_body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.metrics_body.addWidget(kv_row(t("dashboard.hostname"), report.host or "—"))
        self.metrics_body.addWidget(
            kv_row(t("dashboard.privilege"),
                   t("dashboard.elevated_yes") if report.elevated else t("dashboard.elevated_no"),
                   ok=report.elevated)
        )

        # 从检测项里抽取关键指标，保持与检测引擎解耦：只按 check_id 取。
        # adapter 只取链路速率与适配器总数——IP / 网关 / DNS 各有独立检测项，
        # 重复展示会让用户看到两遍同样的值。
        wanted = {"adapter": 2, "dns_server": 2, "connectivity": 2}
        for r in report.results:
            limit = wanted.get(r.check_id)
            if not limit:
                continue
            for m in r.metrics[:limit]:
                name_text, note_text = tr_metric(m)
                self.metrics_body.addWidget(kv_row(name_text, m.value, ok=m.ok))
        self.metrics_body.addStretch(1)

    def _render_problems(self, report: DiagnosticReport) -> None:
        """渲染根因结论。

        为什么不直接列「哪几项异常」：用户看到"网关异常 + DNS 慢 + MTU 不对"
        并不知道该先修哪个、它们是不是同一个原因。根因分析把 N 个异常
        收敛为 1-3 条可执行结论，这才是普通用户需要的东西。
        未被任何规则解释的异常仍单独列出（不臆测原因）。
        """
        while self.problems_card.body.count():
            item = self.problems_card.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        analysis = getattr(self.state, "analysis", None)
        causes = analysis.root_causes if analysis is not None else []

        if not causes and not report.problems():
            lbl = self._empty_hint(t("dashboard.no_problems"))
            lbl.setStyleSheet(f"color:{T.ACCENT};")
            self.problems_card.body.addWidget(lbl)
            self.problems_card.body.addStretch(1)
            return

        # ---- 根因卡片 ----
        for rc in causes[:4]:
            self.problems_card.body.addWidget(self._root_cause_row(rc))

        # ---- 未被解释的异常 ----
        unexplained = analysis.unexplained if analysis is not None else report.problems()
        if unexplained:
            hdr = QLabel(t("dashboard.other_issues", n=len(unexplained)))
            hdr.setStyleSheet(f"color:{T.TEXT_FAINT}; font-size:8.5pt; margin-top:6px;")
            self.problems_card.body.addWidget(hdr)
            for r in unexplained[:3]:
                row = QWidget()
                h = QHBoxLayout(row)
                h.setContentsMargins(0, 2, 0, 2)
                h.setSpacing(9)
                h.addWidget(SeverityBadge(r.severity.value), 0, Qt.AlignmentFlag.AlignTop)
                txt = QVBoxLayout()
                txt.setSpacing(1)
                tt = QLabel(tr_result_title(r))
                tt.setFont(ui_font(9.5))
                tt.setStyleSheet(f"color:{T.TEXT};")
                dd = QLabel(tr_result_summary(r))
                dd.setObjectName("Caption")
                dd.setWordWrap(True)
                txt.addWidget(tt)
                txt.addWidget(dd)
                h.addLayout(txt, 1)
                self.problems_card.body.addWidget(row)

        self.problems_card.body.addStretch(1)

    def _root_cause_row(self, rc) -> QWidget:
        """一条根因：标题 + 置信度 + 影响 + 建议。"""
        from core.rootcause import Confidence

        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 5, 0, 5)
        v.setSpacing(2)

        head = QHBoxLayout()
        head.setSpacing(7)
        title = QLabel(t(rc.title_key))
        title.setFont(ui_font(10, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color:{T.TEXT};")
        title.setWordWrap(True)
        head.addWidget(title, 1)

        conf = QLabel(t("dashboard.confidence",
                        level=t(f"rootcause.confidence.{rc.confidence}")))
        color = {"high": T.DANGER, "medium": T.WARN, "low": T.TEXT_DIM}.get(
            rc.confidence, T.TEXT_DIM)
        conf.setStyleSheet(
            f"color:{color}; border:1px solid {color}; border-radius:8px;"
            f"padding:0 6px; font-size:8pt;"
        )
        conf.setFixedHeight(18)
        head.addWidget(conf, 0, Qt.AlignmentFlag.AlignTop)
        v.addLayout(head)

        impact = QLabel(t(rc.impact_key))
        impact.setObjectName("Caption")
        impact.setWordWrap(True)
        v.addWidget(impact)

        advice = QLabel("→ " + t(rc.advice_key))
        advice.setWordWrap(True)
        advice.setStyleSheet(f"color:{T.CYAN}; font-size:9pt;")
        v.addWidget(advice)

        return wrap


__all__ = ["DashboardPage"]
