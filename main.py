"""LanPulse 启动入口。

启动顺序（每一步失败都有明确的降级或提示，不静默）：
  1. 单实例互斥 —— 已有实例则把它的窗口唤到前台并退出；
  2. 初始化日志与 Qt 应用；
  3. 判定是否管理员：是则正常启动；否则在首次运行时提示可提权（不强制，
     因为体检、报告、备份查看都不需要管理员权限）；
  4. 应用深色主题并显示主窗口。
"""
from __future__ import annotations

import ctypes
import os
import sys


def _ensure_path() -> None:
    """保证以脚本方式或打包方式运行时都能 import 到包内模块。"""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


def main(argv: list[str] | None = None) -> int:
    _ensure_path()

    # 打包后 HIGH DPI 由 Qt 自身处理；未打包时确保任务栏图标不被合并成 python 图标
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LanPulse.Desktop.1")
        except (AttributeError, OSError):
            pass

    from app.logging_setup import setup_logging

    verbose = "--verbose" in (argv or sys.argv)
    log = setup_logging(verbose=verbose)
    log.info("LanPulse 启动，Python %s，平台 %s", sys.version.split()[0], sys.platform)

    # ---- 单实例 ----
    try:
        from app.sysutil import SingleInstance
    except ImportError:
        SingleInstance = None  # type: ignore[assignment]
    guard = None
    if SingleInstance is not None:
        guard = SingleInstance()
        if not guard.acquire():
            guard.activate_existing()
            return 0

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont, QIcon, QPixmap
    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow
    from app.ui.state import AppState
    from core import platform_win as pw

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("LanPulse")
    # 不设 setApplicationDisplayName：Qt 会把它追加到窗口标题后面，
    # 导致标题变成「LanPulse - 网络体检与优化 - LanPulse 网络体检与优化」，
    # 也会让单实例用 FindWindowW 按标题唤起窗口时匹配不上。
    app.setOrganizationName("LanPulse")
    app.setStyle("Fusion")

    font = QFont("Microsoft YaHei UI", 10)
    app.setFont(font)
    app.setWindowIcon(_make_icon())

    elevated = pw.is_elevated()
    log.info("管理员权限：%s", elevated)

    # 语言必须在建窗口前定好，否则第一帧会用系统默认语言渲染再被覆盖
    from core import i18n
    from core.settings import effective_language, load_settings

    settings = load_settings()
    lang = effective_language(settings)
    i18n.set_language(lang)
    log.info("语言：%s，区域：%s", lang, settings.get("region"))

    state = AppState(settings=settings)
    window = MainWindow(state, elevated=elevated, settings=settings)
    window.show()

    exit_code = app.exec()
    log.info("LanPulse 退出，code=%s", exit_code)
    if guard is not None:
        guard.release()
    return int(exit_code)


def _make_icon() -> "object":
    """用 QPainter 画一个程序图标，避免依赖外部资源文件（打包更简单）。"""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(size * 0.08, size * 0.08, size * 0.84, size * 0.84)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#0A0E17"))
        p.drawRoundedRect(r, size * 0.2, size * 0.2)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#00E5A0"), max(1.5, size * 0.075)))
        p.drawArc(r.adjusted(size * 0.16, size * 0.16, -size * 0.16, -size * 0.16),
                  225 * 16, -270 * 16)
        p.setPen(QPen(QColor("#3DD8FF"), max(1.2, size * 0.05)))
        cy = size * 0.5
        p.drawLine(int(size * 0.32), int(cy), int(size * 0.68), int(cy))
        p.end()
        icon.addPixmap(pm)
    return icon


if __name__ == "__main__":
    sys.exit(main())
