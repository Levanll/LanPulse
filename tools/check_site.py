r"""站点自检：部署前挡住页面层面的常见错误。

本工具存在的原因与 check_consistency.py 相同——手工维护的静态页面必然
漂移，而没人会主动去点每个链接。检查项：

  1. 页面引用的本地资源（图片/CSS/JS）必须存在，且相对路径在 Pages 的
     目录结构下能解析（site/ 是站点根，en/ 是多一层）；
  2. 页面里写死的版本号必须与 core/branding.py 一致——否则发版后
     下载链接会指向不存在的文件；
  3. 下载链接的文件名必须与 installer 实际产出的命名一致；
  4. 双语页面必须互相链接（缺一侧用户会困在单语页面）；
  5. 站点必需文件齐全（index.html / style.css / en/index.html / favicon）。

用法：python tools/check_site.py
"""
from __future__ import annotations

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

from core.branding import VERSION  # noqa: E402

SITE = ROOT / "site"

REQUIRED = (
    "index.html",
    "style.css",
    "en/index.html",
    "assets/favicon.svg",
)

failures = 0


def check(msg: str, ok: bool, detail: str = "") -> bool:
    global failures
    mark = "[OK]  " if ok else "[FAIL]"
    print(f"  {mark} {msg}")
    if detail and not ok:
        print(f"         {detail}")
        failures += 1
    return ok


def local_refs(html: str) -> list[str]:
    """提取页面里所有本地资源引用（img src / link href / script src）。"""
    refs: list[str] = []
    for m in re.finditer(r'<img[^>]+src="([^"]+)"', html):
        refs.append(m.group(1))
    for m in re.finditer(r'<link[^>]+href="([^"]+)"', html):
        refs.append(m.group(1))
    for m in re.finditer(r'<script[^>]+src="([^"]+)"', html):
        refs.append(m.group(1))
    return refs


def resolve(page: Path, ref: str) -> Path | None:
    """把页面里的相对引用解析成磁盘路径。外链返回 None。"""
    if ref.startswith(("http://", "https://", "//", "mailto:", "#", "data:")):
        return None
    target = (page.parent / ref).resolve()
    if target.is_dir():
        target = target / "index.html"
    return target


def main() -> int:
    print("=" * 60)
    print("LanPulse 站点自检")
    print("=" * 60)

    if not SITE.is_dir():
        print(f"[X] site 目录不存在：{SITE}")
        return 2

    # ---- 1. 必需文件 ----
    print("\n[1] 必需文件")
    for rel in REQUIRED:
        p = SITE / rel
        check(f"site/{rel}", p.is_file())

    pages = [p for p in (SITE / "index.html", SITE / "en" / "index.html") if p.is_file()]

    # ---- 2. 本地资源可解析 ----
    print("\n[2] 本地资源引用")
    for page in pages:
        html = page.read_text(encoding="utf-8")
        rel_page = page.relative_to(ROOT)
        missing = []
        checked = 0
        for ref in local_refs(html):
            target = resolve(page, ref)
            if target is None:
                continue
            checked += 1
            if not target.is_file():
                missing.append(f"{ref} -> {target}")
        check(f"{rel_page} 的 {checked} 个本地资源全部存在",
              not missing, "；".join(missing[:4]))

    # ---- 3. 版本号一致 ----
    print("\n[3] 版本号")
    # Pages 用 /releases/latest/download/<固定文件名>，文件名带版本号，
    # 因此页面里的版本必须与 branding 完全一致，否则下载会 404。
    want_setup = f"LanPulse-{VERSION}-Setup.exe"
    want_zip = f"LanPulse-{VERSION}-win64-portable.zip"
    for page in pages:
        html = page.read_text(encoding="utf-8")
        rel_page = page.relative_to(ROOT)
        found_versions = set(re.findall(r"LanPulse-(\d+\.\d+\.\d+)-", html))
        stale = sorted(v for v in found_versions if v != VERSION)
        check(f"{rel_page} 只引用当前版本 {VERSION}",
              not stale, f"出现了旧版本：{stale}")

    # 下载链接的文件名必须与 installer 的产物命名规则一致
    iss = (ROOT / "installer" / "LanPulse.iss").read_text(encoding="utf-8")
    m = re.search(r'^\s*OutputBaseFilename\s*=\s*(\S+)', iss, re.M)
    if m:
        base = m.group(1).replace("{#MyAppVersion}", VERSION)
        check(f"安装包名与 installer 一致（{base}.exe）",
              want_setup == f"{base}.exe",
              f"页面写的是 {want_setup}")
    for page in pages:
        html = page.read_text(encoding="utf-8")
        if "releases/latest/download" in html:
            check(f"{page.relative_to(ROOT)} 的下载链接含当前版本",
                  (want_setup in html) and (want_zip in html),
                  f"期望 {want_setup} 与 {want_zip}")

    # ---- 4. 双语互链 ----
    print("\n[4] 双语互链")
    zh = (SITE / "index.html")
    en = (SITE / "en" / "index.html")
    if zh.is_file() and en.is_file():
        zh_html = zh.read_text(encoding="utf-8")
        en_html = en.read_text(encoding="utf-8")
        check("中文页链到 English", 'href="en/"' in zh_html)
        check("英文页链回中文", 'href="../"' in en_html)
        # 语言标记要与内容语言一致，否则屏幕阅读器与搜索引擎会误判
        check("lang 属性正确",
              'lang="zh-CN"' in zh_html and 'lang="en"' in en_html)

    # ---- 5. 页面没有引用站点外的本地路径 ----
    # 从 site/ 里往外交（../docs/...）在 Pages 上必然 404，
    # 因为站点根就是 site/。
    print("\n[5] 越界引用")
    for page in pages:
        html = page.read_text(encoding="utf-8")
        escapes = [r for r in local_refs(html) if r.startswith("../docs/")
                   or r.startswith("../core/") or r.startswith("../tools/")]
        check(f"{page.relative_to(ROOT)} 未引用站点外资源",
              not escapes, "；".join(escapes[:4]))

    print("\n" + "=" * 60)
    if failures == 0:
        print("全部通过。")
    else:
        print(f"发现 {failures} 项问题，需要修复。")
    print("=" * 60)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
