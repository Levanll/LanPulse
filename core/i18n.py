"""国际化核心 —— 运行时语言切换 + 缺失键可见 + 无第三方依赖。

为什么自己写而不上 gettext/Qt 自带翻译：
  * Qt 的 .ts/.qm 需要 lrelease 编译，PyInstaller 打包时容易漏文件；
    改一个文案要重新走一遍编译流程，对单机小工具太重。
  * gettext 的 .mo 同样需要编译，且不能热切换（进程级绑定）。
  * 本软件只有两种语言、约 600 条文案，一个扁平 dict + 一个信号就够，
    且能保证**切换语言后已打开的窗口立即重绘**，不需要重启。

三条硬规则：
  1. 缺失的 key 必须**显式可见**（返回 `⟦key⟧` 而不是静默回退英文），
     否则漏翻译的界面看起来像正常的英文界面，永远发现不了。
  2. 任何语言表缺 key，测试必须失败（tests 里有全覆盖校验）。
  3. 所有面向用户的字符串必须走 t()，不得在代码里拼中文或英文。
"""
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Iterable


_ZH = "zh"
_EN = "en"

_lock = threading.RLock()
_current = _EN
_catalogs: dict[str, dict[str, str]] = {}
_listeners: list[Callable[[str], None]] = []
_missing: set[str] = set()


def register_catalog(lang: str, catalog: dict[str, str]) -> None:
    """登记一个语言的文案表。同语言重复登记会合并（后者覆盖）。"""
    with _lock:
        bucket = _catalogs.setdefault(lang, {})
        bucket.update(catalog)


def register_all(catalogs: dict[str, dict[str, str]]) -> None:
    for lang, cat in catalogs.items():
        register_catalog(lang, cat)


def set_language(lang: str) -> None:
    """切换当前语言并通知所有监听者（UI 会据此重绘）。"""
    global _current
    if lang not in (_ZH, _EN):
        return
    with _lock:
        if _current == lang:
            return
        _current = lang
        callbacks = list(_listeners)
    for cb in callbacks:
        cb(lang)


def get_language() -> str:
    return _current


def on_language_changed(callback: Callable[[str], None]) -> None:
    with _lock:
        _listeners.append(callback)


def available_languages() -> tuple[str, ...]:
    return (_ZH, _EN)


def t(key: str, /, **fmt: Any) -> str:
    """取文案。

    key 缺失时返回 `⟦key⟧` —— 刻意让它难看，这样漏翻的地方一眼可见，
    而不是被英文兜底掩盖成"看起来正常"。
    """
    with _lock:
        cat = _catalogs.get(_current, {})
        text = cat.get(key)
        if text is None:
            # 回退到另一语言，但仍标记缺失，便于测试与开发期发现
            other = _catalogs.get(_EN if _current == _ZH else _ZH, {})
            text = other.get(key)
            if text is None:
                _missing.add(key)
                return f"⟦{key}⟧"
    if fmt:
        try:
            return text.format(**fmt)
        except (KeyError, IndexError, ValueError):
            # 占位符与传入参数不匹配属于开发期错误，原样返回可读文案而不是抛异常
            return text
    return text


def tn(singular_key: str, plural_key: str, n: int, /, **fmt: Any) -> str:
    """英文需要单复数，中文不需要。用两个 key 表达，避免运行时猜词形。"""
    key = singular_key if n == 1 else plural_key
    fmt.setdefault("n", n)
    return t(key, **fmt)


def missing_keys() -> Iterable[str]:
    with _lock:
        return sorted(_missing)


def clear_missing() -> None:
    with _lock:
        _missing.clear()


def catalog_size(lang: str) -> int:
    with _lock:
        return len(_catalogs.get(lang, {}))


def keys_of(lang: str) -> set[str]:
    with _lock:
        return set(_catalogs.get(lang, {}))


def _bootstrap() -> None:
    """导入内置语言包。放在函数里避免 import 环。"""
    from app import i18n_zh, i18n_en

    register_catalog(_ZH, i18n_zh.CATALOG)
    register_catalog(_EN, i18n_en.CATALOG)
    # 按系统语言初始化，后续由设置覆盖。
    # 用环境变量而不是 locale.getdefaultlocale()：后者在 Python 3.15 会被移除，
    # 且在 Windows 上对 Unicode 环境返回的值并不稳定。
    lang = (os.environ.get("LANG") or os.environ.get("LC_ALL") or "").lower()
    if not lang:
        try:
            import ctypes

            lang = str(ctypes.windll.kernel32.GetUserDefaultUILanguage())
            # 2052 = zh-CN, 1028 = zh-TW, 3076 = zh-HK
            lang = "zh" if lang in ("2052", "1028", "3076") else "en"
        except (AttributeError, OSError):
            lang = "en"
    set_language(_ZH if lang.startswith("zh") else _EN)


_bootstrap()

__all__ = [
    "t", "tn", "set_language", "get_language", "on_language_changed",
    "available_languages", "register_catalog", "register_all",
    "missing_keys", "clear_missing", "catalog_size", "keys_of",
    "_ZH", "_EN",
]
