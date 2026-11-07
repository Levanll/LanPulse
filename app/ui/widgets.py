"""自定义绘制控件：健康度环形仪表、严重度徽章、迷你曲线、卡片容器。

为什么不用第三方 UI 库：整个项目只依赖 PySide6，所有“科技感”来自 QPainter 自绘
（渐变弧、发光环、等宽数字），这样打包体积可控、无授权风险、缩放不糊。
"""
from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import (
    QEasingCurve, QPropertyAnimation, QRectF, Qt, Property, QTimer, Signal,
)
from PySide6.QtGui import (
    QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath,
    QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from app.ui.theme import T, mono_font, sev_color, ui_font


# --------------------------------------------------------------------------- #
# 健康度环形仪表
# --------------------------------------------------------------------------- #
class HealthGauge(QWidget):
    """0-100 分的环形仪表。分数字段用动画过渡，避免体检完突变造成的突兀感。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._score = 0.0
        self._target = 0.0
        self._caption = "等待检测"
        self._sev = "skip"
        self.setMinimumSize(210, 210)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._anim = QPropertyAnimation(self, b"score", self)
        self._anim.setDuration(900)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._pulse = 0.0
        self._pulse_dir = 1
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick_pulse)
        self._pulse_timer.start(40)

    # ---- score property ----
    def get_score(self) -> float:
        return self._score

    def set_score(self, v: float) -> None:
        self._score = float(v)
        self.update()

    score = Property(float, get_score, set_score)

    def _tick_pulse(self) -> None:
        # 仅当存在问题时呼吸，正常状态保持静止，避免干扰阅读
        if self._sev in ("warn", "critical"):
            self._pulse += 0.06 * self._pulse_dir
            if self._pulse > 1.0:
                self._pulse, self._pulse_dir = 1.0, -1
            elif self._pulse < 0.0:
                self._pulse, self._pulse_dir = 0.0, 1
            self.update()

    def set_result(self, score: int, caption: str, sev: str) -> None:
        self._target = float(score)
        self._caption = caption
        self._sev = sev
        self._anim.stop()
        self._anim.setStartValue(self._score)
        self._anim.setEndValue(float(score))
        self._anim.start()

    def reset(self) -> None:
        self._caption = "等待检测"
        self._sev = "skip"
        self._anim.stop()
        self._anim.setStartValue(self._score)
        self._anim.setEndValue(0.0)
        self._anim.start()

    # ---- 绘制 ----
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt 命名
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        side = min(self.width(), self.height()) - 26
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        thickness = 11.0

        color = QColor(sev_color(self._sev))

        # 1) 外圈微光（问题态呼吸）
        glow_alpha = int(28 + 46 * self._pulse) if self._sev in ("warn", "critical") else 20
        glow = QRadialGradient(rect.center(), side / 2 + 12)
        gc = QColor(color)
        gc.setAlpha(glow_alpha)
        glow.setColorAt(0.72, QColor(0, 0, 0, 0))
        glow.setColorAt(1.0, gc)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(rect.adjusted(-12, -12, 12, 12))

        # 2) 轨道
        track_pen = QPen(QColor(T.LINE), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.drawArc(rect, 225 * 16, -270 * 16)

        # 3) 进度弧（渐变）
        span = -270.0 * max(0.0, min(1.0, self._score / 100.0))
        if abs(span) > 0.5:
            grad = QConicalGradient(rect.center(), 225)
            c1 = QColor(color)
            c2 = QColor(T.CYAN)
            grad.setColorAt(0.0, c1)
            grad.setColorAt(0.5, c1)
            grad.setColorAt(1.0, c2)
            pen = QPen(QBrush(grad), thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 225 * 16, int(span * 16))

        # 4) 中央数字
        p.setPen(QPen(QColor(T.TEXT)))
        f = QFont("Consolas", 34, QFont.Weight.Bold)
        p.setFont(f)
        num_rect = QRectF(rect.center().x() - side / 2, rect.center().y() - 34, side, 48)
        p.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, str(int(round(self._score))))

        # 5) 分数标签
        p.setFont(ui_font(8))
        p.setPen(QPen(QColor(T.TEXT_FAINT)))
        p.drawText(QRectF(rect.center().x() - side / 2, rect.center().y() + 14, side, 16),
                   Qt.AlignmentFlag.AlignCenter, "HEALTH SCORE")

        # 6) 说明文字
        p.setFont(ui_font(9, QFont.Weight.DemiBold))
        p.setPen(QPen(color))
        p.drawText(QRectF(rect.center().x() - side / 2 - 30, rect.center().y() + 34,
                          side + 60, 22),
                   Qt.AlignmentFlag.AlignCenter, self._caption)
        p.end()


# --------------------------------------------------------------------------- #
# 严重度徽章
# --------------------------------------------------------------------------- #
_SEV_TEXT = {
    "ok": "正常", "info": "提示", "warn": "异常", "critical": "严重", "skip": "跳过",
}


class SeverityBadge(QWidget):
    """圆角胶囊形状态徽章。文字与颜色由严重度决定，宽度自适应。"""

    def __init__(self, severity: str = "skip", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sev = severity
        self.setFixedHeight(22)
        self.setMinimumWidth(52)
        f = ui_font(8, QFont.Weight.DemiBold)
        self.setFont(f)
        fm = self.fontMetrics()
        self.setFixedWidth(max(52, fm.horizontalAdvance(_SEV_TEXT.get(severity, "")) + 20))

    def set_severity(self, sev: str) -> None:
        self._sev = sev
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = QColor(sev_color(self._sev))
        bg = QColor(c)
        bg.setAlpha(28)
        r = QRectF(0, 0, self.width(), self.height())
        p.setPen(QPen(QColor(c.red(), c.green(), c.blue(), 130), 1))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 11, 11)
        p.setPen(QPen(c))
        p.setFont(self.font())
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, _SEV_TEXT.get(self._sev, ""))
        p.end()


# --------------------------------------------------------------------------- #
# 迷你延迟曲线
# --------------------------------------------------------------------------- #
class SparkLine(QWidget):
    """固定容量环形缓冲的折线图，用于展示延迟 / 丢包趋势。"""

    def __init__(self, max_points: int = 60, color: str = T.CYAN,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: deque[float] = deque(maxlen=max_points)
        self._color = color
        self._max_value = 100.0
        self.setMinimumHeight(46)

    def push(self, value: float) -> None:
        self._points.append(value)
        self._max_value = max(100.0, max(self._points) * 1.15 if self._points else 100.0)
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def clear(self) -> None:
        self._points.clear()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        if len(self._points) < 2:
            p.setPen(QPen(QColor(T.TEXT_FAINT)))
            p.setFont(ui_font(8))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, "等待采样")
            p.end()
            return

        # 网格
        p.setPen(QPen(QColor(T.LINE_SOFT), 1))
        for i in range(1, 3):
            y = h * i / 3
            p.drawLine(0, int(y), w, int(y))

        pts = list(self._points)
        step = w / max(1, len(pts) - 1)
        path = QPainterPath()
        for i, v in enumerate(pts):
            x = i * step
            y = h - (v / self._max_value) * (h - 4) - 2
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        # 填充
        fill = QPainterPath(path)
        fill.lineTo(w, h)
        fill.lineTo(0, h)
        fill.closeSubpath()
        grad = QLinearGradient(0, 0, 0, h)
        c = QColor(self._color)
        c.setAlpha(70)
        grad.setColorAt(0, c)
        c2 = QColor(self._color)
        c2.setAlpha(0)
        grad.setColorAt(1, c2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawPath(fill)

        # 折线
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(self._color), 1.8))
        p.drawPath(path)

        # 末点高亮
        last_x, last_y = (len(pts) - 1) * step, h - (pts[-1] / self._max_value) * (h - 4) - 2
        p.setBrush(QBrush(QColor(self._color)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(last_x - 2.5, last_y - 2.5, 5, 5))
        p.end()


# --------------------------------------------------------------------------- #
# 卡片 / 面板容器
# --------------------------------------------------------------------------- #
class Card(QFrame):
    """带标题的卡片。内容区通过 body 布局添加控件。"""

    def __init__(self, title: str = "", subtitle: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 13, 16, 13)
        outer.setSpacing(8)

        if title:
            head = QHBoxLayout()
            head.setSpacing(8)
            self.title_label = QLabel(title)
            self.title_label.setFont(ui_font(10, QFont.Weight.DemiBold))
            self.title_label.setStyleSheet(f"color:{T.TEXT};")
            head.addWidget(self.title_label)
            head.addStretch(1)
            self.head_tail = QWidget()
            self._tail_layout = QHBoxLayout(self.head_tail)
            self._tail_layout.setContentsMargins(0, 0, 0, 0)
            head.addWidget(self.head_tail)
            outer.addLayout(head)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setObjectName("Caption")
                sub.setWordWrap(True)
                outer.addWidget(sub)
        else:
            self.title_label = QLabel("")
            self.head_tail = QWidget()
            self._tail_layout = QHBoxLayout(self.head_tail)

        self.body = QVBoxLayout()
        self.body.setSpacing(7)
        outer.addLayout(self.body, 1)

    def add_tail_widget(self, w: QWidget) -> None:
        self._tail_layout.addWidget(w)

    def set_title(self, text: str) -> None:
        """运行时更新卡片标题（语言切换时调用）。"""
        self.title_label.setText(text)


class Panel(QFrame):
    """无标题的大面板，用于页面主容器。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(20, 18, 20, 18)
        self.body.setSpacing(12)


class GlowLabel(QLabel):
    """带柔和投影的标题，用于仪表盘主数值。"""

    def __init__(self, text: str, color: str = T.ACCENT,
                 size: int = 22, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setFont(QFont("Consolas", size, QFont.Weight.Bold))
        self.setStyleSheet(f"color:{color};")
        eff = QGraphicsDropShadowEffect(self)
        c = QColor(color)
        c.setAlpha(120)
        eff.setColor(c)
        eff.setBlurRadius(22)
        eff.setOffset(0, 0)
        self.setGraphicsEffect(eff)


class Divider(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background:{T.LINE_SOFT};")


class Toast(QLabel):
    """轻量悬浮提示，不阻断操作。"""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setVisible(False)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: rgba(16,25,40,0.97); border:1px solid {T.LINE};"
            f"border-radius:9px; padding:9px 16px; color:{T.TEXT}; font-size:9.5pt;"
        )
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_message(self, text: str, msec: int = 2600) -> None:
        self.setText(text)
        self.adjustSize()
        parent_rect = self.parentWidget().rect()
        self.move((parent_rect.width() - self.width()) // 2,
                  parent_rect.height() - self.height() - 26)
        self.setVisible(True)
        self.raise_()
        self._timer.start(msec)


class ModuleCard(QFrame):
    """左侧导航卡 / 功能入口卡：标题 + 说明 + 可点击。"""

    clicked = Signal()

    def __init__(self, title: str, desc: str, icon: str = "◆",
                 accent: str = T.ACCENT, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(12)

        badge = QLabel(icon)
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color:{accent}; background: rgba(255,255,255,0.03);"
            f"border:1px solid {T.LINE}; border-radius:9px; font-size:13pt;"
        )
        lay.addWidget(badge)

        texts = QVBoxLayout()
        texts.setSpacing(2)
        t = QLabel(title)
        t.setFont(ui_font(10, QFont.Weight.DemiBold))
        t.setStyleSheet(f"color:{T.TEXT};")
        d = QLabel(desc)
        d.setObjectName("Caption")
        d.setWordWrap(True)
        texts.addWidget(t)
        texts.addWidget(d)
        lay.addLayout(texts, 1)

        arrow = QLabel("›")
        arrow.setStyleSheet(f"color:{T.TEXT_FAINT}; font-size:14pt;")
        lay.addWidget(arrow)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


def hline() -> Divider:
    return Divider()


def kv_row(key: str, value: str, ok: bool | None = None) -> QWidget:
    """键值行：左灰色键名、右等宽值，可选状态色。"""
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 2, 0, 2)
    lay.setSpacing(8)
    k = QLabel(key)
    k.setObjectName("Caption")
    k.setFixedWidth(150)
    v = QLabel(value)
    v.setFont(mono_font(9))
    color = T.TEXT
    if ok is True:
        color = T.ACCENT
    elif ok is False:
        color = T.DANGER
    v.setStyleSheet(f"color:{color};")
    v.setWordWrap(True)
    v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    lay.addWidget(k)
    lay.addWidget(v, 1)
    return w


def make_shadow(widget: QWidget, blur: int = 30, alpha: int = 90) -> None:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setColor(QColor(0, 0, 0, alpha))
    eff.setOffset(0, 4)
    widget.setGraphicsEffect(eff)


__all__ = [
    "HealthGauge", "SeverityBadge", "SparkLine", "Card", "Panel", "GlowLabel",
    "Divider", "Toast", "ModuleCard", "hline", "kv_row", "make_shadow",
]
