"""场景选择页 —— 用户旅程的起点。

设计动机：普通用户不知道"我该跑哪几项检测"。他们只知道症状。
这一页把症状翻译成检测计划，是参考项目里最有价值的一个设计。

交互：
  * 6 张卡片，每张一个场景（图标 + 场景名 + 一句话描述 + 检测项数）
  * 点击卡片立即开始对应体检
  * 底部保留"完整体检"作为兜底
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core.i18n import t
from core.scenarios import all_scenarios, get_scenario
from app.ui.theme import T, ui_font
from app.ui.widgets import Card, Panel


class ScenarioCard(QWidget):
    """一张场景卡。"""

    clicked = Signal(str)

    def __init__(self, scenario, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.scenario = scenario
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(104)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(14)

        icon = QLabel(scenario.icon)
        icon.setFixedSize(42, 42)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size:19pt; color:{T.ACCENT};"
            f"background:rgba(0,229,160,0.07); border:1px solid {T.LINE};"
            f"border-radius:11px;"
        )
        lay.addWidget(icon)

        texts = QVBoxLayout()
        texts.setSpacing(3)
        self.title = QLabel(t(scenario.name_key))
        self.title.setFont(ui_font(11, QFont.Weight.DemiBold))
        self.title.setStyleSheet(f"color:{T.TEXT};")
        self.desc = QLabel(t(scenario.desc_key))
        self.desc.setObjectName("Caption")
        self.desc.setWordWrap(True)
        self.count = QLabel(t("scenario.checks_count", n=len(scenario.checks)))
        self.count.setStyleSheet(f"color:{T.TEXT_FAINT}; font-size:8.5pt;")
        texts.addWidget(self.title)
        texts.addWidget(self.desc)
        texts.addWidget(self.count)
        lay.addLayout(texts, 1)

        arrow = QLabel("›")
        arrow.setStyleSheet(f"color:{T.TEXT_FAINT}; font-size:15pt;")
        lay.addWidget(arrow)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.scenario.scenario_id)
        super().mouseReleaseEvent(event)

    def retranslate(self) -> None:
        self.title.setText(t(self.scenario.name_key))
        self.desc.setText(t(self.scenario.desc_key))
        self.count.setText(t("scenario.checks_count", n=len(self.scenario.checks)))


class ScenarioPage(QWidget):
    """场景选择页。"""

    scenario_chosen = Signal(str)

    def __init__(self, state, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._cards: list[ScenarioCard] = []
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        inner = QWidget()
        scroll.setWidget(inner)
        root.addWidget(scroll, 1)

        lay = QVBoxLayout(inner)
        lay.setContentsMargins(2, 2, 10, 10)
        lay.setSpacing(13)

        # 引导语
        self.intro = QLabel("")
        self.intro.setWordWrap(True)
        self.intro.setStyleSheet(
            f"color:{T.TEXT_DIM}; font-size:10pt; padding:2px 0 6px 0;"
        )
        lay.addWidget(self.intro)

        # 场景网格（前 5 个，最后一个是"完整体检"单独放底部）
        grid = QGridLayout()
        grid.setSpacing(11)
        regular = [s for s in all_scenarios() if s.scenario_id != "full"]
        for i, sc in enumerate(regular):
            card = ScenarioCard(sc)
            card.clicked.connect(self.scenario_chosen)
            self._cards.append(card)
            grid.addWidget(card, i // 2, i % 2)
        lay.addLayout(grid)

        # 完整体检单独一条，视觉上区分
        full = get_scenario("full")
        full_card = ScenarioCard(full)
        full_card.clicked.connect(self.scenario_chosen)
        self._cards.append(full_card)
        lay.addWidget(full_card)

        # 高级入口：直接看全部检测项
        adv = Panel()
        row = QHBoxLayout()
        row.setSpacing(10)
        self.adv_label = QLabel("")
        self.adv_label.setObjectName("Caption")
        self.adv_label.setWordWrap(True)
        row.addWidget(self.adv_label, 1)
        self.btn_all = QPushButton("")
        self.btn_all.setObjectName("Ghost")
        self.btn_all.clicked.connect(lambda: self.scenario_chosen.emit("full"))
        row.addWidget(self.btn_all)
        adv.body.addLayout(row)
        lay.addWidget(adv)
        lay.addStretch(1)

        self.retranslate()

    def retranslate(self) -> None:
        self.intro.setText(t("scenario.intro"))
        self.adv_label.setText(t("scenario.advanced_hint"))
        self.btn_all.setText(t("scenario.btn_full"))
        for card in self._cards:
            card.retranslate()


__all__ = ["ScenarioPage", "ScenarioCard"]
