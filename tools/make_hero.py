"""生成 README 首图（hero banner）。中英各一张。

设计约束（为什么不复用截图里的 UI）：
  * 首图要能一眼讲清"这是什么产品"，不能只截界面
  * 中英各一份：README.md 用 zh，README_EN.md 用 en
  * 所有文案来自 branding / i18n，改版本或改名时只需重跑本脚本

用法：
    python tools/make_hero.py
输出：
    docs/images/hero-banner-zh.png
    docs/images/hero-banner-en.png
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

try:
    from _console import setup_console

    setup_console()
except ImportError:
    pass

from core.branding import NAME, TAGLINE_EN, TAGLINE_ZH, VERSION  # noqa: E402

#: 画布尺寸。宽 1280 适配 GitHub README 的正文宽度。
W, H = 1280, 420

#: 配色与 app/ui/theme.py 保持一致
BG_DEEP = "#070A11"
BG_BASE = "#0A0E17"
ACCENT = "#00E5A0"
CYAN = "#3DD8FF"
TEXT = "#E6EDF7"
TEXT_DIM = "#8A9AB5"
TEXT_FAINT = "#56657F"
LINE = "#1C2740"
WARN = "#FFB020"

ZH = {
    "brand_sub": "澜脉冲",
    "tagline": TAGLINE_ZH,
    "pillars": "诊断 · 解释 · 修复 · 回滚",
    "chips": ["14 项检测", "15 个可回滚修复", "6 个场景"],
    "chips_accent": "中 / 英 双语",
    "footer": "全本地运行 · 零上传 · 每次修改都有备份与审计记录",
}

EN = {
    "brand_sub": "Windows desktop app",
    "tagline": TAGLINE_EN,
    "pillars": "Diagnose · Explain · Repair · Roll back",
    "chips": ["14 checks", "15 reversible fixes", "6 scenarios"],
    "chips_accent": "Chinese / English",
    "footer": "Fully local · zero upload · every change is backed up and audited",
}


def make(lang: str) -> Path:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import (
        QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient,
    )

    data = ZH if lang == "zh" else EN
    pm = QPixmap(W, H)
    pm.fill(QColor(BG_DEEP))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    # ---- 背景：斜向渐变 + 网格 ----
    grad = QLinearGradient(0, 0, W, H)
    grad.setColorAt(0.0, QColor(BG_DEEP))
    grad.setColorAt(0.55, QColor(BG_BASE))
    grad.setColorAt(1.0, QColor("#0B1522"))
    p.fillRect(0, 0, W, H, grad)

    p.setPen(QPen(QColor(255, 255, 255, 10), 1))
    for x in range(0, W, 32):
        p.drawLine(x, 0, x, H)
    for y in range(0, H, 32):
        p.drawLine(0, y, W, y)

    # ---- 右侧环形仪表 ----
    cx, cy, radius = 960, H / 2, 118
    glow = QRadialGradient(cx, cy, radius + 60)
    c = QColor(ACCENT)
    c.setAlpha(46)
    glow.setColorAt(0.6, QColor(0, 0, 0, 0))
    glow.setColorAt(1.0, c)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QRectF(cx - radius - 60, cy - radius - 60,
                         (radius + 60) * 2, (radius + 60) * 2))

    ring = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(LINE), 13, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(ring, 225 * 16, -270 * 16)
    p.setPen(QPen(QColor(ACCENT), 13, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(ring, 225 * 16, int(-270 * 16 * 0.86))
    p.setPen(QPen(QColor(CYAN), 13, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawArc(ring, int((225 - 270 * 0.86) * 16), int(-270 * 16 * 0.14))

    # ---- 环内波形（呼应 "Pulse"）----
    import math

    p.setPen(QPen(QColor(ACCENT), 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    prev = None
    for i in range(0, 101):
        t = i / 100.0
        px = cx - radius * 0.62 + t * radius * 1.24
        amp = math.sin(t * math.pi * 2.6) * 20 * (1 - abs(t - 0.5) * 1.2)
        py = cy + amp
        if prev is not None:
            p.drawLine(int(prev[0]), int(prev[1]), int(px), int(py))
        prev = (px, py)

    # ---- 左侧文字 ----
    left = 84
    p.setPen(QColor(TEXT))
    p.setFont(QFont("Segoe UI", 46, QFont.Weight.Bold))
    p.drawText(left, 132, NAME.upper())

    # 品牌名下的强调线
    p.setPen(QPen(QColor(ACCENT), 3))
    p.drawLine(left + 2, 152, left + 132, 152)

    p.setPen(QColor(TEXT_DIM))
    p.setFont(QFont("Microsoft YaHei UI" if lang == "zh" else "Segoe UI", 19))
    p.drawText(left, 196, data["brand_sub"])

    p.setPen(QColor(TEXT))
    p.setFont(QFont("Microsoft YaHei UI" if lang == "zh" else "Segoe UI", 22,
                    QFont.Weight.DemiBold))
    p.drawText(left, 234, data["tagline"])

    p.setPen(QColor(TEXT_DIM))
    p.setFont(QFont("Consolas", 13))
    p.drawText(left, 264, data["pillars"])

    # ---- 标签胶囊 ----
    def chip(x: int, text: str, color: str) -> int:
        f = QFont("Microsoft YaHei UI" if lang == "zh" else "Segoe UI", 11,
                  QFont.Weight.DemiBold)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(text) + 34
        r = QRectF(x, 292, w, 38)
        bg = QColor(color)
        bg.setAlpha(30)
        p.setPen(QPen(QColor(color), 1.4))
        p.setBrush(bg)
        p.drawRoundedRect(r, 19, 19)
        p.setPen(QColor(color))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        return x + int(w) + 14

    x = left
    for text in data["chips"]:
        x = chip(x, text, ACCENT)
    chip(x, data["chips_accent"], WARN)

    # ---- 底注 ----
    p.setPen(QColor(TEXT_FAINT))
    p.setFont(QFont("Microsoft YaHei UI" if lang == "zh" else "Segoe UI", 11))
    p.drawText(left, 372, data["footer"])

    # ---- 版本角标 ----
    p.setPen(QColor(TEXT_FAINT))
    p.setFont(QFont("Consolas", 11))
    p.drawText(W - 96, H - 18, f"v{VERSION}")

    p.end()

    out = ROOT / "docs" / "images" / f"hero-banner-{lang}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    pm.save(str(out))
    return out


def main() -> int:
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)  # noqa: F841 - QPixmap 需要 QApplication
    for lang in ("zh", "en"):
        path = make(lang)
        print(f"  已生成 {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
