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
from core.branding import DATA_DIR_NAME, NAME, VERSION, WINDOW_TITLE  # noqa: E402
from core.registry import load_checks  # noqa: E402
from core.scenarios import SCENARIOS  # noqa: E402

#: 旧品牌名。拼接写避免脚本自身被误报
OLD_BRAND = "Net" + "Pulse"

#: 允许出现旧名的上下文：仅限"兼容旧版构建工具目录"的探测路径。
#: 这类引用不是品牌残留，而是为了在老机器上仍能找到 Inno Setup。
ALLOWED_LINES = ("NetPulseBuildTools",)

#: 行内豁免标记：只有提到旧名的那一行显式携带该标记时才放过。
#:
#: 为什么需要它：文档里有"正当提到旧名"的句子，最典型的是验收要点
#: 「数据目录应为 …，且不应创建旧品牌目录」——它说的是旧目录不该被创建，
#: 语义与品牌残留正好相反。没有豁免机制时这类句子会让门禁长期红灯，而
#: 长期红灯的结果是大家习惯性忽略这条检查，真正的残留反而被漏掉。
#:
#: 为什么用行内标记而不是文件白名单：白名单按整个文件豁免，登记一次就能
#: 让该文件后续所有残留蒙混过关。行内标记把豁免面收敛到单行，同文件里新
#: 增的残留仍然会被抓住，检查强度不降。标记写在 HTML 注释里，Markdown
#: 渲染时不可见，不影响文档可读性。
INLINE_OK_MARK = "brand-ok"

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

    # 版本号第三个来源：i18n 里的 "app.version"。
    # 它曾经是一条死文案（界面版本走 main_window.py 的 f"v{VERSION}"），
    # 却因为长得像"需要同步的地方"而被误改、也一度漏改。现在已删除；
    # 这条检查防止有人再把它加回来——重复的版本来源必然再次不同步。
    stale_version_hits = []
    for name in ("app/i18n_zh.py", "app/i18n_en.py"):
        path = ROOT / name
        if not path.is_file():
            continue
        if re.search(r'"app\.version"\s*:', path.read_text(encoding="utf-8")):
            stale_version_hits.append(name)
    failures += 0 if check("版本号只有一个来源（无 app.version 死文案）",
                           not stale_version_hits, ", ".join(stale_version_hits)) else 1

    # 窗口标题与标语同理：只能在 core/branding.py 定义。
    # app/sysutil.py 曾经硬编码 "LanPulse - 网络体检与优化"（重命名前的旧标语），
    # 而单实例检测正是按这个常量找窗口——标题一旦对不上，二次启动就会静默多开。
    title_violations = []
    for rel in ("app/sysutil.py", "app/i18n_zh.py", "app/i18n_en.py", "main.py",
                "app/ui/main_window.py"):
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        # 允许 import 与注释，只禁止重新定义标题字符串
        if re.search(r'^\s*WINDOW_TITLE\s*=\s*["\']', text, re.M):
            title_violations.append(f"{rel}(WINDOW_TITLE)")
        if re.search(r'"app\.window_title"\s*:', text):
            title_violations.append(f"{rel}(app.window_title)")
    failures += 0 if check("窗口标题只有一个来源（core/branding.py）",
                           not title_violations, ", ".join(title_violations)) else 1

    # Windows 标题必须与 branding 完全一致，否则 FindWindowW 找不到窗口
    try:
        sys.path.insert(0, str(ROOT))
        os.environ.setdefault("PYTHONPATH", ".")
        import importlib

        sysutil = importlib.import_module("app.sysutil")
        same = getattr(sysutil, "WINDOW_TITLE", None) == WINDOW_TITLE
        failures += 0 if check("app.sysutil.WINDOW_TITLE == branding.WINDOW_TITLE",
                               same, f"{getattr(sysutil, 'WINDOW_TITLE', None)!r}") else 1
    except Exception as exc:  # noqa: BLE001 - 导入失败本身就是不一致
        failures += 0 if check("app.sysutil.WINDOW_TITLE == branding.WINDOW_TITLE",
                               False, f"{type(exc).__name__}: {exc}") else 1

    # ---- 3. 品牌名残留 ----
    print("\n[3] 品牌名")
    leftovers = []
    for p in iter_text_files():
        try:
            s = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if OLD_BRAND in s:
            # 逐行判断：既允许兼容性探测路径存在，也放过显式登记为正当
            # 提及旧名的行（行内豁免标记见 INLINE_OK_MARK 的注释）。
            bad = [
                ln for ln in s.splitlines()
                if OLD_BRAND in ln
                and not any(a in ln for a in ALLOWED_LINES)
                and INLINE_OK_MARK not in ln
            ]
            if bad:
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

    # ---- 7. README 内部链接 ----
    # 页内锚点与相对链接最容易在改名后失效，且没人会去点。
    # 曾经两个 README 的「回到顶部」都指向旧品牌的小写锚点，全是断的；
    # 品牌检查没抓到，因为它匹配的是驼峰写法，而锚点全小写。
    print("\n[7] README 内部链接")
    for readme_name in ("README.md", "README_EN.md"):
        p = ROOT / readme_name
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8")
        # 页内锚点：只校验指向本文档标题的纯 #anchor
        anchors = set(re.findall(r"\]\(#([A-Za-z0-9_-]+)\)", txt))
        # GitHub 把标题转成锚点的规则：小写、空格转连字符。
        # 本项目两个 README 的一级标题都是 "LanPulse"，故合法锚点即 lanpulse。
        headings = re.findall(r"^#{1,6}\s+(.+)$", txt, re.M)
        valid = {
            re.sub(r"[^a-z0-9 _-]", "", h.lower()).strip().replace(" ", "-")
            for h in headings
        }
        broken = sorted(a for a in anchors if a not in valid)
        failures += 0 if check(f"{readme_name} 的 {len(anchors)} 个页内锚点有效",
                               not broken, ", ".join(f"#{b}" for b in broken)) else 1

        # 相对链接（不含 scheme 与纯锚点）：文件必须存在
        rel = [m for m in re.findall(r"\]\(([^)#][^)]*)\)", txt)
               if not m.startswith(("http://", "https://", "mailto:"))]
        missing_files = []
        for r in rel:
            target = r.split("#", 1)[0]
            if not target:
                continue
            if not (ROOT / target).exists():
                missing_files.append(r)
        failures += 0 if check(f"{readme_name} 的 {len(rel)} 个相对链接可达",
                               not missing_files,
                               ", ".join(missing_files[:3])) else 1

    # ---- 8. 站点与文档同步 ----
    # 落地页的下载链接把版本号写在文件名里（/releases/latest/download/
    # 需要固定文件名），所以每次发版都必须同步改页面，否则用户点下载会 404。
    # 这里只做"是否一致"的粗检；页面级细节交给 tools/check_site.py。
    print("\n[8] 站点")
    site = ROOT / "site"
    if site.is_dir():
        html_files = sorted(site.rglob("*.html"))
        stale = []
        for page in html_files:
            text = page.read_text(encoding="utf-8")
            for ver in set(re.findall(r"LanPulse-(\d+\.\d+\.\d+)-", text)):
                if ver != VERSION:
                    stale.append(f"{page.relative_to(ROOT)}({ver})")
        failures += 0 if check(
            f"站点 {len(html_files)} 个页面的下载链接版本 == {VERSION}",
            not stale, ", ".join(sorted(set(stale))[:3])) else 1

        # 截图是 docs/images 的副本；不同步会让线上图与 README 不一致
        import hashlib

        out_of_sync = []
        assets = site / "assets"
        for img in sorted((ROOT / "docs" / "images").glob("*.png")):
            copy = assets / img.name
            if not copy.is_file():
                continue                      # 没被站点引用的图不算
            if hashlib.sha256(copy.read_bytes()).hexdigest() != \
                    hashlib.sha256(img.read_bytes()).hexdigest():
                out_of_sync.append(img.name)
        failures += 0 if check("站点截图与 docs/images 一致",
                               not out_of_sync,
                               "先跑 tools/sync_site_assets.py：" + ", ".join(out_of_sync[:3])) else 1

    print("\n" + "=" * 66)
    if failures == 0:
        print("全部通过。")
    else:
        print(f"发现 {failures} 项不一致，需要修复。")
    print("=" * 66)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
