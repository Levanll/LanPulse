"""用户设置：持久化 + 强类型访问 + 变更广播。

存储位置 `%LOCALAPPDATA%\\LanPulse\\settings.json`，UTF-8 明文，用户可直接编辑。
损坏时不会崩溃：视为空配置并以默认值启动，同时把损坏文件备份为 `.invalid`，
避免用户丢失原有设置却毫不知情。

设计约束：
  * 所有键必须有默认值——新增设置项不能要求用户迁移。
  * 未知键保留（用户可能用新版本写入了旧版本不认识的键，回退版本时不丢数据）。
  * 每次写入都走原子替换（atomic_write），断电不会产生半截 JSON。
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Callable

from core import platform_win as pw

SETTINGS_NAME = "settings.json"

#: 语言取值。auto = 跟随系统
LANG_AUTO = "auto"
LANG_ZH = "zh"
LANG_EN = "en"
ALL_LANGS = (LANG_AUTO, LANG_ZH, LANG_EN)

#: 主题
THEME_DARK = "dark"
ALL_THEMES = (THEME_DARK,)

DEFAULTS: dict[str, Any] = {
    "language": LANG_AUTO,
    "region": "auto",
    "theme": THEME_DARK,
    # 启动后自动体检
    "auto_scan_on_start": True,
    # 备份保留数量
    "backup_keep": 30,
    # 高危动作是否需要在确认框里额外勾选（二次确认中的二次确认）
    "extra_confirm_high_risk": True,
    # 报告默认导出格式
    "report_format": "html",
    # 检测超时倍数（网络很慢的地区可调大）
    "timeout_scale": 1.0,
    # 是否允许联网探测（关闭后所有网络探测跳过，只看本地配置）
    "allow_network_probe": True,
    # 是否在报告中包含原始证据
    "report_include_evidence": True,
    # 窗口尺寸记忆
    "window_width": 1280,
    "window_height": 820,
}


@dataclass
class Settings:
    """设置的运行时视图。写操作统一走 set()，保证落盘与通知。"""

    path: str
    _data: dict[str, Any] = field(default_factory=dict)
    _listeners: list[Callable[[str, Any], None]] = field(default_factory=list)

    # ---- 读 ----
    def get(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            return self._data[key]
        return DEFAULTS.get(key, default)

    def get_int(self, key: str) -> int:
        try:
            return int(self.get(key))
        except (TypeError, ValueError):
            return int(DEFAULTS.get(key, 0))

    def get_float(self, key: str) -> float:
        try:
            return float(self.get(key))
        except (TypeError, ValueError):
            return float(DEFAULTS.get(key, 1.0))

    def get_bool(self, key: str) -> bool:
        return bool(self.get(key))

    # ---- 写 ----
    def set(self, key: str, value: Any, *, save: bool = True) -> None:
        old = self.get(key)
        self._data[key] = value
        if save:
            self.save()
        if old != value:
            for cb in list(self._listeners):
                cb(key, value)

    def update(self, values: dict[str, Any]) -> None:
        changed: list[tuple[str, Any]] = []
        for k, v in values.items():
            if self.get(k) != v:
                self._data[k] = v
                changed.append((k, v))
        if not changed:
            return
        self.save()
        for k, v in changed:
            for cb in list(self._listeners):
                cb(k, v)

    def on_change(self, callback: Callable[[str, Any], None]) -> None:
        self._listeners.append(callback)

    # ---- 持久化 ----
    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = dict(DEFAULTS)
        payload.update(self._data)
        pw.atomic_write(self.path, json.dumps(payload, ensure_ascii=False, indent=2))

    def reset(self) -> None:
        self._data = {}
        self.save()

    def as_dict(self) -> dict[str, Any]:
        merged = dict(DEFAULTS)
        merged.update(self._data)
        return merged


def settings_path() -> str:
    return os.path.join(pw.app_data_dir(), SETTINGS_NAME)


def load_settings(path: str | None = None) -> Settings:
    """加载设置。文件损坏时备份为 .invalid 并用默认值启动。"""
    path = path or settings_path()
    data: dict[str, Any] = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                raw = json.load(fh)
            if isinstance(raw, dict):
                # 只保留认识的键 + 用户自定义键；类型不做强制转换，
                # 由各自的 get_xxx 负责容错，避免一处类型错误毁掉整份配置
                data = raw
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            try:
                shutil.copy2(path, path + ".invalid")
            except OSError:
                pass
            data = {}
    return Settings(path=path, _data=data)


def effective_language(settings: Settings) -> str:
    """把 auto 解析成实际语言。解析失败回退英语（国际化默认）。"""
    lang = str(settings.get("language", LANG_AUTO))
    if lang in (LANG_ZH, LANG_EN):
        return lang
    try:
        import locale as _locale

        name = (_locale.getdefaultlocale()[0] or "").lower()
    except (ValueError, TypeError):
        name = os.environ.get("LANG", "").lower()
    return LANG_ZH if name.startswith("zh") else LANG_EN


__all__ = [
    "Settings", "load_settings", "settings_path", "effective_language",
    "DEFAULTS", "LANG_AUTO", "LANG_ZH", "LANG_EN", "ALL_LANGS",
]
