"""品牌标识的唯一来源。

改名只改这里，不需要在整个代码库搜索替换。所有对外展示的名称
（窗口标题、报告页眉、安装包、注册表项）都从本模块读取。

历史：原名 LanPulse 与 github.com/silentcrow09/netpulse 重名（对方已发到 v1.18.2），
为避免混淆改名为 LanPulse——保留 "Pulse" 的设计语言延续性，
"Lan" 更贴合面向家庭/小型办公局域网的定位。
"""
from __future__ import annotations

#: 产品英文名（用于 exe 名、仓库名、窗口标题）
NAME = "LanPulse"

#: 中文名（用于中文界面的副标题）
NAME_ZH = "澜脉冲"

#: 一句话定位
TAGLINE_ZH = "网络体检与一键修复"
TAGLINE_EN = "Network checkup & one-click repair"

#: 版本号。与 installer/LanPulse.iss 的 MyAppVersion 保持一致。
VERSION = "1.2.0"

#: 窗口标题（单实例检测按此查找窗口，改这里即可全局生效）
WINDOW_TITLE = f"{NAME} - {TAGLINE_ZH}"

#: 应用数据目录名（%LOCALAPPDATA%\<这个>）
DATA_DIR_NAME = "LanPulse"

#: 发布标签前缀（用于 Git tag 与 Release 标题）
TAG_PREFIX = "v"

#: 完整发布标签
RELEASE_TAG = f"{TAG_PREFIX}{VERSION}"


def window_title() -> str:
    return WINDOW_TITLE


def exe_name() -> str:
    return f"{NAME}.exe"


__all__ = [
    "NAME", "NAME_ZH", "TAGLINE_ZH", "TAGLINE_EN", "VERSION",
    "WINDOW_TITLE", "DATA_DIR_NAME", "TAG_PREFIX", "RELEASE_TAG",
    "window_title", "exe_name",
]
