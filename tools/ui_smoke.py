r"""UI 冒烟与截图脚本（开发期工具，不参与打包）。

用法：
    .\.venv\Scripts\python.exe tools\ui_smoke.py

它会在真实体检结果上渲染每一个页面并截图到 shots/，用于人工核对排版。
不修改任何系统配置。
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.state import AppState

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "shots")
PAGES = ["dashboard", "dns", "hosts", "repair", "backup", "diagnose", "report"]


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv)

    from core import platform_win as pw

    state = AppState()
    win = MainWindow(state, elevated=pw.is_elevated())
    win.show()

    # 直接同步跑一次体检，跳过自动扫描的异步路径，保证截图有数据
    report = state.run_diagnosis()
    state.set_report(report)
    print(f"体检完成：{len(report.results)} 项，健康分 {report.score}")

    idx = {"i": 0}

    def shoot_next() -> None:
        i = idx["i"]
        if i >= len(PAGES):
            print("所有页面已截图")
            app.quit()
            return
        win.switch_page(i)
        app.processEvents()
        time.sleep(0.35)
        app.processEvents()
        path = os.path.join(OUT, f"{i}_{PAGES[i]}.png")
        win.grab().save(path)
        print("saved", path)
        idx["i"] = i + 1
        QTimer.singleShot(500, shoot_next)

    QTimer.singleShot(600, shoot_next)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
