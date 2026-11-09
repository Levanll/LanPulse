"""把落地页需要的静态资源从 docs/images/ 同步到 site/assets/。

为什么复制而不是在 HTML 里直接引用 ../docs/images/：

1. GitHub Pages 的发布源若设为 site/ 目录，上级目录根本不在站点里，
   引用会 404；
2. 即使发布源是仓库根，把 docs/ 也暴露成网站路径会让内部设计文档、
   实测报告里的本机信息（项目路径等）可被公开访问。

因此站点资产必须是自包含的一份。但"复制"带来同步风险，所以这个脚本
是唯一入口：截图重新生成后跑一次即可，并在 check_consistency.py 里校验
两边的 SHA256 一致，防止忘了同步。
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "docs" / "images"
DST = ROOT / "site" / "assets"

#: 落地页实际引用到的图。只同步用到的，避免把 20 张图全搬过去。
NEEDED = (
    "hero-banner-zh.png",
    "hero-banner-en.png",
    "screenshot-dashboard.png",
    "screenshot-dashboard-en.png",
    "screenshot-scenario.png",
    "screenshot-scenario-en.png",
    "screenshot-diagnose.png",
    "screenshot-diagnose-en.png",
    "screenshot-repair.png",
    "screenshot-repair-en.png",
    "screenshot-backup.png",
    "screenshot-backup-en.png",
    "screenshot-settings-zh.png",
    "screenshot-settings-en.png",
)

FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
<rect width="32" height="32" rx="7" fill="#0b0f14"/>
<circle cx="16" cy="16" r="4" fill="#00e5a0"/>
<circle cx="16" cy="16" r="9" fill="none" stroke="#0aa97b" stroke-width="2"
        stroke-dasharray="3 4"/>
</svg>
"""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not SRC.is_dir():
        print(f"[X] 源目录不存在：{SRC}")
        return 2
    DST.mkdir(parents=True, exist_ok=True)

    copied, missing = 0, []
    for name in NEEDED:
        src = SRC / name
        if not src.is_file():
            missing.append(name)
            continue
        dst = DST / name
        if dst.is_file() and sha256(dst) == sha256(src):
            continue                      # 已是最新，不动文件时间戳
        shutil.copy2(src, dst)
        copied += 1

    fav = DST / "favicon.svg"
    if not fav.is_file() or fav.read_text(encoding="utf-8") != FAVICON:
        fav.write_text(FAVICON, encoding="utf-8", newline="\n")

    print(f"[OK] 同步完成：复制 {copied} 个文件，跳过 {len(NEEDED) - copied - len(missing)} 个未变化的")
    if missing:
        print(f"[!] 源文件缺失：{missing}")
        return 3
    print(f"    目标目录：{DST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
