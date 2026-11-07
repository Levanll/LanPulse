"""LanPulse 视觉主题 —— 深色科技感。

设计取向：
  * 底色近黑但带蓝紫偏移（#0A0E17），避免纯黑的廉价感；
  * 主色用青绿 #00E5A0 表示“健康/可执行”，预警用琥珀 #FFB020，危险用珊瑚红 #FF5C6C；
  * 圆角 10px、细描边 1px 的半透明边框，配合轻微发光，形成“仪器面板”观感；
  * 全部字号用 pt，正文 10.5pt，标题 15pt，数字用等宽字体，保证排布稳定。

只在此处定义颜色与 QSS，其它模块一律通过 TOKENS 取色，不写死十六进制。
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase


class T:
    """颜色令牌表。"""

    BG_DEEP = "#070A11"
    BG_BASE = "#0A0E17"
    BG_PANEL = "#101725"
    BG_PANEL_ALT = "#0D1420"
    BG_HOVER = "#16203300"  # 透明叠加用

    LINE = "#1C2740"
    LINE_SOFT = "#151E33"

    TEXT = "#E6EDF7"
    TEXT_DIM = "#8A9AB5"
    TEXT_FAINT = "#56657F"

    ACCENT = "#00E5A0"        # 主强调：正常 / 主按钮
    ACCENT_DIM = "#00B37D"
    ACCENT_GLOW = "#00E5A033"

    CYAN = "#3DD8FF"          # 次强调：链接 / 进度
    WARN = "#FFB020"
    DANGER = "#FF5C6C"
    INFO = "#6EA8FF"
    SKIP = "#5B6A85"

    # 严重度 → 颜色
    SEV = {
        "ok": ACCENT,
        "info": INFO,
        "warn": WARN,
        "critical": DANGER,
        "skip": SKIP,
    }


MONO_FAMILY = "Consolas"
UI_FAMILY = "Microsoft YaHei UI"


def mono_font(size: int = 9, weight: int = QFont.Weight.Normal) -> QFont:
    f = QFont(MONO_FAMILY, size)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    f.setWeight(weight)
    return f


def ui_font(size: int = 10, weight: int = QFont.Weight.Normal) -> QFont:
    if UI_FAMILY not in QFontDatabase.families():
        return QFont("Segoe UI", size, weight)
    return QFont(UI_FAMILY, size, weight)


# --------------------------------------------------------------------------- #
# 全局样式表
# --------------------------------------------------------------------------- #
QSS = f"""
* {{
    font-family: "{UI_FAMILY}", "Segoe UI", sans-serif;
    outline: none;
}}

QWidget {{
    color: {T.TEXT};
    background: transparent;
    font-size: 10pt;
}}

#Root {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {T.BG_DEEP}, stop:0.55 {T.BG_BASE}, stop:1 #0B1220);
}}

/* ---------------- 侧栏 ---------------- */
#Sidebar {{
    background: rgba(13, 20, 32, 0.86);
    border-right: 1px solid {T.LINE_SOFT};
}}

#BrandMark {{
    color: {T.ACCENT};
    font-size: 17pt;
    font-weight: 700;
    letter-spacing: 1px;
}}
#BrandSub {{
    color: {T.TEXT_FAINT};
    font-size: 8pt;
    letter-spacing: 3px;
}}

QPushButton#NavButton {{
    text-align: left;
    padding: 10px 14px;
    border: 1px solid transparent;
    border-radius: 8px;
    color: {T.TEXT_DIM};
    font-size: 10pt;
    background: transparent;
}}
QPushButton#NavButton:hover {{
    background: rgba(61, 216, 255, 0.07);
    color: {T.TEXT};
}}
QPushButton#NavButton:checked {{
    background: rgba(0, 229, 160, 0.12);
    border: 1px solid rgba(0, 229, 160, 0.35);
    color: {T.ACCENT};
    font-weight: 600;
}}

/* ---------------- 面板 ---------------- */
#Panel {{
    background: rgba(16, 23, 37, 0.92);
    border: 1px solid {T.LINE};
    border-radius: 12px;
}}
#PanelTight {{
    background: rgba(13, 20, 32, 0.92);
    border: 1px solid {T.LINE_SOFT};
    border-radius: 10px;
}}
#Card {{
    background: rgba(18, 26, 42, 0.9);
    border: 1px solid {T.LINE};
    border-radius: 10px;
}}
#Card:hover {{
    border: 1px solid rgba(0, 229, 160, 0.45);
}}

QLabel#H1 {{
    font-size: 20pt;
    font-weight: 700;
    color: {T.TEXT};
}}
QLabel#H2 {{
    font-size: 13pt;
    font-weight: 600;
    color: {T.TEXT};
}}
QLabel#SectionLabel {{
    font-size: 9pt;
    color: {T.TEXT_FAINT};
    letter-spacing: 2px;
    font-weight: 600;
}}
QLabel#Caption {{
    color: {T.TEXT_DIM};
    font-size: 9pt;
}}
QLabel#Mono {{
    font-family: "{MONO_FAMILY}";
    font-size: 9pt;
    color: {T.TEXT_DIM};
}}

/* ---------------- 按钮 ---------------- */
QPushButton {{
    background: rgba(22, 32, 51, 0.95);
    border: 1px solid {T.LINE};
    border-radius: 8px;
    padding: 9px 18px;
    color: {T.TEXT};
    font-size: 10pt;
}}
QPushButton:hover {{
    background: rgba(30, 43, 68, 0.98);
    border-color: rgba(61, 216, 255, 0.5);
}}
QPushButton:pressed {{
    background: rgba(16, 24, 38, 1);
}}
QPushButton:disabled {{
    color: {T.TEXT_FAINT};
    background: rgba(20, 26, 38, 0.6);
    border-color: {T.LINE_SOFT};
}}

QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {T.ACCENT_DIM}, stop:1 {T.ACCENT});
    color: #04120C;
    font-weight: 700;
    font-size: 11pt;
    border: 1px solid {T.ACCENT};
    border-radius: 10px;
    padding: 12px 26px;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {T.ACCENT}, stop:1 #4DFFC4);
}}
QPushButton#Primary:disabled {{
    background: rgba(0, 179, 125, 0.28);
    color: rgba(230, 237, 247, 0.45);
    border-color: rgba(0, 229, 160, 0.25);
}}

QPushButton#Ghost {{
    background: transparent;
    border: 1px solid {T.LINE};
    color: {T.TEXT_DIM};
}}
QPushButton#Ghost:hover {{
    color: {T.ACCENT};
    border-color: rgba(0, 229, 160, 0.55);
}}

QPushButton#Danger {{
    background: rgba(255, 92, 108, 0.12);
    border: 1px solid rgba(255, 92, 108, 0.55);
    color: {T.DANGER};
}}
QPushButton#Danger:hover {{
    background: rgba(255, 92, 108, 0.2);
}}

/* ---------------- 输入 ---------------- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    background: rgba(9, 14, 23, 0.9);
    border: 1px solid {T.LINE};
    border-radius: 8px;
    padding: 7px 10px;
    color: {T.TEXT};
    selection-background-color: {T.ACCENT_DIM};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid rgba(0, 229, 160, 0.65);
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {T.BG_PANEL};
    border: 1px solid {T.LINE};
    selection-background-color: rgba(0, 229, 160, 0.22);
    outline: none;
}}

QPlainTextEdit#Editor {{
    font-family: "{MONO_FAMILY}";
    font-size: 9.5pt;
    line-height: 150%;
}}

/* ---------------- 滚动条 ---------------- */
QScrollBar:vertical {{
    background: transparent; width: 9px; margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(92, 116, 156, 0.45);
    border-radius: 4px; min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: rgba(0, 229, 160, 0.6); }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: rgba(92, 116, 156, 0.45); border-radius: 4px; min-width: 30px;
}}

/* ---------------- 表格 ---------------- */
QTableWidget {{
    background: rgba(9, 14, 23, 0.6);
    border: 1px solid {T.LINE_SOFT};
    border-radius: 8px;
    gridline-color: {T.LINE_SOFT};
    selection-background-color: rgba(0, 229, 160, 0.16);
    selection-color: {T.TEXT};
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QHeaderView::section {{
    background: rgba(16, 23, 37, 0.95);
    color: {T.TEXT_FAINT};
    border: none;
    border-bottom: 1px solid {T.LINE};
    padding: 7px 8px;
    font-size: 9pt;
    font-weight: 600;
}}

QCheckBox {{ spacing: 9px; color: {T.TEXT}; }}
QCheckBox::indicator {{
    width: 17px; height: 17px;
    border: 1px solid {T.LINE};
    border-radius: 5px;
    background: rgba(9, 14, 23, 0.9);
}}
QCheckBox::indicator:hover {{ border-color: {T.ACCENT_DIM}; }}
QCheckBox::indicator:checked {{
    background: {T.ACCENT};
    border-color: {T.ACCENT};
    image: none;
}}

QProgressBar {{
    background: rgba(9, 14, 23, 0.9);
    border: 1px solid {T.LINE_SOFT};
    border-radius: 5px;
    height: 7px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {T.ACCENT_DIM}, stop:1 {T.CYAN});
    border-radius: 5px;
}}

QTabWidget::pane {{
    border: 1px solid {T.LINE_SOFT};
    border-radius: 10px;
    background: rgba(10, 15, 25, 0.6);
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {T.TEXT_DIM};
    padding: 8px 18px;
    margin-right: 4px;
    border-radius: 8px;
    font-size: 9.5pt;
}}
QTabBar::tab:selected {{
    color: {T.ACCENT};
    background: rgba(0, 229, 160, 0.1);
}}
QTabBar::tab:hover {{ color: {T.TEXT}; }}

QSplitter::handle {{ background: {T.LINE_SOFT}; }}
QSplitter::handle:hover {{ background: {T.ACCENT_DIM}; }}

QToolTip {{
    background: {T.BG_PANEL};
    color: {T.TEXT};
    border: 1px solid {T.LINE};
    border-radius: 6px;
    padding: 5px 8px;
}}

QMessageBox {{ background: {T.BG_PANEL}; }}
QMenu {{
    background: {T.BG_PANEL};
    border: 1px solid {T.LINE};
    border-radius: 8px;
    padding: 5px;
}}
QMenu::item {{ padding: 6px 22px; border-radius: 5px; }}
QMenu::item:selected {{ background: rgba(0, 229, 160, 0.16); }}
"""


def sev_color(sev: str) -> str:
    return T.SEV.get(str(sev), T.TEXT_DIM)


def qcolor(hex_str: str, alpha: int = 255) -> QColor:
    c = QColor(hex_str)
    c.setAlpha(alpha)
    return c


__all__ = ["T", "QSS", "mono_font", "ui_font", "sev_color", "qcolor", "MONO_FAMILY", "UI_FAMILY"]
