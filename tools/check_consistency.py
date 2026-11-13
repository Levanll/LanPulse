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

import json
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


def _page_count() -> int:
    """界面页数：静态读 main_window 里实际实例化的页面，而不是数文档。

    直接 import app.ui.main_window 会把整个 PySide6 拖进来（慢，且在无显示
    环境可能失败），所以读源码。文档里长期写 "7 个页面"，实际是 9 个——
    因为没人会对着一张目录树图去核对。
    """
    src = ROOT / "app" / "ui" / "main_window.py"
    if not src.is_file():
        return 0
    text = src.read_text(encoding="utf-8")
    # 数实际被放进 stack 的页面实例，而不是数常量：设置页没有 PAGE_ 前缀
    # （它叫 SETTINGS_INDEX），按常量数会少一个，正是文档写 7 个的由来。
    return len(re.findall(r"self\.\w+ = \w+Page\(", text))


def _closed_loop_actions() -> set[str]:
    """从闭环脚本里反推"真正跑过真实闭环"的动作集合。

    文档里的覆盖数没有可靠来源——它是手写的，且手写过一次 10（实际 7）。
    真实来源只有脚本本身：动作出现在闭环脚本的动作清单里，才意味着它被
    执行过 apply + verify + rollback 三轮并留下快照。
    """
    actions: set[str] = set()
    for rel, var in (("tools/closed_loop_test.py", "TEST_ACTIONS"),
                     ("tools/closed_loop_v12.py", "TARGETS")):
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        m = re.search(rf"^{var}\s*=\s*\[(.*?)\]", text, re.S | re.M)
        if not m:
            continue
        actions.update(re.findall(r'"([a-z_]+\.[a-z_]+)"', m.group(1)))
    return actions


def _ver_tuple_ge(left: str, right: str) -> bool:
    """left >= right，按数字分段比较（"1.10.0" > "1.9.0"）。"""
    try:
        return tuple(int(x) for x in left.lstrip("vV").split(".")) >= \
               tuple(int(x) for x in right.lstrip("vV").split("."))
    except ValueError:
        return False


def _count_tests() -> int:
    """静态数出 pytest 收集到的用例数，不真跑 pytest。

    为什么静态数：门禁要在 CI 与本地都够快，跑一遍测试会执行用户环境上的
    真实代码；而"文档里的数字对不对"只需要用例个数。

    **必须展开参数化**：pytest 把 `@pytest.mark.parametrize` 的每个参数组
    各算一个用例。只数 `def test_*` 会数出 135 而实际是 143，两者差 8，
    正是 test_grade_boundaries 那 9 组参数（9-1=8）。
    静态计数与真实结果不一致的门禁，比没有门禁更糟——它会逼着人把文档
    改成错数字。
    """
    total = 0
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # 先数普通用例
        n_func = len(re.findall(r"^\s*def test_\w+\s*\(", text, re.M))
        total += n_func
        # 再把参数化的组数折算进来：每个 parametrize 装饰器把紧随其后的
        # 那个 test 从 1 个展开为 N 个，因此补 (N-1)。
        for m in re.finditer(
                r"@pytest\.mark\.parametrize\([^\[]*\[([\s\S]*?)\]\)\s*\n"
                r"\s*def test_", text):
            body = m.group(1)
            # 每组参数是一个元组或单值，按顶层 (…) / , 计组数
            groups = len(re.findall(r"\([^()]*\)", body))
            if groups == 0:
                groups = len([x for x in body.split(",") if x.strip()])
            total += max(0, groups - 1)
    return total


def _section(text: str, start: str, end: str) -> str:
    """取 text 中 start 之后、end 之前的片段（都找不到就返回空串）。"""
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i)
    return text[i: j if j > 0 else len(text)]


#: 运行期实际执行过的「节」数量。由 section() 在每节真正开始时 +1，
#: 不依赖任何对源码字面量的扫描（那种做法会被注释里的同样文本骗过）。
_SECTIONS_SEEN = 0


def section(title: str) -> None:
    """开始一节：打印小标题并登记。

    所有节都必须通过它进入，否则 [10] 统计到的规模会与真实执行不符。
    """
    global _SECTIONS_SEEN
    _SECTIONS_SEEN += 1
    print(f"\n{title}")


#: 运行期实际执行的子检查数量。文档里的"N 项交叉校验"必须等于它——
#: 这个数字曾长期写作 18，而脚本实际跑 20 项，没人发现，因为没有任何
#: 东西去核对。现在由脚本自己数自己，文档只是被核对的对象。
_CHECKS_RUN = 0


def check(msg: str, ok: bool, detail: str = "") -> bool:
    global _CHECKS_RUN
    _CHECKS_RUN += 1
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
    # 这里不再写死某个过期数字（如 "11 项"），而是把「数字 + 量词」整体抓出来
    # 与真实值比对。写死法漏过一次真实缺陷：README_EN 的 "11 check units"
    # 因为量词是 "check units" 而不是 "checks"，三套死 token 全都没匹配上，
    # 门禁绿灯放行了半年。任何新量词都不该再成为盲区。
    section("[1] 数量声明")
    page_count = _page_count()
    # 严格组：这些措辞只在陈述"总量"时出现，数字必须等于真实值。
    strict = {
        "check": (n_checks, r"(\d+)\s*(?:项检测|个检测单元|个检测项|check units)"),
        "page": (page_count, r"(\d+)\s*(?:个页面|pages)"),
        "action": (n_actions, r"(\d+)\s*(?:个修复动作|个原子动作|atomic actions|reversible actions|reversible fixes)"),
        "scenario": (n_scenarios, r"(\d+)\s*(?:个场景|scenarios)"),
    }
    # 宽松组：`N checks` 既可能是总量，也可能是场景表里的"本场景查 7 项"。
    # 子集必然 ≤ 总量，所以只拦"超过总量"这种不可能值，不拦小的子集。
    loose_max = n_checks
    stale = []
    for p in iter_text_files():
        # 历史记录按定义就是旧的；脚本自身含示例文本
        if p.name in ("CHANGELOG.md", "check_consistency.py"):
            continue
        if p.parent.name == "tools":
            continue
        # 发布说明是不可改写的历史快照，不参与"当前状态"校验
        if "release-notes" in str(p) or "对比分析" in str(p):
            continue
        try:
            s = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for label, (truth, pat) in strict.items():
            for i, line in enumerate(s.splitlines(), 1):
                for m in re.finditer(pat, line):
                    if int(m.group(1)) != truth:
                        stale.append((p.relative_to(ROOT), i, label,
                                      line.strip()[:70]))
        for i, line in enumerate(s.splitlines(), 1):
            for m in re.finditer(r"(?<![\d.])(\d+)\s*checks?\b", line):
                if int(m.group(1)) > loose_max:
                    stale.append((p.relative_to(ROOT), i, "check>max",
                                  line.strip()[:70]))
    failures += 0 if check("文档中的数量声明与实际一致", not stale,
                           f"{len(stale)} 处") else 1
    for item in stale[:10]:
        print(f"         {item[0]}:{item[1]} [{item[2]}]  {item[3]}")

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
    section("[2] 版本号")
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
    section("[3] 品牌名")
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
    section("[4] 数据目录")
    failures += 0 if check(f"数据目录为 {DATA_DIR_NAME}",
                           DATA_DIR_NAME == NAME) else 1

    # ---- 5. 截图与引用 ----
    section("[5] 截图")
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
    section("[6] 国际化")
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
    section("[7] README 内部链接")
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
    section("[8] 站点")
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

    # ---- 9. 闭环实测覆盖 ----
    # 这个数字曾在 HANDOFF 里被写成 10/15，实际只有 7 个动作跑过真实闭环：
    # 把 dns.set_public / dns.flush_cache 在"已测清单"和"另有 dns.* 两项"
    # 里各数了一次。对一个把"诚实边界"当卖点的项目，夸大安全性比漏洞更糟。
    # 唯一来源是闭环脚本里的动作清单，不是文档里的手写数字。
    section("[9] 闭环实测覆盖")
    tested = _closed_loop_actions()
    failures += 0 if check(
        f"闭环脚本覆盖 {len(tested)} / {n_actions} 个动作",
        bool(tested) and all(a in ACTIONS for a in tested),
        "脚本里出现了未登记的动作 id：" +
        ", ".join(sorted(a for a in tested if a not in ACTIONS))) else 1

    # HANDOFF 的"已测"清单必须与脚本完全一致（双向：多写和少写都算错）
    handoff = ROOT / "HANDOFF.md"
    if handoff.is_file():
        text = handoff.read_text(encoding="utf-8")
        m = re.search(r"闭环实测覆盖 (\d+)/(\d+) 个动作", text)
        claimed = int(m.group(1)) if m else -1
        failures += 0 if check(
            f"HANDOFF 声明覆盖 {len(tested)}/{n_actions} 个动作",
            claimed == len(tested) and m and int(m.group(2)) == n_actions,
            f"HANDOFF 写的是 {claimed}，脚本实际 {len(tested)}") else 1

        # 已测清单逐项比对：文档列出的每个 id 必须真在脚本里
        listed = set(re.findall(
            r"`((?:dns|proxy|hosts|tcp|mtu|adapter|firewall|netbios)\.[a-z_]+)`",
            _section(text, "3. **闭环实测覆盖", "未测：")))
        extra = sorted(listed - tested)
        failures += 0 if check("HANDOFF 已测清单与脚本一致", not extra,
                               ", ".join(extra)) else 1

    # ---- 10. 测试数量 ----
    # "140 项测试"曾长期写死在 HANDOFF 四处，实际早已是 143。
    # 与其它数字同理：不手写，从测试源码数出来。
    section("[10] 测试数量")
    n_tests = _count_tests()
    if n_tests:
        print(f"         实际用例：{n_tests} 项")
        handoff = ROOT / "HANDOFF.md"
        if handoff.is_file():
            claimed = {int(n) for n in
                       re.findall(r"(\d+)\s*项测试", handoff.read_text(encoding="utf-8"))}
            claimed |= {int(n) for n in re.findall(
                r"pytest tests -q\s*\|\s*(\d+) 项",
                handoff.read_text(encoding="utf-8"))}
            failures += 0 if check(
                f"HANDOFF 的测试数与实际一致（{n_tests}）",
                claimed == {n_tests},
                f"HANDOFF 写的是 {sorted(claimed) or '未找到'}") else 1

    # ---- 11. 更新清单 ----
    # site/latest.json 是更新检测的唯一数据源。它一旦与 branding.VERSION
    # 脱节，用户就永远收不到（或永远收到）更新提示，而且不会有任何报错。
    section("[11] 更新清单")
    manifest_path = ROOT / "site" / "latest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            manifest = None
            failures += 0 if check("site/latest.json 可解析", False, str(exc)) else 1
        if isinstance(manifest, dict):
            failures += 0 if check(
                "site/latest.json 可解析", True) else 1
            mver = str(manifest.get("version") or "")
            # 清单版本不得低于当前版本：低于意味着发版时忘了更新，
            # 所有用户都会收到"有新版本"却指向已发布的旧版。
            ok = bool(mver) and _ver_tuple_ge(mver, VERSION)
            failures += 0 if check(
                f"清单版本 {mver or '缺失'} >= 当前 {VERSION}", ok,
                "发版时必须同步更新 site/latest.json") else 1
            url = str(manifest.get("url") or "")
            failures += 0 if check(
                "清单 url 为 https", url.startswith("https://"), url) else 1
            # 双语文案 key 必须齐全（可为空串，但字段得存在）
            missing = [k for k in ("notes_zh", "notes_en", "mandatory")
                       if k not in manifest]
            failures += 0 if check("清单含双语字段", not missing,
                                   ", ".join(missing)) else 1
    else:
        failures += 0 if check("site/latest.json 存在", False) else 1

    # ---- 12. 门禁自身规模 ----
    # 文档长期写"18 项"，而脚本实际跑 20 项且从未被核对过。根因是
    # "项"这个单位本身模糊：它既可以是"节"，也可以是"子检查"。
    # 现在对外口径统一为**节数**（结构稳定），子检查数一并打印但不管制。
    section("[12] 门禁自身规模")
    # 只认**真的执行过**的节：section() 每被调用一次就登记一次。
    # 这里绝不能去数源码里的 print("\n[N] ...") 字面量——注释里写一句
    # 同一段文字就会被算成一节。上一版正是如此：第 449 行那条解释性注释
    # 抵消了第 [1] 节漏写的前导 "\n"，凑巧还得出了正确的 10，
    # 于是"数字对得上"这件事本身失去了意义。
    n_sections = _SECTIONS_SEEN
    print(f"         共 {n_sections} 节 / {_CHECKS_RUN + 1} 项子检查")
    handoff = ROOT / "HANDOFF.md"
    if handoff.is_file():
        text = handoff.read_text(encoding="utf-8")
        claimed = {int(n) for n in re.findall(r"(\d+)\s*节交叉校验", text)}
        failures += 0 if check(
            f"文档声明的节数 == 实际的 {n_sections} 节",
            claimed == {n_sections},
            f"文档写的是 {sorted(claimed) or '未找到'}") else 1

    print("\n" + "=" * 66)
    if failures == 0:
        print("全部通过。")
    else:
        print(f"发现 {failures} 项不一致，需要修复。")
    print("=" * 66)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
