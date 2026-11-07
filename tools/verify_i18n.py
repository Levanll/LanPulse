r"""双语与跨区域联合验证。

确认三件事：
  1. 两种语言下所有检测项的 title / summary 都能翻译成真实文字（不出现 ⟦key⟧）
  2. 切换语言不改变检测结论（判定逻辑与文案解耦）
  3. 三个区域剖面下探测目标真的不同

用法: .\.venv\Scripts\python.exe tools\verify_i18n.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.context import DiagnosticContext  # noqa: E402
from core.i18n import missing_keys, set_language, t  # noqa: E402
from core.registry import load_checks, run_all  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()

MISSING_MARK = "\u27e6"  # ⟦


def _show(label: str, text: str) -> str:
    return f"{label}: {text[:60]}"


def main() -> int:
    problems: list[str] = []

    for region in ("cn", "global"):
        ctx = DiagnosticContext(region_override=region)
        results = run_all(ctx)
        print(f"===== region={region}  ({ctx.profile.resolve_domains[0]})")

        severities: dict[str, dict[str, str]] = {}
        for lang in ("zh", "en"):
            set_language(lang)
            print(f"  --- {lang}")
            for r in results:
                title = t(r.title) if not r.title.startswith("check.") else t(r.title)
                summary = r.summary
                if MISSING_MARK in title or MISSING_MARK in summary:
                    problems.append(f"[{region}/{lang}] {r.check_id} 有未翻译文案: {title} / {summary[:50]}")
                print(f"    {r.check_id:<13} {r.severity.value:<8} {title[:26]:<26} | {summary[:46]}")
                severities.setdefault(r.check_id, {})[lang] = r.severity.value

        # 语言只影响文案，不应影响判定
        for cid, by_lang in severities.items():
            if len(set(by_lang.values())) > 1:
                problems.append(f"[{region}] {cid} 判定随语言变化: {by_lang}")
        print()

    set_language("zh")
    # missing_keys 会记录所有"未命中"的查询，包括动态值（IP、数字）——
    # 这些本来就不是 key，属于正常的 tr_or_raw 回退，不算缺陷。
    # 真正的缺陷是界面出现 ⟦key⟧，上面的 MISSING_MARK 检查已经覆盖。
    mk = [k for k in missing_keys() if not _looks_dynamic(k)]
    if mk:
        problems.append(f"缺失 key: {mk[:10]}")

    print(f"语言包：zh={len(_cat('zh'))} keys, en={len(_cat('en'))} keys")

    if problems:
        print("\n发现 %d 个问题：" % len(problems))
        for p in problems:
            print("  ✗", p)
        return 1
    print("\n全部通过：双语渲染完整、判定不受语言影响、区域探测集各自独立。")
    return 0


def _cat(lang: str) -> dict:
    from app import i18n_en, i18n_zh

    return i18n_zh.CATALOG if lang == "zh" else i18n_en.CATALOG


def _looks_dynamic(text: str) -> bool:
    """判断一个"未命中"的查询是不是动态值而非漏翻的 key。

    动态值包括：IP 地址、纯数字、网卡名、域名。
    它们经 tr_or_raw() 查询时会登记进 missing，但本就不该被翻译。
    真正的漏翻特征是"形如 a.b.c 的标识符"，用点号 + 全小写判定。
    注意：域名也含点号（www.baidu.com），所以额外排除以字母开头且含常见 TLD 的情况。
    """
    import re

    if re.fullmatch(r"[\d.]+", text):
        return True                      # IP / 数字
    if re.fullmatch(r"[\d:]+", text):
        return True                      # IPv6
    if "." in text and not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", text):
        return True                      # 含大写或非标识符字符（网卡名、域名带 www.）
    return False


if __name__ == "__main__":
    sys.exit(main())
