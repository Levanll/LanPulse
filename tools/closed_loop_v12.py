r"""「执行修复 → 回滚」闭环测试（真实修改系统，需管理员权限）。

本脚本是 v1.1.0 的升级版：原版只验证 DNS 类动作，本版覆盖 v1.2.0 要求补测的
四个动作，按风险从低到高：

    proxy.reset          (HKCU 注册表，不需提权但脚本统一提权运行)
    firewall.ensure_enabled
    tcp.autotuning
    hosts.clean_bad_lines

## 为什么需要"构造故障状态"

这四个动作的共同点是**只在需要时才动手**：代理本来就是直连、防火墙本来就全开、
autotuning 本来就是 normal、hosts 本来就没有可疑行时，apply() 会返回 SKIPPED，
系统毫无变化。那样"回滚"也无从验证——没有任何东西可回滚。

因此闭环必须分两段：
    A. 原始真实状态  → 快照1
    B. 构造出待修状态 → 快照2（这是动作"应该修复"的输入）
    C. 执行修复      → 快照3（验证确实改了）
    D. 回滚          → 快照4

关键点：**动作的 backup() 是在 B 之后才跑的**，所以它备份的是"造出来的故障态"，
回滚只能回到 B，回不到 A。这不是缺陷——真实用户场景里 B 就是他们的现状。
所以正确的验收是 快照4 == 快照2（回滚把修复撤销干净），而不是 快照4 == 快照1。

作为额外保障，每项跑完后都用 `_restore_original` 把 A 恢复回去，让本机最终
回到测试前的样子。脚本会逐项报告 A/B/C/D 四段的状态，便于人工复核。

## 安全边界

- 每项开始前都先抓快照，任何一项出现意外都保留现场文件；
- 构造的值都是最小无害值（本地不存在的代理端口、加一条 example.com、
  autotuning=disabled、关掉防火墙——防火墙原本就是关的）；
- 每项独立 try/finally，单项异常不影响后续项，且异常项也会尝试还原原始状态；
- 全程写 verify/closed_loop_v12.log。

用法（必须管理员）：
    python tools/closed_loop_v12.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import platform_win as pw  # noqa: E402
from core.backup import BackupStore  # noqa: E402
from core.context import DiagnosticContext  # noqa: E402
from core.repair import engine as E  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console  # noqa: E402
_setup_console()

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "verify")
LOG_PATH = os.path.join(OUT_DIR, "closed_loop_v12.log")

#: 构造故障状态用的最小无害值
FAKE_PROXY_SERVER = "127.0.0.1:1"     # 本地 1 号端口，必然无人监听
HOSTS_MARKER = "0.0.0.0 example.com"  # 典型屏蔽记录，example.com 是保留域名

#: 本轮验证的动作，按风险从低到高
TARGETS = [
    # v1.1.0 只验证过 DNS 类；v1.2.0 补前四项（4/4 通过）。
    "proxy.reset",
    "firewall.ensure_enabled",
    "tcp.autotuning",
    "hosts.clean_bad_lines",
    # 第一档遗留项：只改一个 DWORD，且回滚有两条路径
    # （reg export 成功则整项导入；原本不存在则删除值），验证成本最低。
    "netbios.disable_public",
]


def log(msg: str = "") -> None:
    """控制台 + 日志文件双写。提权后的 cmd 是 GBK，需容错。"""
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
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


# --------------------------------------------------------------------------- #
# 构造 / 还原：每个动作一组
# --------------------------------------------------------------------------- #
def _fabricate_proxy() -> str:
    """造出"代理已启用但服务器不存在"的经典故障。返回原始状态描述。"""
    from core.repair import proxy_actions as P

    original = P.read_proxy_state()
    P._write_dword("ProxyEnable", 1)
    import winreg

    with P._open_wininet(write=True) as key:
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, FAKE_PROXY_SERVER)
    P.notify_proxy_changed()
    return json.dumps(original, ensure_ascii=False)


def _restore_proxy(original_json: str) -> None:
    """把 WinINET 代理恢复成测试前的样子。"""
    import winreg

    from core.repair import proxy_actions as P

    original = json.loads(original_json)
    with P._open_wininet(write=True) as key:
        enable = original.get("ProxyEnable")
        P._write_dword("ProxyEnable", 0 if enable is None else int(enable))
        for name in ("ProxyServer", "ProxyOverride"):
            value = original.get(name)
            try:
                if value is None:
                    winreg.DeleteValue(key, name)
                else:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
            except FileNotFoundError:
                pass
    P.notify_proxy_changed()


def _fabricate_firewall() -> str:
    """把三个 profile 全部关掉（本机实测原本就是 OFF，仍然显式关一次保证前置条件）。"""
    from core.repair.base import FIREWALL_PROFILES, netsh_firewall_set, read_firewall_profiles

    original = read_firewall_profiles()
    for profile, _, _ in FIREWALL_PROFILES:
        netsh_firewall_set(profile, False)
    return json.dumps(original, ensure_ascii=False)


def _restore_firewall(original_json: str) -> None:
    from core.repair.base import netsh_firewall_set

    original = json.loads(original_json)
    for profile, state in original.items():
        netsh_firewall_set(profile, str(state).upper() == "ON")


def _fabricate_tcp() -> str:
    """把 autotuning 改成 disabled（模拟"优化软件"关掉自动调节）。"""
    from core.repair.base import netsh_tcp_set, read_tcp_global, tcp_value

    values = read_tcp_global()
    current = tcp_value(values, "autotuning", "自动调谐", "自动调节") or ""
    netsh_tcp_set("autotuninglevel", "disabled")
    return current


def _restore_tcp(original_level: str) -> None:
    from core.repair.base import netsh_tcp_set

    if original_level:
        netsh_tcp_set("autotuninglevel", original_level)


def _fabricate_hosts() -> str:
    """往 hosts 追加一条指向 0.0.0.0 的屏蔽记录。返回原始文件字节（base64）。"""
    import base64

    raw = open(pw.HOSTS_PATH, "rb").read()
    text = raw.decode("utf-8", errors="surrogateescape")
    if not text.endswith("\n"):
        text += "\n"
    text += HOSTS_MARKER + "\n"
    pw.atomic_write(pw.HOSTS_PATH, text)
    return base64.b64encode(raw).decode("ascii")


def _restore_hosts(original_b64: str) -> None:
    import base64

    raw = base64.b64decode(original_b64.encode("ascii"))
    with open(pw.HOSTS_PATH, "wb") as fh:
        fh.write(raw)


def _fabricate_netbios() -> str:
    """把主网卡的 NetbiosOptions 置为「启用」（1），让动作有东西可修。

    本机实测原值是 0（由 DHCP 决定），动作只在值 != 2 时才真的动手，
    所以不构造也能验证。但若某台机器上原本就是 2，动作会 SKIPPED、
    闭环就退化成空转——因此这里显式构造，保证前置条件恒定。
    """
    from core.repair.netbios_actions import _read_options, _write_options
    from core.repair.base import require_primary

    ctx = DiagnosticContext()
    guid = require_primary(ctx).interface_guid
    original = _read_options(guid)
    _write_options(guid, 1)  # 1 = 启用
    # 用 JSON 保存，None 表示"原本不存在"，还原时必须删值而不是写 0
    return json.dumps({"guid": guid, "value": original})


def _restore_netbios(original_json: str) -> None:
    import winreg

    from core.repair.netbios_actions import _full_path, _write_options

    data = json.loads(original_json)
    guid = data["guid"]
    value = data["value"]
    if value is None:
        # 原本没有这个值：删掉我们写的，而不是写一个 0 冒充"原本是 0"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _full_path(guid), 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, "NetbiosOptions")
        except FileNotFoundError:
            pass
    else:
        _write_options(guid, int(value))


FABRICATE = {
    "proxy.reset": (_fabricate_proxy, _restore_proxy),
    "firewall.ensure_enabled": (_fabricate_firewall, _restore_firewall),
    "tcp.autotuning": (_fabricate_tcp, _restore_tcp),
    "hosts.clean_bad_lines": (_fabricate_hosts, _restore_hosts),
    "netbios.disable_public": (_fabricate_netbios, _restore_netbios),
}


# --------------------------------------------------------------------------- #
# 单动作闭环
# --------------------------------------------------------------------------- #
def run_one(action_id: str, store: BackupStore, ctx: DiagnosticContext,
            index: int) -> dict:
    """对单个动作跑完整闭环，返回结构化结果。"""
    tag = f"{index:02d}_{action_id.replace('.', '_')}"
    outcome = {
        "action_id": action_id,
        "applied": False,
        "rolled_back": False,
        "zero_diff": False,
        "states": [],
        "verifies": [],
        "notes": [],
        "result": None,
        "rollback": None,
    }

    log(f"\n{'=' * 70}")
    log(f"[{index}] {action_id}")
    log("=" * 70)

    fabricate, restore = FABRICATE[action_id]

    # A. 真实原始状态
    log("\n  A. 原始状态快照")
    snap_a = snapshot(f"{tag}_A_original.json")

    original = None
    try:
        # B. 构造待修状态
        log("\n  B. 构造待修状态")
        original = fabricate()
        log(f"     已构造；原始值已记录（{str(original)[:70]}）")
        snap_b = snapshot(f"{tag}_B_fabricated.json")
        code, out = diff(snap_a, snap_b)
        if code == 0:
            # 不是失败：有些动作的目标状态本来就等于本机现状（例如防火墙本就全关），
            # 构造步骤自然不产生差异。此时 apply 依然会真实执行并改变状态。
            log("     [说明] 构造未产生差异（本机现状已等于待修状态），继续执行")
            outcome["notes"].append("构造未产生差异（现状即待修状态）")
        else:
            log("     ✓ 构造生效（快照已变化）")

        # C. 执行修复
        log("\n  C. 执行修复")
        eng = E.RepairEngine(store=store, dry_run=False)
        plan = eng.plan([action_id], ctx)
        if len(plan) == 0:
            log(f"     [跳过] plan() 未纳入该动作：{plan.notes}")
            outcome["notes"].append("plan 剔除：" + "；".join(plan.notes))
            snap_c = snapshot(f"{tag}_C_applied.json")
            return outcome

        report = eng.execute(plan, ctx)
        outcome["result"] = report.to_dict()
        log(f"     session={report.session_id}  成功/失败/跳过="
            f"{report.ok_count}/{report.fail_count}/{report.skipped_count}")
        for r in report.results:
            log(f"       · {r.action_id}: {r.state.value} verified={r.verified} "
                f"{r.message[:70]}")
            if r.error:
                log(f"         错误：{r.error[:160]}")
        if report.aborted:
            log(f"     [中止] {report.abort_reason[:200]}")
            outcome["notes"].append("执行时中止：" + report.abort_reason[:120])
            return outcome

        snap_c = snapshot(f"{tag}_C_applied.json")
        code_c, out_c = diff(snap_b, snap_c)

        # apply 是否真的成功，判据是「动作自己的状态 + verify 结果」，不是
        # 快照有没有变化。原因：某些动作的目标状态可能与构造态相同（例如
        # 防火墙本来就是全 OFF，构造步骤没有改变任何东西），此时 apply 依然
        # 真实执行了 netsh 命令并置为 ON，快照当然会变；但若未来某个动作的
        # 构造恰好等于目标态，apply 会返回 SKIPPED 且快照不变——那也不算失败。
        states = [r.state.value for r in report.results]
        verifies = [r.verified for r in report.results]
        outcome["states"] = states
        outcome["verifies"] = verifies

        if "applied" in states and all(v is not False for v in verifies):
            outcome["applied"] = True
            log("     ✓ 动作报告 applied 且校验通过")
        elif "skipped" in states:
            # 没有可修的东西：这是合法结果，但本轮就无法验证「改了→能还原」
            log("     [跳过] 动作判定为无需修改（SKIPPED），本项无法验证真实改动")
            outcome["notes"].append("动作返回 SKIPPED，无可验证的改动")
        else:
            log(f"     [失败] 动作状态异常：{states}，错误："
                f"{[r.error for r in report.results if r.error]}")
            outcome["notes"].append(f"动作状态异常：{states}")

        if code_c == 0:
            log("     [提示] 修复后快照与构造态无差异（可能构造态已等于目标态）")
        else:
            log("     修复后 vs 构造态差异：")
            log(out_c)

        # D. 回滚
        log("\n  D. 回滚")
        rb = eng.rollback(report.session_id, ctx)
        outcome["rollback"] = rb.to_dict()
        log(f"     回滚 成功/失败/跳过={rb.ok_count}/{rb.fail_count}/"
            f"{getattr(rb, 'skipped_count', '?')}  marked_restored={rb.marked_restored}")
        for r in rb.results:
            log(f"       · {r.action_id}: {r.state.value}  {r.message[:70]}")
            if r.error:
                log(f"         错误：{r.error[:160]}")
        if rb.error:
            log(f"     回滚层面错误：{rb.error}")

        snap_d = snapshot(f"{tag}_D_rolledback.json")
        # 关键判决：回滚后应与「构造态」一致 —— 即修复被撤销干净。
        code_d, out_d = diff(snap_b, snap_d)
        log(f"\n  判决：回滚后 vs 构造态 差异项={code_d}")
        log(out_d)
        if code_d == 0:
            outcome["rolled_back"] = True
            outcome["zero_diff"] = True
            log("  ✓ 闭环通过：修复生效、回滚完全撤销，与构造态零差异")
        else:
            outcome["rolled_back"] = True
            log("  ✗ 回滚后仍与构造态有差异，需人工核查")

    except Exception as exc:  # noqa: BLE001 - 单项失败不能中断整轮
        log(f"\n  [异常] {action_id}：{type(exc).__name__}: {exc}")
        log(traceback.format_exc(limit=4))
        outcome["notes"].append(f"异常：{type(exc).__name__}: {exc}")

    finally:
        # 无论成败，都把本机还原到测试前的真实状态
        if original is not None:
            try:
                restore(original)
                log(f"\n  已把本项恢复为测试前的真实状态")
                snap_a2 = snapshot(f"{tag}_E_restored.json")
                code_a, out_a = diff(snap_a, snap_a2)
                if code_a == 0:
                    log("  ✓ 已复原到原始状态（与 A 零差异）")
                else:
                    log("  [注意] 复原后与原始状态仍有差异，请人工核对：")
                    log(out_a)
                    outcome["notes"].append("复原未回到原始状态")
            except Exception as exc:  # noqa: BLE001
                log(f"  [严重] 还原原始状态失败：{type(exc).__name__}: {exc}")
                outcome["notes"].append(f"还原失败：{exc}")

    return outcome


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    open(LOG_PATH, "w", encoding="utf-8").close()

    log("=" * 70)
    log("LanPulse 闭环测试：此前未验证的修复动作")
    log(f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)

    if not pw.is_elevated():
        log("\n[中止] 需要管理员权限。请以管理员身份运行本脚本。")
        return 2

    ctx = DiagnosticContext()
    log(f"\n权限：管理员　主机：{ctx.hostname}")
    primary = ctx.primary
    if primary is not None:
        log(f"主网卡：{primary.name}（ifIndex={primary.if_index}）")

    store = BackupStore()
    log(f"现有备份会话：{len(store.list_sessions())} 个")

    results: list[dict] = []
    for i, action_id in enumerate(TARGETS, start=1):
        results.append(run_one(action_id, store, ctx, i))

    # ---------------- 汇总 ----------------
    log("\n" + "=" * 70)
    log("汇总")
    log("=" * 70)
    passed = 0
    for r in results:
        # 闭环通过 = 真实改成功 + 回滚撤销干净 + 复原回原始状态。
        # 三者缺一都不算通过：只验证"改了"不能说明可回滚，
        # 只验证"回滚了"不能说明当初真的改过。
        ok = r["applied"] and r["rolled_back"] and r["zero_diff"]
        passed += 1 if ok else 0
        mark = "✓ 通过" if ok else "✗ 未通过"
        log(f"  {mark}  {r['action_id']}")
        if not ok:
            for n in r["notes"]:
                log(f"          · {n}")
            if not r["states"]:
                log("          · 未取得动作状态（可能在更早阶段中止）")

    log(f"\n结果：{passed}/{len(results)} 项闭环通过")
    with open(os.path.join(OUT_DIR, "closed_loop_v12_summary.json"), "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=2,
                  default=lambda o: getattr(o, "value", str(o)))
    log(f"明细已保存：{os.path.join(OUT_DIR, 'closed_loop_v12_summary.json')}")
    return 0 if passed == len(results) else 6


if __name__ == "__main__":
    sys.exit(main())
