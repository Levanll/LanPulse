r"""审计：代码里引用但语言包中缺失的 i18n key。

用法: .\.venv\Scripts\python.exe tools\audit_i18n.py
返回码：0 = 无缺失；1 = 有缺失（CI 可直接用它做门禁）。

docstring 前缀 r 是必需的：正文含 `\.venv` 这类 Windows 反斜杠路径，
不加会触发 SyntaxWarning。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import i18n_en, i18n_zh  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()

# 匹配 t("a.b") / t('a.b', ...) / tn("a.b", ...)
KEY_RE = re.compile(r"""\bt\(\s*["']([a-z][\w]*(?:\.[\w]+)+)["']""")

# 这些不是 i18n key，是动作 id / 其它标识符，误报时在此登记
KNOWN_NON_KEYS = {"mtu.optimize"}


def _duplicate_keys(path: pathlib.Path) -> list[tuple[str, int, int]]:
    """找出语言包源码里重复定义的 key。

    必须读源码而不是遍历 CATALOG：Python 的 dict 字面量遇到重复键会**静默
    保留后者**，运行时根本看不到重复。`msg.rollback_partial` 就这样被定义过
    两次、值还不一样，界面上表现为"文案改了没生效"。

    返回 [(key, 首次行号, 重复行号)]，只报值不同的；值相同的重复属于
    历史冗余，清理它不属于本检查的职责。
    """
    import ast

    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    dups: list[tuple[str, int, int]] = []
    for node in tree.body:
        value = None
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "CATALOG":
            value = node.value
        elif isinstance(node, ast.Assign) and any(
                getattr(t, "id", None) == "CATALOG" for t in node.targets):
            value = node.value
        if not isinstance(value, ast.Dict):
            continue
        seen: dict[str, tuple[int, object]] = {}
        for k, v in zip(value.keys, value.values):
            if not (isinstance(k, ast.Constant) and isinstance(k.value, str)):
                continue
            try:
                lit = ast.literal_eval(v)
            except ValueError:
                lit = object()
            if k.value in seen:
                first_line, first_lit = seen[k.value]
                if first_lit != lit:
                    dups.append((k.value, first_line, k.lineno))
            else:
                seen[k.value] = (k.lineno, lit)
    return dups


def main() -> int:
    used: set[str] = set()
    for p in list((ROOT / "app").rglob("*.py")) + list((ROOT / "core").rglob("*.py")):
        if p.name.startswith("i18n_"):
            continue
        used.update(KEY_RE.findall(p.read_text(encoding="utf-8")))
    used -= KNOWN_NON_KEYS

    zh_keys, en_keys = set(i18n_zh.CATALOG), set(i18n_en.CATALOG)
    miss_zh = sorted(k for k in used if k not in zh_keys)
    miss_en = sorted(k for k in used if k not in en_keys)
    only_zh = sorted(zh_keys - en_keys)
    only_en = sorted(en_keys - zh_keys)

    print(f"代码引用 key：{len(used)}")
    print(f"语言包规模：zh={len(zh_keys)} en={len(en_keys)}")
    bad = False
    if miss_zh:
        bad = True
        print(f"\nzh 缺失 {len(miss_zh)} 个：")
        for k in miss_zh:
            print("  -", k)
    if miss_en:
        bad = True
        print(f"\nen 缺失 {len(miss_en)} 个：")
        for k in miss_en:
            print("  -", k)
    if only_zh:
        bad = True
        print(f"\n仅 zh 有 {len(only_zh)} 个：{only_zh[:20]}")
    if only_en:
        bad = True
        print(f"\n仅 en 有 {len(only_en)} 个：{only_en[:20]}")

    # ---- 语言包内重复 key（后一个会静默覆盖前一个） ----
    for name, path in (("zh", ROOT / "app" / "i18n_zh.py"),
                       ("en", ROOT / "app" / "i18n_en.py")):
        dups = _duplicate_keys(path)
        if dups:
            bad = True
            print(f"\n{name} 有 {len(dups)} 个重复 key（后值覆盖前值）：")
            for key, first, again in dups:
                print(f"  - {key}  行 {first} 被行 {again} 覆盖")

    if not bad:
        print("\n通过：无缺失、两语言 key 集合完全一致、无重复定义。")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
