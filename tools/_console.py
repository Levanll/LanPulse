"""控制台输出工具 —— 让脚本在任何代码页下都不会因打印中文而崩溃。

背景（真实缺陷）：
    GitHub Actions 的 windows-latest runner 默认代码页是 **cp1252**，
    而不是中文系统的 cp936。`print("代码引用 key：343")` 在 cp1252 下会抛：

        UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-3

    这不是 pytest 的问题，而是脚本自身在"非中文控制台"上不可用。
    在本地（cp936）一切正常，问题只在 CI 才暴露——正是这类缺陷最容易被漏掉。

解决：
    把 stdout/stderr 重新配置为 UTF-8 + errors="replace"，任何工具
    在任何代码页下都能安全输出中文。这是标准库能力，不引入依赖。
"""
from __future__ import annotations

import sys


def setup_console() -> None:
    """把标准输出切换到 UTF-8 并允许替换无法编码的字符。

    幂等：重复调用无副作用。某些环境（重定向到文件、无 reconfigure 的
    旧版本）不支持时静默跳过，因为此时通常也不会因编码而失败。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            # 已被重定向为不支持 reconfigure 的对象；
            # 退而求其次：保持原样，靠调用方的安全打印兜底
            pass


def safe_print(*args, **kwargs) -> None:
    """print 的兜底版本：编码失败时降级为 ASCII 安全输出。

    只在 setup_console() 之后仍然失败时才会用到（极少见）。
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        msg = " ".join(str(a) for a in args)
        enc = getattr(sys.stdout, "encoding", None) or "ascii"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), **kwargs)


__all__ = ["setup_console", "safe_print"]
