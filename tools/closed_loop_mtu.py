r"""单独跑 mtu.optimize 的真实闭环（需管理员）。

为什么不直接跑 closed_loop_v12.py：那一轮还要重跑 proxy / firewall / tcp /
hosts / netbios 五项，每项都会真实改一次系统配置。本轮只新增 mtu 一项，
没有理由让另外五项再承担一次风险。

复用 closed_loop_v12 的 run_one 与判决口径（快照D == 快照B、快照E == 快照A），
不复制逻辑——复制出来的第二份判决逻辑迟早会与第一份不一致。

用法（必须管理员）：
    python tools/closed_loop_mtu.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import platform_win as pw  # noqa: E402
from core.backup import BackupStore  # noqa: E402
from core.context import DiagnosticContext  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console  # noqa: E402
_setup_console()

import closed_loop_v12 as base  # noqa: E402


#: 提权启动时 stdout 无法被父进程重定向（Start-Process -Verb RunAs 与
#: -RedirectStandardOutput 互斥），所以由脚本自己把控制台输出抄一份到文件，
#: 父进程读这个文件即可拿到完整日志。
CONSOLE_PATH = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "verify", "closed_loop_mtu_console.log")


class _Tee:
    def __init__(self, *streams) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for s in self._streams:
            try:
                s.write(data)
            except Exception:  # noqa: BLE001 - 控制台写失败不能影响测试
                pass
        return len(data)

    def flush(self) -> None:
        for s in self._streams:
            try:
                s.flush()
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    if not pw.is_elevated():
        print("\n[中止] 需要管理员权限。请以管理员身份运行本脚本。")
        return 2

    os.makedirs(base.OUT_DIR, exist_ok=True)
    open(base.LOG_PATH, "w", encoding="utf-8").close()
    console = open(CONSOLE_PATH, "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, console)
    sys.stderr = _Tee(sys.__stderr__, console)

    base.log("=" * 70)
    base.log("LanPulse 闭环测试：mtu.optimize（单独运行）")
    base.log(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    base.log("=" * 70)

    ctx = DiagnosticContext()
    base._CTX = ctx
    base.log(f"\n权限：管理员　主机：{ctx.hostname}")
    primary = ctx.primary
    if primary is not None:
        base.log(f"主网卡：{primary.name}（ifIndex={primary.if_index}）")
        base.log(f"当前 IP 层 MTU：{base._mtu_now(primary.name)}"
                 f"　链路层 MTU：{primary.link_mtu}")
    base.log(f"构造目标：先造到 {base.MTU_CONSTRUCT}，修复目标 {base.MTU_FIX_TO}")

    store = BackupStore()
    base.log(f"现有备份会话：{len(store.list_sessions())} 个")

    r = base.run_one("mtu.optimize", store, ctx, 1)

    base.log("\n" + "=" * 70)
    base.log("汇总")
    base.log("=" * 70)
    ok = r["applied"] and r["rolled_back"] and r["zero_diff"]
    base.log(f"  {'✓ 通过' if ok else '✗ 未通过'}  mtu.optimize")
    for n in r["notes"]:
        base.log(f"          · {n}")
    base.log(f"\n结果：{1 if ok else 0}/1 项闭环通过")
    return 0 if ok else 6


if __name__ == "__main__":
    sys.exit(main())
