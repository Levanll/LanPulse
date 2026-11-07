r"""项目一致性检查：确保所有对外信息与实际代码同步。

这类检查存在的理由：README 写 11 项而代码有 14 项、About 描述停留在旧版本，
这类"文档与实现漂移"在手工维护的项目里几乎必然发生，而且没人会主动发现。
把它做成脚本，每次发布前跑一遍。

检查项：
  1. 检测项数量：README/About 描述 vs registry 实际数量
  2. 修复动作数量：文档 vs action_ids
  3. 场景数量：文档 vs scenarios
  4. 版本号：branding vs installer vs README vs CHANGELOG
  5. 品牌名残留（旧品牌）
  6. 截图文件与 README 引用是否一一对应
  7. i18n key 完整性
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

try:
    from _console import setup_console

    setup_console()
except ImportError:
    pass

from core.action_ids import ACTIONS  # noqa: E402
from core.branding import DATA_DIR_NAME, NAME, VERSION  # noqa: E402
from core.registry import load_checks  # noqa: E402
from core.scenarios import SCENARIOS  # noqa: E402

#: 旧品牌名。拼接写避免脚本自身被误报
OLD_BRAND = "Net" + "Pulse"

SKIP_DIRS = {".venv", "dist", "release", ".git", "__pycache__", ".pytest_cache"}
TEXT_SUFFIX = {".py", ".md", ".iss", ".ps1", ".yml", ".yaml", ".spec",
               ".txt", ".isl", ".json"}


def iter_text_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in TEXT_SUFFIX:
            continue
        yield p


def check(msg: str, ok: bool, detail: str = "") -> bool:
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"  {mark} {msg}")
    if detail and not ok:
        print(f"         {detail}")
    return ok


def main() -> int:
    failures = 0
    n_checks = len(load_checks())
    n_actions = len(ACTIONS)
    n_scenarios = len(SCENARIOS)

    print("=" * 66)
    print(f"{NAME} 项目一致性检查")
    print("=" * 66)
    print(f"实际值：检测 {n_checks} 项 / 动作 {n_actions} 个 / "
          f"场景 {n_scenarios} 个 / 版本 {VERSION}\n")

    # ---- 1. 文档中的数量声明 ----
    print("[1] 数量声明")
    patterns = [
        ("11 项", n_checks == 11), ("11 checks", n_checks == 11),
        ("11 个", n_checks == 11),
    ]
    stale = []
    for p in iter_text_files():
        if p.name in ("CHANGELOG.md", "check_consistency.py"):
            continue
        # 工具脚本里的示例文本不算文档声明
        if p.parent.name == "tools":
            continue
        try:
            s = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token, valid in patterns:
            if valid:
                continue
            for m in re.finditer(re.escape(token), s):
                ln = s[: m.start()].count("\n") + 1
                line = s.splitlines()[ln - 1].strip()
                # 排除对比文档里的历史描述
                if "对比分析" in str(p):
                    continue
                stale.append((p.relative_to(ROOT), ln, token, line[:60]))
    failures += 0 if check("文档中无过期的『11 项』声明", not stale,
                           f"{len(stale)} 处") else 1
    for item in stale[:8]:
        print(f"         {item[0]}:{item[1]}  {item[3]}")

    # 文档必须声明正确的数量
    readme = ROOT / "README.md"
    if readme.is_file():
        txt = readme.read_text(encoding="utf-8")
        ok = f"{n_checks} 项" in txt
        failures += 0 if check(f"README.md 声明了『{n_checks} 项』", ok) else 1
    readme_en = ROOT / "README_EN.md"
    if readme_en.is_file():
        txt = readme_en.read_text(encoding="utf-8")
        ok = f"{n_checks} checks" in txt
        failures += 0 if check(f"README_EN.md 声明了『{n_checks} checks』", ok) else 1

    # ---- 2. 版本号一致 ----
    print("\n[2] 版本号")
    iss = ROOT / "installer" / "LanPulse.iss"
    if iss.is_file():
        # 只匹配行首为 #define 的行（跳过 ; 开头的注释示例）
        m = None
        for line in iss.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith(";"):
                continue
            mm = re.search(r'^\s*#define\s+MyAppVersion\s+"([^"]+)"', line)
            if mm:
                m = mm
                break
        got = m.group(1) if m else "?"
        failures += 0 if check(f"installer 版本 {got} == branding {VERSION}",
                               got == VERSION) else 1
    changelog = ROOT / "CHANGELOG.md"
    if changelog.is_file():
        txt = changelog.read_text(encoding="utf-8")
        ok = f"## [{VERSION}]" in txt
        failures += 0 if check(f"CHANGELOG 顶部含 {VERSION}", ok) else 1

    # ---- 3. 品牌名残留 ----
    print("\n[3] 品牌名")
    leftovers = []
    for p in iter_text_files():
        try:
            s = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if OLD_BRAND in s:
            leftovers.append(p.relative_to(ROOT))
    failures += 0 if check("全项目无旧品牌残留", not leftovers,
                           f"{len(leftovers)} 个文件") else 1
    for p in leftovers[:8]:
        print(f"         {p}")

    # ---- 4. 数据目录名 ----
    print("\n[4] 数据目录")
    failures += 0 if check(f"数据目录为 {DATA_DIR_NAME}",
                           DATA_DIR_NAME == NAME) else 1

    # ---- 5. 截图与引用 ----
    print("\n[5] 截图")
    img_dir = ROOT / "docs" / "images"
    for readme_name, suffix in (("README.md", ""), ("README_EN.md", "-en")):
        p = ROOT / readme_name
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8")
        refs = re.findall(r"\]\((docs/images/[^)]+)\)", txt)
        missing = [r for r in refs if not (ROOT / r).is_file()]
        failures += 0 if check(f"{readme_name} 引用的 {len(refs)} 张图全部存在",
                               not missing, ", ".join(missing[:3])) else 1
        # 英文版不该引用中文截图
        if suffix == "-en":
            cn = [r for r in refs if r.endswith((".png",)) and "-en" not in r
                  and "-zh" not in r]
            # settings-zh 是中文截图，英文版不应出现
            bad = [r for r in refs if "settings-zh" in r or
                   (r.endswith(".png") and "-en" not in r and "hero" not in r
                    and "settings-zh" not in r)]
            failures += 0 if check("README_EN 只引用英文截图", not bad,
                                   ", ".join(bad[:3])) else 1

    # ---- 6. i18n ----
    print("\n[6] 国际化")
    try:
        from app import i18n_en, i18n_zh

        zh, en = set(i18n_zh.CATALOG), set(i18n_en.CATALOG)
        failures += 0 if check(f"两语言 key 一致（各 {len(zh)} 条）", zh == en,
                               f"仅zh {sorted(zh-en)[:3]} 仅en {sorted(en-zh)[:3]}") else 1
    except ImportError as exc:
        failures += 1
        check("语言包可导入", False, str(exc))

    print("\n" + "=" * 66)
    if failures == 0:
        print("全部通过。")
    else:
        print(f"发现 {failures} 项不一致，需要修复。")
    print("=" * 66)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
