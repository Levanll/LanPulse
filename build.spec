# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置。

打包策略说明：
  * 单目录（--onedir）而非单文件：单文件模式每次启动都要把 PySide6 的
    Qt 运行时解压到临时目录，冷启动 3-6 秒且杀软误报率更高。对一款要频繁
    打开的小工具，单目录更合适。
  * 排除掉 PySide6 里用不到的重量级模块（WebEngine / 3D / Multimedia 等），
    能把体积从 200+ MB 压到 60 MB 左右。
  * 不打包任何外部配置文件——程序的所有资源都由代码生成（图标、主题），
    这样 exe 不会因为缺失附件而启动失败。

用法：
    .\.venv\Scripts\python.exe -m PyInstaller build.spec --noconfirm
"""
from __future__ import annotations

import os

block_cipher = None

# 明确排除的模块：这些是本项目完全没用到、但 PySide6 会连带打进来的大块头。
#
# 踩过的坑（务必保留注释，防止后人重犯）：
#   * 绝不能排除 shiboken6.Shiboken —— 它是 PySide6 的 C++ 绑定运行时，
#     排除后窗口程序会在导入 QtWidgets 时直接崩，且 windowed 模式下只弹
#     “Unhandled exception in script”，看不到任何 traceback，极难定位。
#   * 绝不能排除 email / http / xmlrpc / unittest —— 标准库之间有隐式依赖
#     （例如 urllib 依赖 email、pkg_resources 依赖 unittest 的部分子模块），
#     排掉后报 ModuleNotFoundError 的位置往往与真正缺失项毫无关系。
# 体积优化只动「确定用不到的 Qt 大模块」，不动标准库。
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets", "PySide6.QtQml",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtTextToSpeech", "PySide6.QtUiTools",
    "tkinter", "pytest", "_pytest", "pip",
]

HIDDEN = [
    "core.checks",
    "core.repair",
    "app.ui.pages",
]

a = Analysis(
    ["main.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LanPulse",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # 窗口程序，不弹黑框
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 图标由程序运行时自绘，不依赖外部 .ico
    version=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LanPulse",
)
