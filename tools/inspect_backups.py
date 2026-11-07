r"""备份会话体检工具（只读诊断，不修改任何文件）。

用途：核实每个备份会话的 manifest 与真实落盘文件是否一致，
尤其是 file_name 中是否残留 Windows 非法字符（会导致 NTFS 交替数据流）。

用法: .\.venv\Scripts\python.exe tools\inspect_backups.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import platform_win as pw  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()


def main() -> int:
    root = os.path.join(pw.app_data_dir(), "backups")
    if not os.path.isdir(root):
        print(f"备份目录不存在：{root}")
        return 0

    names = sorted(os.listdir(root))
    print(f"备份根目录：{root}")
    print(f"会话数：{len(names)}\n")

    problems = 0
    for name in names:
        manifest = os.path.join(root, name, "manifest.json")
        if not os.path.isfile(manifest):
            continue
        with open(manifest, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        print(f"== {name}")
        print(f"   类型：{doc.get('kind')}")
        print(f"   说明：{(doc.get('note') or '')[:90]}")
        for item in doc.get("items", []):
            rel = item.get("file_name", "")
            full = os.path.join(root, name, rel)
            exists = os.path.isfile(full)
            size = os.path.getsize(full) if exists else -1
            has_colon = ":" in rel
            flag = ""
            if has_colon:
                flag = "  <== 文件名含冒号（NTFS ADS）"
                problems += 1
            elif exists and size == 0:
                flag = "  <== 文件为 0 字节"
                problems += 1
            elif not exists:
                flag = "  <== 文件缺失"
                problems += 1
            print(f"   - {item.get('key','')[:30]:<30} {rel[:46]:<46} "
                  f"size={size:<8} {flag}")
        print()

    if problems:
        print(f"发现 {problems} 个异常项。这些会话的备份内容可能不可用于回滚，"
              f"建议删除后重新创建。")
        return 1
    print("全部备份项落盘正常。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
