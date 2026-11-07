r"""修复链路端到端验证（只读 + dry-run，绝不改系统）。

覆盖：
  1. plan() 对全部 15 个 action_id 的规划与预览能力
  2. mtu.optimize 缺 target_mtu 必须抛 ValueError
  3. dns.set_public 的非法 servers 必须被拒绝
  4. execute(dry_run=True) 创建备份会话且不修改系统
  5. rollback 对空/无需修复会话的安全处理

用法: .\.venv\Scripts\python.exe tools\verify_repair.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.action_ids import ACTIONS
from core.context import DiagnosticContext
from core.repair import engine as E

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()


def main() -> int:
    ctx = DiagnosticContext()
    print(f"权限：{'管理员' if ctx.elevated else '普通用户'}；主机：{ctx.hostname}")
    print(f"已登记动作：{len(ACTIONS)} 个\n")

    eng = E.RepairEngine(dry_run=True)

    # ---- 1. 全量规划（跳过需要参数的 mtu，单独测） ----
    safe_ids = [a for a in ACTIONS if a != "mtu.optimize"]
    plan = eng.plan(safe_ids, ctx)
    print(f"[1] plan() 输入 {len(safe_ids)} 个动作")
    print(f"    实际纳入 {len(plan.actions())} 个，剔除 {len(plan.skipped_action_ids)} 个")
    if plan.notes:
        for n in plan.notes:
            print(f"    备注：{n}")

    previews = eng.preview_all(plan, ctx)
    print(f"[2] preview_all() 生成 {len(previews)} 条预览")
    for p in previews[:6]:
        print(f"    - {p.target[:46]:<46} {p.before[:22]:>22} -> {p.after[:26]}")
    if len(previews) > 6:
        print(f"    … 另有 {len(previews) - 6} 条")

    # ---- 3. 参数校验必须拒绝 ----
    print("\n[3] 参数校验（期望全部抛 ValueError）")
    checks = [
        ("mtu.optimize 缺参", lambda: eng.plan(["mtu.optimize"], ctx)),
        ("mtu.optimize 超范围", lambda: eng.plan([("mtu.optimize", {"target_mtu": 9000})], ctx)),
        ("dns.set_public 空列表", lambda: eng.plan(["dns.set_public"], ctx, servers=[])),
        ("dns.set_public 非法 IP", lambda: eng.plan(["dns.set_public"], ctx, servers=["999.1.1.1"])),
    ]
    failures = 0
    for name, fn in checks:
        try:
            fn()
            print(f"    ✗ {name}：未抛异常（缺陷）")
            failures += 1
        except ValueError as exc:
            print(f"    ✓ {name}：{str(exc)[:62]}")
        except Exception as exc:  # noqa: BLE001
            print(f"    ? {name}：抛了 {type(exc).__name__}（应为 ValueError）: {exc}")
            failures += 1

    # ---- 4. dry-run 全链路 ----
    print("\n[4] dry-run 执行（不修改系统）")
    order = []
    rep = eng.execute(
        plan, ctx,
        progress=lambda i, t, aid, ph: order.append((i, t, aid, ph)),
    )
    print(f"    session_id = {rep.session_id}")
    print(f"    备份路径   = {rep.session_path}")
    print(f"    结果：成功 {rep.ok_count} / 失败 {rep.fail_count} / 跳过 {rep.skipped_count}")
    print(f"    dry_run={rep.dry_run}, partial={rep.partial}, aborted={rep.aborted}")
    phases = {ph for _, _, _, ph in order}
    print(f"    进度回调阶段集合 = {sorted(phases)}（应为 backup 加可能 verify）")
    if order:
        print(f"    回调样例 = {order[0]}")

    # 确认备份真的落盘
    from core.backup import BackupStore

    store = BackupStore()
    loaded = store.load(rep.session_id)
    print(f"    备份会话可读回：{loaded.session_id}，items={len(loaded.items)}")
    for it in loaded.items:
        print(f"      · [{it.kind}] {it.label}")

    # ---- 5. 空动作 rollback 不应崩 ----
    print("\n[5] 回滚 dry-run 会话（应安全处理，不真实改配置）")
    try:
        rb = eng.rollback(rep.session_id, ctx)
        print(f"    回滚结果：成功 {rb.ok_count} / 失败 {rb.fail_count}")
        for r in rb.results[:5]:
            print(f"      · {r.action_id}: {r.state.value} {r.message[:46]}")
    except Exception as exc:  # noqa: BLE001
        print(f"    ✗ 回滚抛异常：{type(exc).__name__}: {exc}")
        failures += 1

    print("\n" + ("全部检查通过" if failures == 0 else f"有 {failures} 项不符合预期"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
