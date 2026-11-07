r"""跨区域验证：在三种区域剖面下跑检测，确认探测目标真的跟着切换。

用法: .\.venv\Scripts\python.exe tools\verify_regions.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.context import DiagnosticContext
from core.registry import load_checks, run_check

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()


def main() -> int:
    print("自动识别结果：")
    ctx_auto = DiagnosticContext()
    key = ctx_auto.region_key
    print(f"  region = {key}")
    for k, v in ctx_auto.region_evidence.items():
        print(f"    {k} = {v}")
    print()

    checks = load_checks()
    targets = {"connectivity", "dns_resolve", "mtu"}
    for region in ("cn", "global", "apac"):
        ctx = DiagnosticContext(region_override=region)
        prof = ctx.profile
        print(f"===== region={region}")
        print(f"  resolve_domains = {prof.resolve_domains}")
        print(f"  ping_target     = {prof.ping_targets[0][0]}")
        print(f"  mtu_target      = {prof.mtu_target}")
        print(f"  primary_dns     = {prof.dns_plans[0].servers}")
        for chk in checks:
            if chk.check_id not in targets:
                continue
            r = run_check(chk, ctx)
            print(f"  {r.check_id:<13} {r.severity.value:<7} {r.duration_ms:>5}ms | {r.summary[:64]}")
        print()

    # 验证探测目标真的变了（不是只改了文档）
    cns = DiagnosticContext(region_override="cn").profile
    glb = DiagnosticContext(region_override="global").profile
    assert cns.resolve_domains != glb.resolve_domains, "解析域名未随区域切换"
    assert cns.ping_targets != glb.ping_targets, "ping 目标未随区域切换"
    assert cns.mtu_target != glb.mtu_target, "MTU 目标未随区域切换"
    assert cns.dns_plans[0].servers != glb.dns_plans[0].servers, "DNS 方案未随区域切换"
    print("断言通过：解析域名 / ping 目标 / MTU 目标 / DNS 方案 均随区域切换。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
