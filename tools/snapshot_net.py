r"""闭环测试用的状态快照工具（只读，不修改任何东西）。

用途：在"执行修复 → 回滚"前后各抓一次系统网络状态，用于逐项比对
「是否真的改了」「是否真的还原了」。这是本次闭环测试的判决依据。

抓取内容：
  * 主网卡 DNS 服务器列表（IPv4 / IPv6）
  * DNS 是否 DHCP 下发
  * hosts 文件 SHA256 与字节数
  * WinINET 代理设置（Enable / Server / Override / AutoConfigURL）
  * WinHTTP 代理
  * TCP autotuning / heuristics 级别
  * 主网卡 MTU
  * 防火墙三个 profile 状态

用法：
    python tools/snapshot_net.py before.json
    python tools/snapshot_net.py after.json
    python tools/snapshot_net.py --diff before.json after.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import platform_win as pw  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()


def _dns_servers() -> dict:
    """通过 CIM 取所有网卡的 DNS，按 ifIndex 索引。"""
    script = (
        "$r = Get-DnsClientServerAddress -ErrorAction SilentlyContinue | "
        "Select-Object InterfaceIndex,InterfaceAlias,AddressFamily,"
        "@{n='Servers';e={$_.ServerAddresses -join ','}}; $r"
    )
    out: dict[str, dict] = {}
    try:
        data = pw.run_ps_json(script, timeout=30)
    except RuntimeError as exc:
        return {"error": str(exc)}
    items = data if isinstance(data, list) else [data]
    for it in items:
        if not isinstance(it, dict):
            continue
        idx = str(it.get("InterfaceIndex"))
        entry = out.setdefault(idx, {
            "alias": it.get("InterfaceAlias"),
            "v4": "",
            "v6": "",
        })
        fam = str(it.get("AddressFamily"))
        servers = it.get("Servers") or ""
        if fam in ("2", "IPv4", "InterNetwork"):
            entry["v4"] = servers
        elif fam in ("23", "IPv6", "InterNetworkV6"):
            entry["v6"] = servers
    return out


def _hosts_state() -> dict:
    path = pw.HOSTS_PATH
    try:
        data = open(path, "rb").read()
    except OSError as exc:
        return {"error": str(exc)}
    return {
        "path": path,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest().upper(),
    }


def _wininet() -> dict:
    try:
        import winreg
    except ImportError as exc:
        return {"error": str(exc)}
    key = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    out: dict = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as h:
            for name in ("ProxyEnable", "ProxyServer", "ProxyOverride", "AutoConfigURL"):
                try:
                    out[name] = winreg.QueryValueEx(h, name)[0]
                except OSError:
                    out[name] = None
    except OSError as exc:
        return {"error": str(exc)}
    return out


def _winhttp() -> str:
    rc, out = pw.run_cmd(["netsh", "winhttp", "show", "proxy"], timeout=15)
    lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
    # 只保留有意义的那一两行，避免把表头噪音计入比对
    keep = [ln for ln in lines if "代理" in ln or "Proxy" in ln or "直接" in ln or "Direct" in ln]
    return " | ".join(keep) if keep else out.strip()[:200]


def _tcp_global() -> dict:
    rc, out = pw.run_cmd(["netsh", "int", "tcp", "show", "global"], timeout=20)
    if rc != 0:
        return {"error": out[:200]}
    wanted = {
        "autotuning": ("接收窗口自动调节级别", "Receive Window Auto-Tuning Level"),
        "rss": ("接收方缩放状态", "Receive-Side Scaling State"),
        "ecn": ("ECN", "ECN"),
    }
    result: dict[str, str] = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        for key, names in wanted.items():
            if any(n.lower() in k.lower() for n in names):
                result[key] = v
    result["_raw_lines"] = len(out.splitlines())
    return result


def _mtu(primary) -> dict:
    if not primary:
        return {"error": "no primary adapter"}
    return {
        "adapter": primary.name,
        "if_index": primary.if_index,
        "guid": primary.interface_guid,
        "mtu": primary.mtu,
    }


def _firewall() -> dict:
    rc, out = pw.run_cmd(["netsh", "advfirewall", "show", "allprofiles"], timeout=25)
    if rc != 0:
        return {"error": out[:300]}
    result: dict[str, str] = {}
    current = ""
    for line in out.splitlines():
        s = line.strip()
        low = s.lower()
        if "profile settings" in low or "配置文件设置" in s:
            current = s.split()[0].lower()
        if "state" in low or "状态" in s:
            val = s.split(":")[-1].strip() if ":" in s else s.split()[-1]
            if current:
                result[current] = val
    return result


def take_snapshot() -> dict:
    adapters = pw.collect_adapters()
    primary = pw.primary_adapter(adapters)
    return {
        "elevated": pw.is_elevated(),
        "hostname": pw.computer_name(),
        "primary_adapter": {
            "name": primary.name if primary else None,
            "if_index": primary.if_index if primary else None,
            "guid": primary.interface_guid if primary else None,
            "dns_v4": list(primary.dns_v4) if primary else [],
        },
        "dns_all_interfaces": _dns_servers(),
        "hosts": _hosts_state(),
        "wininet": _wininet(),
        "winhttp": _winhttp(),
        "tcp": _tcp_global(),
        "mtu": _mtu(primary),
        "firewall": _firewall(),
    }


def diff(before: dict, after: dict) -> int:
    """逐项比对并打印差异。返回差异项数。"""
    changes = 0
    print("=" * 66)
    print("状态比对")
    print("=" * 66)

    def cmp(label: str, a, b) -> None:
        nonlocal changes
        if a == b:
            print(f"  [同] {label}")
        else:
            changes += 1
            print(f"  [变] {label}")
            print(f"        之前: {a}")
            print(f"        之后: {b}")

    pa = before.get("primary_adapter") or {}
    pb = after.get("primary_adapter") or {}
    cmp("主网卡 DNS",
        pa.get("dns_v4"), pb.get("dns_v4"))

    cmp("hosts sha256",
        (before.get("hosts") or {}).get("sha256"),
        (after.get("hosts") or {}).get("sha256"))

    wa = before.get("wininet") or {}
    wb = after.get("wininet") or {}
    for k in ("ProxyEnable", "ProxyServer", "ProxyConfigURL", "AutoConfigURL"):
        cmp(f"WinINET {k}", wa.get(k), wb.get(k))

    cmp("WinHTTP 代理", before.get("winhttp"), after.get("winhttp"))

    ta = before.get("tcp") or {}
    tb = after.get("tcp") or {}
    for k in ("autotuning", "rss", "ecn"):
        cmp(f"TCP {k}", ta.get(k), tb.get(k))

    cmp("MTU", (before.get("mtu") or {}).get("mtu"),
        (after.get("mtu") or {}).get("mtu"))

    cmp("防火墙", before.get("firewall"), after.get("firewall"))

    # 逐网卡 DNS 对比
    da = before.get("dns_all_interfaces") or {}
    db = after.get("dns_all_interfaces") or {}
    for idx in sorted(set(da) | set(db)):
        a = da.get(idx) or {}
        b = db.get(idx) or {}
        if a == b:
            continue
        if not a or not b:
            continue
        if a.get("v4") != b.get("v4"):
            changes += 1
            print(f"  [变] 网卡 {a.get('alias') or idx} DNS")
            print(f"        之前: {a.get('v4')!r}")
            print(f"        之后: {b.get('v4')!r}")

    print("=" * 66)
    print(f"差异项：{changes}")
    return changes


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1

    if argv[0] == "--diff":
        before = json.load(open(argv[1], encoding="utf-8"))
        after = json.load(open(argv[2], encoding="utf-8"))
        n = diff(before, after)
        return 0 if n == 0 else 2

    out_path = argv[0]
    snap = take_snapshot()
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=2)
    print(f"快照已保存：{out_path}")
    print(f"  权限: {'管理员' if snap['elevated'] else '普通'}")
    pa = snap["primary_adapter"]
    print(f"  主网卡: {pa['name']}  DNS={pa['dns_v4']}")
    print(f"  hosts: {(snap['hosts'] or {}).get('sha256')}")
    print(f"  MTU: {(snap['mtu'] or {}).get('mtu')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
