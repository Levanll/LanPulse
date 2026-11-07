r"""品牌改名：LanPulse → LanPulse。

关键约束（不能一律替换）：
  1. **用户数据目录必须保留旧名** `LanPulse`
     —— 改名后若换了目录，已备份的网络配置会"消失"，这违反
        "备份可随时还原"的承诺。branding.DATA_DIR_NAME 显式固定为旧名。
  2. **安装器 AppId 必须固定**，否则 Windows 会把新版本当成另一个产品，
     导致重复卸载项。AppId 是 GUID，不含产品名，不受影响。
  3. 仓库地址里的 owner 不变（Levanll），只改仓库名。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 扫描范围
PATTERNS = ("*.py", "*.md", "*.iss", "*.ps1", "*.yml", "*.spec", "*.txt", "*.isl")
SKIP_DIRS = {".venv", "dist", "release", ".git", "__pycache__", ".pytest_cache"}

#: 这些行里的 LanPulse **不能改**（用户数据目录 / 兼容性原因）
PROTECTED_MARKERS = (
    'DATA_DIR_NAME = "NetPulse"',
    "DATA_DIR_NAME",                    # 任何提到数据目录名的行
    "NetPulse_Global_Mutex",            # 单实例互斥体名改了会让新旧版本同时启动
    "%LOCALAPPDATA%\\LanPulse",         # 文档里描述用户数据位置
    "LOCALAPPDATA\\LanPulse",
)


def _should_skip_line(line: str) -> bool:
    return any(m in line for m in PROTECTED_MARKERS)


def rename_in_file(path: pathlib.Path) -> int:
    """替换文件里的 LanPulse → LanPulse，跳过受保护的行。"""
    text = path.read_text(encoding="utf-8", errors="surrogateescape")
    lines = text.splitlines(keepends=True)
    changed = 0

    for i, line in enumerate(lines):
        if "LanPulse" not in line:
            continue
        if _should_skip_line(line):
            continue
        new = line.replace("LanPulse", "LanPulse")
        if new != line:
            lines[i] = new
            changed += 1

    if changed:
        path.write_text("".join(lines), encoding="utf-8", errors="surrogateescape")
    return changed


def rename_files() -> list[tuple[str, str]]:
    """重命名文件名里含 LanPulse 的文件。"""
    renames: list[tuple[str, str]] = []
    for old, new in (
        ("installer/LanPulse.iss", "installer/LanPulse.iss"),
        ("installer/LanPulse.ico", "installer/LanPulse.ico"),
    ):
        src, dst = ROOT / old, ROOT / new
        if src.is_file():
            src.rename(dst)
            renames.append((old, new))
    return renames


def main() -> int:
    renames = rename_files()
    if renames:
        print("重命名文件：")
        for old, new in renames:
            print(f"  {old} → {new}")

    total = 0
    files = 0
    for pattern in PATTERNS:
        for path in ROOT.rglob(pattern):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            n = rename_in_file(path)
            if n:
                total += n
                files += 1
                print(f"  {n:>3} 处  {path.relative_to(ROOT)}")

    print(f"\n共替换 {total} 处，涉及 {files} 个文件。")

    # 校验：受保护内容是否还在
    brands = (ROOT / "core" / "branding.py").read_text(encoding="utf-8")
    if 'DATA_DIR_NAME = "NetPulse"' not in brands:
        print("警告：DATA_DIR_NAME 被改动，老用户备份将找不到！")
        return 1
    print("✓ 数据目录名保持不变（老备份仍可还原）")

    # 校验：品牌常量已更新
    if 'NAME = "LanPulse"' not in brands:
        print("警告：branding.NAME 未更新")
        return 1
    print("✓ branding.NAME 已是 LanPulse")
    return 0


if __name__ == "__main__":
    sys.exit(main())
