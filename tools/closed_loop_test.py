r"""「执行修复 → 回滚」闭环测试（真实修改系统，需管理员权限）。

设计原则：
  1. **只选能完整回滚的动作**。`dns.set_public` 备份原 DNS 列表 + was_dhcp，
     回滚可精确还原；`dns.flush_cache` 无状态、天然可复现。
  2. **每一步都抓快照**，用 `tools/snapshot_net.py --diff` 做机器判决，
     不靠人眼看。
  3. **回滚后必须与基线完全一致**，任何差异都要人工确认原因。
  4. 全程写 `verify/closed_loop.log`，失败也能追溯。

流程：
    before 快照 → dry-run（验证备份链路）→ 真实 apply → after 快照（确认真的改了）
    → rollback → restored 快照 → 与 before 逐项比对

用法（必须管理员）：
    python tools/closed_loop_test.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import platform_win as pw  # noqa: E402
from core.backup import BackupStore  # noqa: E402
from core.context import DiagnosticContext  # noqa: E402
from core.i18n import set_language, t  # noqa: E402
from core.repair import engine as E  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verify")

#: 本轮测试使用的动作。
#: dns.set_public 是"真实改写系统配置且可完整回滚"的最佳样本：
#: 它修改网卡 DNS（有明确的前后状态），备份记录原列表与是否 DHCP，
#: 回滚能精确还原。dns.flush_cache 无持久状态，用来验证"无备份项动作"
#: 也能正常进出流程。
TEST_ACTIONS = ["dns.set_public", "dns.flush_cache"]
TEST_SERVERS = ["9.9.9.9", "149.112.112.112"]  # Quad9：与当前阿里系明显不同，便于肉眼识别


def log(msg: str) -> None:
    """写日志。

    提权后的 cmd 窗口默认是 GBK 代码页，直接 print 含非 GBK 字符
    （如某些引号、箭头）会抛 UnicodeEncodeError 中断整个测试。
    这里对控制台输出做兜底编码，日志文件始终写 UTF-8。
    """
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))
    with open(os.path.join(OUT_DIR, "closed_loop.log"), "a", encoding="utf-8") as fh:
        fh.write(msg + "\n")


def snapshot(name: str) -> str:
    path = os.path.join(OUT_DIR, name)
    subprocess.run(
        [sys.executable, os.path.join(OUT_DIR, "..", "tools", "snapshot_net.py"), path],
        check=True, capture_output=True, encoding="utf-8", errors="replace",
    )
    return path


def diff(a: str, b: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, os.path.join(OUT_DIR, "..", "tools", "snapshot_net.py"),
         "--diff", a, b],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def show_plan(plan) -> None:
    log(f"  纳入动作 {len(plan.actions())} 个，剔除 {len(plan.skipped_action_ids)} 个")
    for n in plan.notes:
        log(f"    备注：{n}")
    for aid in plan.action_ids:
        log(f"    - {aid}")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    # 提权后的控制台是 GBK，把标准输出强制成可容错，避免日志打印中断测试
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    open(os.path.join(OUT_DIR, "closed_loop.log"), "w", encoding="utf-8").close()
    set_language("zh")

    log("=" * 70)
    log("LanPulse 闭环测试：执行修复 → 回滚")
    log(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    if not pw.is_elevated():
        log("\n[中止] 需要管理员权限。请以管理员身份运行本脚本。")
        log("  原因：修改网卡 DNS 需要提权，非管理员下 apply 会失败，")
        log("        无法验证真实的『改成功 → 还原成功』。")
        return 2

    ctx = DiagnosticContext()
    log(f"\n权限：管理员　主机：{ctx.hostname}")
    primary = ctx.primary
    if primary is None:
        log("[中止] 未找到主网卡")
        return 2
    log(f"主网卡：{primary.name}（ifIndex={primary.if_index}）")
    log(f"当前 DNS：{primary.dns_v4}")

    store = BackupStore()
    sessions_before = len(store.list_sessions())
    log(f"现有备份会话：{sessions_before} 个")

    # ---------------- 1. 基线快照 ----------------
    log("\n[1] 抓取基线快照")
    before = snapshot("10_before.json")
    log(f"    {before}")

    # ---------------- 2. dry-run ----------------
    log("\n[2] dry-run（验证备份链路，不改系统）")
    eng_dry = E.RepairEngine(store=store, dry_run=True)
    plan = eng_dry.plan(TEST_ACTIONS, ctx, servers=TEST_SERVERS)
    show_plan(plan)
    dry_report = eng_dry.execute(plan, ctx)
    log(f"    dry_run={dry_report.dry_run} aborted={dry_report.aborted} "
        f"session={dry_report.session_id}")
    log(f"    备份路径：{dry_report.session_path}")
    dry_session = store.load(dry_report.session_id)
    log(f"    备份项：{len(dry_session.items)} 个")
    for it in dry_session.items:
        log(f"      · [{it.kind}] {it.label}")

    # dry-run 不得改动系统
    mid = snapshot("20_after_dryrun.json")
    code, out = diff(before, mid)
    log(f"    dry-run 后与基线差异：{'无' if code == 0 else '有差异'}")
    if code != 0:
        log(out)
        log("[中止] dry-run 竟然改动了系统，这是严重缺陷，停止后续真实执行。")
        return 3

    # ---------------- 3. 真实执行 ----------------
    log("\n[3] 真实执行修复（会修改网卡 DNS）")
    eng = E.RepairEngine(store=store, dry_run=False)
    real_plan = eng.plan(TEST_ACTIONS, ctx, servers=TEST_SERVERS)
    phases: list[tuple] = []
    report = eng.execute(
        real_plan, ctx,
        progress=lambda i, n, aid, ph: phases.append((i, n, aid, ph)),
    )
    log(f"    session     = {report.session_id}")
    log(f"    备份路径    = {report.session_path}")
    log(f"    成功/失败/跳过 = {report.ok_count}/{report.fail_count}/{report.skipped_count}")
    log(f"    partial={report.partial} aborted={report.aborted}")
    if report.aborted:
        log(f"    中止原因：{report.abort_reason}")
        return 4
    log("    执行明细：")
    for r in report.results:
        log(f"      · {r.action_id}: {r.state.value}  verified={r.verified}  {r.message[:60]}")
        if r.error:
            log(f"        错误：{r.error[:200]}")
    log(f"    进度回调阶段：{sorted({p[3] for p in phases})}")

    real_session = store.load(report.session_id)
    log(f"    实际备份项：{len(real_session.items)} 个")
    for it in real_session.items:
        log(f"      · [{it.kind}] {it.label}  payload={json.dumps(it.payload, ensure_ascii=False)[:120]}")

    # ---------------- 4. 确认真的改了 ----------------
    log("\n[4] 抓取执行后快照，确认系统确实被修改")
    after = snapshot("30_after_apply.json")
    code, out = diff(before, after)
    log(out)
    if code == 0:
        log("[失败] 执行后系统状态与基线相同 —— 说明 apply 实际没生效（假成功）。")
        log("       这是必须修复的缺陷，不进入回滚阶段。")
        return 5
    log("    ✓ 系统状态已改变，apply 确实生效")

    # 读回当前 DNS 供人眼确认
    adapters_now = pw.collect_adapters()
    prim_now = pw.primary_adapter(adapters_now)
    log(f"    当前 DNS 实测：{prim_now.dns_v4 if prim_now else '无'}")

    # ---------------- 5. 回滚 ----------------
    log("\n[5] 回滚")
    rb = eng.rollback(report.session_id, ctx)
    log(f"    回滚结果：成功 {rb.ok_count} / 失败 {rb.fail_count} / 跳过 "
        f"{getattr(rb, 'skipped_count', '?')}")
    for r in rb.results:
        log(f"      · {r.action_id}: {r.state.value}  {r.message[:70]}")
        if r.error:
            log(f"        错误：{r.error[:200]}")

    # ---------------- 6. 比对还原 ----------------
    log("\n[6] 抓取回滚后快照，与基线逐项比对")
    restored = snapshot("40_after_rollback.json")
    code, out = diff(before, restored)
    log(out)

    log("\n" + "=" * 70)
    if code == 0:
        log("结论：闭环通过 —— 执行生效、回滚完全还原，与基线零差异。")
        result = 0
    else:
        log("结论：回滚后仍有差异，需要人工核查上面列出的项目。")
        result = 6
    log("=" * 70)
    return result


if __name__ == "__main__":
    sys.exit(main())
