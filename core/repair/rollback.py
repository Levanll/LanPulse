"""回滚分派层。

为什么独立成模块而不是塞进 engine：
    每个修复动作的 `rollback()` 方法和 `engine.rollback()` 必须走**同一套**
    恢复逻辑。如果各写一遍，必然出现"单条回滚能修复、整轮回滚反而漏掉某项"
    的诡异 bug。这里提供唯一的按 kind 分派的实现，两边都调它。

容错原则（有意为之）：
    单个备份项恢复失败**不中断**后续项。恢复尽可能多的状态，比因为第一项失败
    就全部放弃更有价值。但每一次失败都必须被记录成 ActionResult.FAILED 并带
    原始异常文本，绝不静默跳过。
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

from .. import platform_win as pw
from ..backup import BackupItem
from ..models import ActionState, ActionResult
from .base import (
    netsh_dns_dhcp,
    netsh_dns_static,
    netsh_firewall_set,
    netsh_mtu_set,
    netsh_tcp_set,
    reg_import,
    run_or_raise,
)

# 回滚项的 kind 常量，与各动作 backup() 里写入的值保持一致
KIND_HOSTS = "hosts"
KIND_DNS = "dns"
KIND_REGISTRY = "registry"
KIND_MTU = "mtu"
KIND_FIREWALL = "firewall"
KIND_TCP = "tcp"
KIND_DHCP = "dhcp"
KIND_WINHTTP = "winhttp"
KIND_NETBIOS = "netbios"


def rollback_item(store: Any, session: Any, ctx: Any, item: BackupItem,
                  *, elevated: bool | None = None) -> ActionResult:
    """恢复单个备份项。失败返回 FAILED，不抛异常（由调用方汇总）。

    elevated 由调用方一次性算出后传入，避免每一项都去问系统一次；
    非管理员时对需要提权的项直接标 SKIPPED 而非 FAILED——"权限不够"和
    "备份坏了"是两件事，混在一起会误导用户。
    """
    result = ActionResult(action_id=f"rollback:{item.key}", started_at=pw.now())
    if elevated is None:
        elevated = pw.is_elevated()
    try:
        skipped_reason = _elevation_gate(item, elevated)
        if skipped_reason:
            result.state = ActionState.SKIPPED
            result.message = skipped_reason
            result.finished_at = pw.now()
            return result
        detail = _dispatch(store, session, ctx, item, result)
    except Exception as exc:  # noqa: BLE001 - 逐项容错是刻意设计，但必须记录
        result.state = ActionState.ROLLBACK_FAILED
        result.message = f"恢复「{item.label}」失败"
        result.error = f"{type(exc).__name__}: {exc}"
        result.finished_at = pw.now()
        return result

    result.finished_at = pw.now()
    if result.state is ActionState.SKIPPED:
        return result
    result.state = ActionState.ROLLED_BACK
    result.message = detail or f"已恢复「{item.label}」"
    result.verified = True
    return result


# 哪些 kind 的恢复动作必须以管理员身份运行
_NEEDS_ELEVATION = {
    KIND_REGISTRY,  # reg import 写 HKLM
    KIND_DNS,       # netsh set dnsservers
    KIND_MTU,       # netsh set subinterface
    KIND_FIREWALL,  # netsh advfirewall
    KIND_TCP,       # netsh int tcp set global
    KIND_NETBIOS,   # winreg 写 HKLM
    KIND_HOSTS,     # hosts 位于 C:\Windows\System32\drivers\etc，普通用户不可写
}


def _elevation_gate(item: BackupItem, elevated: bool) -> str:
    """非管理员且该项需要提权时，返回跳过原因（空串表示可以继续）。

    例外：写 HKCU 的项不需要提权。wininet 代理备份在 HKCU，普通用户也能导回，
    所以按 hive_path 再判一次，不要一刀切。
    """
    if elevated or item.kind not in _NEEDS_ELEVATION:
        return ""
    hive = str((item.payload or {}).get("hive_path") or "")
    if item.kind == KIND_REGISTRY and hive.upper().startswith("HKCU"):
        return ""
    return (
        f"「{item.label}」需要管理员权限才能还原，当前以普通用户身份运行。"
        f"请右键以管理员身份启动后重试回滚；备份文件本身完好，可在备份目录中手工还原"
    )


def _dispatch(store: Any, session: Any, ctx: Any, item: BackupItem,
              result: ActionResult) -> str:
    kind = item.kind
    if kind == KIND_HOSTS:
        return _rollback_hosts(session, item, result)
    if kind == KIND_DNS:
        return _rollback_dns(ctx, item, result)
    if kind == KIND_REGISTRY:
        return _rollback_registry(session, item, result)
    if kind == KIND_MTU:
        return _rollback_mtu(ctx, item, result)
    if kind == KIND_FIREWALL:
        return _rollback_firewall(item, result)
    if kind == KIND_TCP:
        return _rollback_tcp(item, result)
    if kind == KIND_NETBIOS:
        return _rollback_netbios(item, result)
    if kind == KIND_DHCP:
        result.state = ActionState.SKIPPED
        result.message = (
            f"「{item.label}」不自动回滚：DHCP 续租会再次断开网络。"
            f"备份记录的原地址为 {item.payload.get('ipv4') or '无'}，"
            f"网关 {item.payload.get('gateway') or '无'}，请手工核对是否需要还原"
        )
        result.detail.append("如需恢复地址，请在网卡属性中改为静态 IP 并填入上述值")
        return ""
    if kind == KIND_WINHTTP:
        result.state = ActionState.SKIPPED
        result.message = (
            f"「{item.label}」仅记录了展示文本，未导出可导入的注册表快照；"
            f"请使用备份目录中的原始输出人工核对 WinHTTP 代理"
        )
        return ""
    # 未知 kind 必须显式暴露：说明备份格式与回滚实现不匹配，属于缺陷而非正常情况
    result.state = ActionState.ROLLBACK_FAILED
    result.message = f"未知的备份类型「{kind}」（key={item.key}）"
    result.error = "备份项类型与回滚实现不匹配，拒绝猜测恢复方式"
    return ""


# --------------------------------------------------------------------------- #
# 各类恢复
# --------------------------------------------------------------------------- #
def _rollback_hosts(session: Any, item: BackupItem, result: ActionResult) -> str:
    payload = item.payload or {}
    source_path = payload.get("source_path") or pw.HOSTS_PATH
    expected_sha = payload.get("sha256") or ""
    backup_path = os.path.join(session.path, item.file_name) if item.file_name else ""

    if not backup_path or not os.path.isfile(backup_path):
        raise FileNotFoundError(f"HOSTS 备份文件不存在：{backup_path or item.file_name}")

    raw = open(backup_path, "rb").read()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if expected_sha and actual_sha != expected_sha:
        # 备份被外部改动过。用损坏的备份覆盖 hosts 会把用户彻底搞断网，
        # 因此这里的正确行为是拒绝，并告诉用户去核对哪个文件。
        raise RuntimeError(
            f"备份文件已损坏，拒绝恢复：{backup_path}\n"
            f"期望 sha256={expected_sha}\n实际 sha256={actual_sha}\n"
            f"请检查该文件是否被其它程序修改"
        )

    text = raw.decode("utf-8", errors="surrogateescape")
    pw.atomic_write(source_path, text)
    result.detail.append(f"已从 {backup_path} 恢复 HOSTS（sha256 校验通过）")
    return f"已恢复 HOSTS 原文（{len(raw)} 字节）"


def _rollback_dns(ctx: Any, item: BackupItem, result: ActionResult) -> str:
    payload = item.payload or {}
    alias = payload.get("alias") or ""
    servers = [str(s) for s in payload.get("servers") or []]
    was_dhcp = bool(payload.get("was_dhcp"))
    guid = payload.get("interface_guid") or ""

    # 网卡可能已被用户改名：优先按 GUID 找到它当前的别名，
    # 用备份里的旧别名去调 netsh 会因"接口不存在"直接失败。
    resolved = _current_alias(guid, ctx)
    if resolved is None:
        raise RuntimeError(
            f"未找到 GUID 为 {guid or '（备份中未记录）'} 的网卡，"
            f"该网卡可能已被禁用或移除，无法恢复其 DNS 配置"
        )
    alias = resolved

    if was_dhcp:
        netsh_dns_dhcp(alias)
        result.detail.append(f"原本为 DHCP 自动获取，已恢复：{alias}")
        return f"「{alias}」的 DNS 已恢复为自动获取"
    if not servers:
        raise RuntimeError(
            f"备份记录了静态 DNS 但服务器列表为空（{item.key}），"
            f"无法据此恢复；请手工在网卡属性中设置"
        )
    netsh_dns_static(alias, servers)
    result.detail.append(f"原本为静态列表，已恢复：{alias} -> {'、'.join(servers)}")
    return f"「{alias}」的 DNS 已恢复为 {'、'.join(servers)}"


def _current_alias(guid: str, ctx: Any) -> str | None:
    if not guid:
        return None
    adapters = ctx.adapters if hasattr(ctx, "adapters") else pw.collect_adapters()
    for adapter in adapters:
        if adapter.interface_guid.lower() == guid.lower():
            return adapter.name
    # 缓存可能已过期（用户刚改过网卡），再直采一次
    for adapter in pw.collect_adapters():
        if adapter.interface_guid.lower() == guid.lower():
            return adapter.name
    return None


def _rollback_registry(session: Any, item: BackupItem, result: ActionResult) -> str:
    backup_path = os.path.join(session.path, item.file_name) if item.file_name else ""
    if not backup_path or not os.path.isfile(backup_path):
        raise FileNotFoundError(f"注册表备份文件不存在：{backup_path or item.file_name}")
    out = reg_import(backup_path)
    result.detail.append(f"已导入 {backup_path}")
    if out:
        result.detail.extend(line for line in out.splitlines() if line.strip())
    return f"已导入注册表备份（{item.payload.get('hive_path', item.key)}）"


def _rollback_mtu(ctx: Any, item: BackupItem, result: ActionResult) -> str:
    payload = item.payload or {}
    target = payload.get("mtu")
    if not isinstance(target, int) or target <= 0:
        raise RuntimeError(f"备份中的 MTU 值无效：{target!r}")
    guid = payload.get("interface_guid") or ""
    alias = payload.get("alias") or ""
    resolved = _current_alias(guid, ctx) if guid else None
    if resolved is None and not alias:
        raise RuntimeError("备份中既无网卡 GUID 也无别名，无法定位要恢复的网卡")
    alias = resolved or alias
    if resolved is None and guid:
        result.detail.append(
            f"警告：未按 GUID 找到网卡 {guid}，退化为按备份别名「{alias}」恢复"
        )
    netsh_mtu_set(alias, int(target))
    return f"「{alias}」的 MTU 已恢复为 {target}"


def _rollback_firewall(item: BackupItem, result: ActionResult) -> str:
    profiles = (item.payload or {}).get("profiles") or {}
    if not profiles:
        raise RuntimeError("防火墙备份中没有配置文件状态，无法恢复")
    restored: list[str] = []
    for profile, state in profiles.items():
        wanted = str(state).upper() == "ON"
        netsh_firewall_set(profile, wanted)
        restored.append(f"{profile}={'ON' if wanted else 'OFF'}")
    return "防火墙已恢复：" + "、".join(restored)


def _rollback_tcp(item: BackupItem, result: ActionResult) -> str:
    payload = item.payload or {}
    level = (payload.get("level") or "").strip()
    if not level:
        raise RuntimeError(f"备份中没有 TCP 参数原值（{item.key}）")
    # key 决定要设哪个参数，以及用哪条命令：autotuning 走 set global，
    # heuristics 走 set heuristics wsh=（后者不在 set global 的合法参数里）
    if "autotuning" in item.key:
        netsh_tcp_set("autotuninglevel", level)
        return f"TCP autotuninglevel 已恢复为 {level}"
    if "heuristics" in item.key:
        run_or_raise(["netsh", "int", "tcp", "set", "heuristics", f"wsh={level}"],
                     timeout=25, what=f"恢复窗口缩放启发式为 {level}")
        return f"TCP 窗口缩放启发式已恢复为 {level}"
    raise RuntimeError(f"无法从备份 key 判断 TCP 参数名：{item.key}")


def _rollback_netbios(item: BackupItem, result: ActionResult) -> str:
    """恢复 NetBIOS 开关。

    这里有两种来源，处理方式不同：
      * 退化快照（reg export 失败）：备份里明确记了 existed=False，
        说明该注册表项原本不存在，正确做法是删除我们创建的值；
      * 兜底情况：说明备份不完整，如实报失败，不猜。
    """
    import winreg

    payload = item.payload or {}
    guid = (payload.get("interface_guid") or "").strip()
    hive_path = payload.get("hive_path") or ""
    existed = payload.get("existed")

    if not guid:
        raise RuntimeError(f"备份中没有网卡 GUID（{item.key}），无法定位 NetBIOS 配置项")

    from .netbios_actions import _full_path  # 复用同一套路径拼装规则

    path = _full_path(guid)
    if existed is False:
        # 原本不存在：删掉 NetbiosOptions 值（键本身留着无害，且可能已被系统重建）
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0,
                                winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, "NetbiosOptions")
        except FileNotFoundError:
            result.detail.append("注册表值与键均不存在，视为已回到原始状态")
            return "NetBIOS 配置已回到原状（原本不存在）"
        except OSError as exc:
            raise RuntimeError(f"删除 NetbiosOptions 失败（{path}）：{exc}") from exc
        result.detail.append(f"已删除 {path}\\NetbiosOptions（原本不存在）")
        return "NetBIOS 配置已回到「未设置」状态"

    raise RuntimeError(
        f"该 NetBIOS 备份不含可恢复的注册表快照（{item.key}，"
        f"hive={hive_path or '未记录'}）；请用备份目录中的 .reg 文件人工导入"
    )


# --------------------------------------------------------------------------- #
# 给单个动作用的便利入口
# --------------------------------------------------------------------------- #
def rollback_items_of_kind(store: Any, session: Any, ctx: Any, *, kind: str,
                           action_id: str) -> ActionResult:
    """恢复本会话中指定 kind 的全部备份项，聚合成单个 ActionResult。

    动作自己的 `rollback()` 用它，保证"单条回滚"与"整轮回滚"行为一致。
    """
    items = [item for item in session.items if item.kind == kind]
    result = ActionResult(action_id=action_id, started_at=pw.now())
    if not items:
        result.state = ActionState.SKIPPED
        result.message = "本次备份会话中没有该动作产生的备份项，无可回滚内容"
        result.finished_at = pw.now()
        return result

    elevated = pw.is_elevated()
    failures: list[str] = []
    applied = 0
    for item in reversed(items):
        sub = rollback_item(store, session, ctx, item, elevated=elevated)
        if sub.state in (ActionState.ROLLED_BACK, ActionState.SKIPPED):
            applied += 1
            result.detail.append(f"[{sub.state.value}] {sub.message}")
        else:
            failures.append(f"{item.key}: {sub.error or sub.message}")

    result.finished_at = pw.now()
    if failures:
        result.state = ActionState.ROLLBACK_FAILED
        result.message = f"部分备份项恢复失败（成功 {applied} 项）"
        result.error = "\n".join(failures)
        result.verified = False
        return result
    result.state = ActionState.ROLLED_BACK
    result.message = f"已恢复 {applied} 项备份"
    result.verified = True
    return result


__all__ = [
    "KIND_DHCP",
    "KIND_DNS",
    "KIND_FIREWALL",
    "KIND_HOSTS",
    "KIND_MTU",
    "KIND_NETBIOS",
    "KIND_REGISTRY",
    "KIND_TCP",
    "KIND_WINHTTP",
    "rollback_item",
    "rollback_items_of_kind",
]
