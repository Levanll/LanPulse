"""DNS 优化中心 —— 独立的功能入口页。

普通用户最常遇到的“网页打不开但 QQ 能上”几乎都是 DNS 问题，所以 DNS 单独成页：
  * 上半区：当前 DNS 服务器列表（含归属识别）
  * 下半区：推荐方案卡片（公共 DNS / 自动获取），每张卡显示适用场景与风险
  * 底部：执行按钮（走统一的备份-修改-验证-回滚通道）
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core import platform_win as pw
from core.models import DiagnosticReport
from app.ui.theme import T, mono_font
from app.ui.widgets import Card, Panel, SeverityBadge, kv_row
from app.ui.i18n_ui import tr_result_advice, tr_result_summary

# 已知公共 DNS 归属表。用于把裸 IP 变成普通用户能理解的“这是谁的服务器”。
DNS_VENDORS = {
    "223.5.5.5": "阿里云公共 DNS",
    "223.6.6.6": "阿里云公共 DNS",
    "119.29.29.29": "腾讯 DNSPod",
    "182.254.116.116": "腾讯 DNSPod",
    "114.114.114.114": "114DNS",
    "114.114.115.115": "114DNS",
    "180.76.76.76": "百度 DNS",
    "8.8.8.8": "Google Public DNS",
    "8.8.4.4": "Google Public DNS",
    "1.1.1.1": "Cloudflare",
    "1.0.0.1": "Cloudflare",
    "9.9.9.9": "Quad9",
    "208.67.222.222": "OpenDNS",
    "101.226.4.6": "中国电信 DNS",
    "180.184.1.1": "字节跳动 DNS",
    "210.2.4.8": "中国移动 DNS",
}

DNS_PLANS = [
    {
        "id": "ali_tencent",
        "name": "阿里 + 腾讯",
        "servers": ["223.5.5.5", "119.29.29.29"],
        "tag": "推荐 · 国内最快",
        "desc": "国内 CDN 解析最准，延迟低，不会被解析到海外节点。适合绝大多数家庭宽带。",
        "accent": T.ACCENT,
    },
    {
        "id": "dns114",
        "name": "114 DNS",
        "servers": ["114.114.114.114", "114.114.115.115"],
        "tag": "稳定 · 老牌",
        "desc": "运营商级 DNS，覆盖广、可用性非常稳定，抗污染能力一般。",
        "accent": T.INFO,
    },
    {
        "id": "overseas",
        "name": "Cloudflare + Google",
        "servers": ["1.1.1.1", "8.8.8.8"],
        "tag": "境外 · 需谨慎",
        "desc": "隐私保护最好，但国内解析可能被调度到海外节点，实际访问反而变慢。",
        "accent": T.WARN,
    },
    {
        "id": "dhcp",
        "name": "自动获取（路由器下发）",
        "servers": [],
        "tag": "回退方案",
        "desc": "恢复为由路由器 / DHCP 自动分配。接入公司、校园网或使用运营商 DNS 时选这个。",
        "accent": T.TEXT_DIM,
    },
]


class DnsPage(QWidget):
    request_apply_plan = Signal(str, list)   # plan_id, servers

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._current: list[str] = []
        self._selected_plan = "ali_tencent"
        self._plan_cards: dict[str, QWidget] = {}
        self._build()
        self.state.report_changed.connect(self.on_report)

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        head = QHBoxLayout()
        sub = QLabel("域名解析服务决定你访问网站走哪条路，是“网页打不开”的首要排查点")
        sub.setObjectName("Caption")
        sub.setWordWrap(True)
        head.addWidget(sub, 1)
        root.addLayout(head)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(2, 2, 10, 10)
        lay.setSpacing(13)

        # ---------------- 当前配置 ----------------
        self.cur_card = Card("当前 DNS 配置", "读取自当前承载上网流量的网卡")
        self.cur_body = self.cur_card.body
        self.cur_body.addWidget(self._hint("体检后显示当前 DNS 服务器"))
        lay.addWidget(self.cur_card)

        # ---------------- 推荐方案 ----------------
        plan_label = QLabel("选择方案")
        plan_label.setObjectName("SectionLabel")
        lay.addWidget(plan_label)

        grid = QGridLayout()
        grid.setSpacing(11)
        for i, plan in enumerate(DNS_PLANS):
            card = self._make_plan_card(plan)
            self._plan_cards[plan["id"]] = card
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)

        # ---------------- 执行条 ----------------
        action_bar = Panel()
        row = QHBoxLayout()
        row.setSpacing(12)
        self.plan_hint = QLabel("")
        self.plan_hint.setObjectName("Caption")
        self.plan_hint.setWordWrap(True)
        row.addWidget(self.plan_hint, 1)
        self.btn_apply = QPushButton("应用所选方案")
        self.btn_apply.setObjectName("Primary")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self._emit_apply)
        row.addWidget(self.btn_apply)
        action_bar.body.addLayout(row)
        lay.addWidget(action_bar)
        lay.addStretch(1)

        self._mark_selection()
        self._refresh_plan_hint()

    def _hint(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("Caption")
        lbl.setWordWrap(True)
        return lbl

    def _make_plan_card(self, plan: dict) -> QWidget:
        card = Card(f"{plan['name']}    {plan['tag']}", "")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.body.addWidget(self._hint(plan["desc"]))
        if plan["servers"]:
            srv = QLabel("  ".join(plan["servers"]))
            srv.setFont(mono_font(9))
            srv.setStyleSheet(f"color:{plan['accent']};")
            card.body.addWidget(srv)
        else:
            lbl = self._hint("由路由器 / DHCP 服务器自动下发")
            lbl.setStyleSheet(f"color:{plan['accent']};")
            card.body.addWidget(lbl)
        card.mouseReleaseEvent = lambda ev, pid=plan["id"]: self._select_plan(pid)  # type: ignore[method-assign]
        return card

    def _select_plan(self, plan_id: str) -> None:
        if self._selected_plan == plan_id:
            return
        self._selected_plan = plan_id
        self._mark_selection()
        self._refresh_plan_hint()

    def _mark_selection(self) -> None:
        for pid, card in self._plan_cards.items():
            sel = pid == self._selected_plan
            color = T.ACCENT if sel else T.LINE
            card.setStyleSheet(
                f"#Card{{background: rgba(18,26,42,0.9);"
                f"border:1px solid {color};border-radius:10px;}}"
            )

    def _refresh_plan_hint(self) -> None:
        plan = next(p for p in DNS_PLANS if p["id"] == self._selected_plan)
        if plan["servers"]:
            self.plan_hint.setText(
                f"将把当前上网网卡的 DNS 改为 {' / '.join(plan['servers'])}。"
                f"修改前会自动备份原配置，可在「备份与回滚」中还原。"
            )
            self.btn_apply.setText("应用所选方案")
        else:
            self.plan_hint.setText("将把 DNS 恢复为由 DHCP 自动下发。修改前会自动备份原配置。")
            self.btn_apply.setText("恢复自动获取")

    def _emit_apply(self) -> None:
        plan = next(p for p in DNS_PLANS if p["id"] == self._selected_plan)
        self.request_apply_plan.emit(plan["id"], list(plan["servers"]))

    # ------------------------------------------------------------------ #
    def on_report(self, report: DiagnosticReport) -> None:
        result = next((r for r in report.results if r.check_id == "dns_server"), None)
        while self.cur_body.count():
            item = self.cur_body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if result is None:
            self.cur_body.addWidget(self._hint("本次体检未包含 DNS 检测项"))
            return

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(SeverityBadge(result.severity.value))
        msg = QLabel(tr_result_summary(result))
        msg.setWordWrap(True)
        msg.setStyleSheet(f"color:{T.TEXT};")
        row.addWidget(msg, 1)
        holder = QWidget()
        holder.setLayout(row)
        self.cur_body.addWidget(holder)

        evidence = result.evidence or {}
        servers = evidence.get("servers") or []
        self._current = [str(s) for s in servers if pw.is_valid_ipv4(str(s))]
        if self._current:
            for ip in self._current:
                vendor = DNS_VENDORS.get(ip, "自定义 / 运营商")
                self.cur_body.addWidget(kv_row(ip, vendor, ok=(ip in DNS_VENDORS)))
        else:
            self.cur_body.addWidget(kv_row("DNS 服务器", "未配置或自动获取"))

        iface = evidence.get("interface") or evidence.get("interface_alias") or ""
        if iface:
            self.cur_body.addWidget(kv_row("作用网卡", str(iface)))
        for advice in tr_result_advice(result)[:3]:
            self.cur_body.addWidget(self._hint(f"· {advice}"))


__all__ = ["DnsPage", "DNS_VENDORS", "DNS_PLANS"]
