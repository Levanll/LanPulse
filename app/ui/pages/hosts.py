"""HOSTS 管理页。

HOSTS 是本软件里“最容易改坏”的文件，所以此页采取**只读优先**的设计：
  * 默认只展示解析后的记录表与风险标注，不进入编辑态；
  * 只有用户主动点「高级编辑」才切换到原始文本编辑，且编辑框上方常驻警告；
  * 无论通过哪种方式保存，都必须先经过一次完整备份（由修复引擎负责）。

这样普通用户不会因为手滑把 hosts 改坏，而排障的人仍然有原始编辑能力。
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit, QPushButton,
    QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core import platform_win as pw
from core.models import DiagnosticReport
from core.i18n import t
from app.ui.theme import T, mono_font, sev_color, ui_font
from app.ui.widgets import Panel, SeverityBadge
from app.ui.i18n_ui import tr_result_summary

# 常见的系统关键域名。若 hosts 把它们指向非常规 IP，基本可判定为劫持。
CRITICAL_DOMAINS = {
    "www.baidu.com", "baidu.com", "www.qq.com", "qq.com", "www.taobao.com",
    "taobao.com", "www.jd.com", "jd.com", "www.weixin.qq.com", "weixin.qq.com",
    "www.bilibili.com", "bilibili.com", "www.zhihu.com", "zhihu.com",
    "update.microsoft.com", "www.microsoft.com", "login.microsoftonline.com",
    "www.apple.com", "www.icloud.com", "www.google.com", "github.com",
    "www.12306.cn", "www.alipay.com", "www.douyin.com",
}


def classify_hosts(text: str) -> list[dict]:
    """把 hosts 文本解析成结构化记录，并标注风险等级。

    纯函数、无副作用，便于测试与复用。风险分级：
      normal      普通映射
      blocked     指向 0.0.0.0 / 127.0.0.1 / ::1 的非 localhost 记录（屏蔽广告或破解补丁）
      hijacked    关键域名被指向非常规地址（高危，可能是劫持）
    """
    records: list[dict] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body = stripped.split("#", 1)[0].strip()
        parts = body.split()
        if len(parts) < 2:
            continue
        ip = parts[0]
        domains = parts[1:]
        sink = ip in ("0.0.0.0", "127.0.0.1", "::1", "::", "255.255.255.255")
        risk = "normal"
        note = ""
        if sink and not all(d.lower() in ("localhost", "localhost.localdomain") for d in domains):
            risk = "blocked"
            note = "屏蔽该域名（广告过滤或破解补丁常见做法）"
        hit = [d for d in domains if d.lower() in CRITICAL_DOMAINS]
        if hit:
            risk = "hijacked"
            note = (f"关键域名（{', '.join(hit[:2])}）被指向 {ip}，"
                    f"{'会被屏蔽' if sink else '可能被劫持'}")
        records.append({
            "line": lineno, "ip": ip, "domains": domains, "raw": raw,
            "risk": risk, "note": note,
        })
    return records


class HostsPage(QWidget):
    request_clean = Signal()
    request_restore = Signal()
    request_save_text = Signal(str)

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._records: list[dict] = []
        self._raw = ""
        self._edit_mode = False
        self._build()
        self.state.report_changed.connect(self.on_report)
        self.reload()

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        head = QHBoxLayout()
        self.path_label = QLabel(pw.HOSTS_PATH)
        self.path_label.setFont(mono_font(8))
        self.path_label.setStyleSheet(f"color:{T.TEXT_FAINT};")
        head.addWidget(self.path_label)
        head.addStretch(1)

        self.btn_reload = QPushButton(t("btn.reload"))
        self.btn_reload.setObjectName("Ghost")
        self.btn_reload.clicked.connect(self.reload)
        head.addWidget(self.btn_reload)

        self.btn_edit = QPushButton(t("btn.advanced_edit"))
        self.btn_edit.setObjectName("Ghost")
        self.btn_edit.setCheckable(True)
        self.btn_edit.toggled.connect(self._toggle_edit)
        head.addWidget(self.btn_edit)
        root.addLayout(head)

        # ---- 状态条 ----
        self.status_row = QHBoxLayout()
        self.status_row.setSpacing(8)
        self.sev_badge = SeverityBadge("skip")
        self.status_row.addWidget(self.sev_badge)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Caption")
        self.status_label.setWordWrap(True)
        self.status_row.addWidget(self.status_label, 1)
        root.addLayout(self.status_row)

        # ---- 主体 ----
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.setChildrenCollapsible(False)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["行", "IP 地址", "域名", "判定"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setShowGrid(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 52)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.splitter.addWidget(self.table)

        # 编辑器（默认隐藏）
        editor_panel = Panel()
        warn = QLabel(
            "⚠ 直接编辑 HOSTS 存在风险：错误内容可能导致部分网站无法访问。"
            "保存前会自动备份当前文件，可在「备份与回滚」中还原。"
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color:{T.WARN};font-size:9pt;")
        editor_panel.body.addWidget(warn)
        self.editor = QPlainTextEdit()
        self.editor.setObjectName("Editor")
        editor_panel.body.addWidget(self.editor, 1)
        erow = QHBoxLayout()
        erow.addStretch(1)
        self.btn_cancel_edit = QPushButton(t("btn.discard"))
        self.btn_cancel_edit.setObjectName("Ghost")
        self.btn_cancel_edit.clicked.connect(lambda: self._toggle_edit(False))
        erow.addWidget(self.btn_cancel_edit)
        self.btn_save = QPushButton(t("btn.save_hosts"))
        self.btn_save.setObjectName("Primary")
        self.btn_save.clicked.connect(self._emit_save)
        erow.addWidget(self.btn_save)
        editor_panel.body.addLayout(erow)
        editor_panel.setVisible(False)
        self.editor_panel = editor_panel
        self.splitter.addWidget(editor_panel)
        root.addWidget(self.splitter, 1)

        # ---- 底部操作 ----
        bar = Panel()
        brow = QHBoxLayout()
        brow.setSpacing(10)
        tip = QLabel(
            "清理只移除「屏蔽」与「劫持」两类记录，其余行原样保留；"
            "恢复默认会把整个文件替换为系统模板，自定义记录将全部丢失。"
        )
        tip.setObjectName("Caption")
        tip.setWordWrap(True)
        brow.addWidget(tip, 1)
        self.btn_clean = QPushButton(t("btn.clean_hosts"))
        self.btn_clean.setObjectName("Ghost")
        self.btn_clean.clicked.connect(self.request_clean)
        brow.addWidget(self.btn_clean)
        self.btn_restore = QPushButton(t("btn.restore_hosts"))
        self.btn_restore.setObjectName("Danger")
        self.btn_restore.clicked.connect(self.request_restore)
        brow.addWidget(self.btn_restore)
        bar.body.addLayout(brow)
        root.addWidget(bar)

    # ------------------------------------------------------------------ #
    def reload(self) -> None:
        try:
            self._raw = pw.read_text_file(pw.HOSTS_PATH)
        except OSError as exc:
            self._raw = ""
            self.sev_badge.set_severity("critical")
            self.status_label.setText(f"无法读取 HOSTS 文件：{exc}")
            self.status_label.setStyleSheet(f"color:{T.DANGER};")
            self.table.setRowCount(0)
            return
        self.editor.setPlainText(self._raw)
        self._render(self._raw)

    def _render(self, text: str) -> None:
        self._records = classify_hosts(text)
        blocked = [r for r in self._records if r["risk"] == "blocked"]
        hijacked = [r for r in self._records if r["risk"] == "hijacked"]

        if hijacked:
            sev = "critical"
        elif blocked:
            sev = "warn"
        else:
            sev = "ok"
        self.sev_badge.set_severity(sev)

        total = len(self._records)
        if sev == "ok":
            msg = f"文件正常：{total} 条有效映射，未发现可疑记录。"
            self.status_label.setStyleSheet(f"color:{T.ACCENT};")
        elif sev == "warn":
            msg = (f"{total} 条有效映射，其中 {len(blocked)} 条为屏蔽记录"
                   f"（常见于广告过滤 / 破解补丁），若对应网站打不开可清理。")
            self.status_label.setStyleSheet(f"color:{T.WARN};")
        else:
            msg = (f"发现 {len(hijacked)} 条疑似劫持记录，{len(blocked)} 条屏蔽记录，"
                   f"建议立即清理并全盘杀毒。")
            self.status_label.setStyleSheet(f"color:{T.DANGER};")
        self.status_label.setText(msg)

        self.table.setRowCount(len(self._records))
        for row, rec in enumerate(self._records):
            no = QTableWidgetItem(str(rec["line"]))
            no.setFont(mono_font(8))
            no.setForeground(QColor(T.TEXT_FAINT))
            self.table.setItem(row, 0, no)

            ip = QTableWidgetItem(rec["ip"])
            ip.setFont(mono_font(9))
            ip.setForeground(QColor(T.TEXT))
            self.table.setItem(row, 1, ip)

            dom = QTableWidgetItem("  ".join(rec["domains"]))
            color = sev_color("critical" if rec["risk"] == "hijacked"
                              else ("warn" if rec["risk"] == "blocked" else "ok"))
            dom.setForeground(QColor(color if rec["risk"] != "normal" else T.TEXT))
            self.table.setItem(row, 2, dom)

            label = {"normal": "正常", "blocked": "屏蔽", "hijacked": "疑似劫持"}[rec["risk"]]
            judge = QTableWidgetItem(label + (f"｜{rec['note']}" if rec["note"] else ""))
            judge.setForeground(QColor(color))
            self.table.setItem(row, 3, judge)
            self.table.setRowHeight(row, 32)

        abnormal = len(blocked) + len(hijacked)
        self.btn_clean.setEnabled(abnormal > 0)
        self.btn_clean.setText(f"清理异常记录（{abnormal}）" if abnormal else "清理异常记录")

        # 空文件时表格区会是一大片空白，补一行说明，避免用户以为界面坏了
        if not self._records:
            from PySide6.QtWidgets import QTableWidgetItem as _Item

            self.table.setRowCount(1)
            hint = _Item("此 HOSTS 文件没有任何自定义映射（仅含注释与空行），"
                         "这通常是正常的默认状态。")
            hint.setForeground(QColor(T.TEXT_FAINT))
            self.table.setItem(0, 0, hint)
            self.table.setSpan(0, 0, 1, 4)
            self.table.setRowHeight(0, 44)

    # ------------------------------------------------------------------ #
    def on_report(self, report: DiagnosticReport) -> None:
        # 体检结果可能比本地解析更权威（例如文件被外部占用），错误时优先展示它
        result = next((r for r in report.results if r.check_id == "hosts"), None)
        if result is not None and result.error:
            self.sev_badge.set_severity(result.severity.value)
            self.status_label.setText(tr_result_summary(result))
            self.status_label.setStyleSheet(f"color:{sev_color(result.severity.value)};")

    def _toggle_edit(self, on: bool) -> None:
        self._edit_mode = on
        self.editor_panel.setVisible(on)
        self.btn_edit.setText(t("btn.exit_edit") if on else "高级编辑")
        self.btn_save.setEnabled(on)
        self.btn_reload.setEnabled(not on)
        if on:
            self.editor.setPlainText(self._raw)
            self.splitter.setSizes([240, 380])
        else:
            self.splitter.setSizes([600, 0])

    def _emit_save(self) -> None:
        text = self.editor.toPlainText()
        if text == self._raw:
            self.status_label.setText(t("hosts.no_change"))
            return
        self.request_save_text.emit(text)


__all__ = ["HostsPage", "classify_hosts", "CRITICAL_DOMAINS"]
