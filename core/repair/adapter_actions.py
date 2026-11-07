"""网卡 / IP 层修复动作。

两条动作都会短暂或显著影响网络，因此都排在执行顺序的后段：
    adapter.renew_dhcp  —— 断网 3~10 秒，成功后即恢复
    adapter.reset_stack —— winsock + ip reset，需重启

为什么要备份"看起来幂等"的 renew：renew 有可能拿到与原来不同的地址（路由器
租约表被刷新、DHCP 服务器换了），用户的端口转发、共享打印、静态映射会全部
失效。不备份就等于不给退路。
"""
from __future__ import annotations

import time
from typing import Any

from .. import platform_win as pw
from ..models import ActionState, ActionResult, ChangePreview
from .base import (
    BaseAction,
    capture_registry_or_state,
    register_action,
    require_primary,
)
from .tcp_actions import TCPIP_PARAMS, WINSOCK_PARAMS

_RESTART_NOTE = "该操作需要重启计算机才能完全生效"


# --------------------------------------------------------------------------- #
# adapter.renew_dhcp
# --------------------------------------------------------------------------- #
@register_action("adapter.renew_dhcp")
class AdapterRenewDhcpAction(BaseAction):
    """对主网卡执行 release + renew。

    用于修复 169.254 开头的 APIPA 地址、以及租约到期后没能续上的情况。
    执行期间网络会中断，这是预期行为而非故障。
    """

    action_id = "adapter.renew_dhcp"
    # release/renew 的等待时间。renew 在弱信号 Wi-Fi 上可能超过 10 秒，
    # 超时设得太短会把正常过程误判成失败。
    release_timeout = 30.0
    renew_timeout = 60.0
    settle_seconds = 1.0

    def preview(self, ctx: Any) -> ChangePreview:
        primary = require_primary(ctx)
        current = primary.primary_ipv4 or "无 IP"
        flag = "（APIPA 无效地址）" if current.startswith("169.254.") else ""
        return ChangePreview(
            target=f"{primary.name} / IPv4 地址与租约",
            before=f"{current}{flag}，地址来源={'DHCP' if primary.dhcp else '静态或未知'}",
            after="重新向 DHCP 服务器申请地址；成功后可能得到与当前不同的 IP",
            note="执行期间网络会中断约 3-10 秒，属预期行为；原地址与网关会完整备份",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        primary = require_primary(ctx)
        key = f"ipconfig:{primary.interface_guid}"
        store.capture_state(
            session,
            key=key,
            kind="dhcp",
            label=f"{primary.name} 的 IP 租约信息",
            payload={
                "interface_guid": primary.interface_guid,
                "interface_index": primary.if_index,
                "alias": primary.name,
                "ipv4": list(primary.ipv4),
                "prefix_len": primary.prefix_len,
                "gateway": primary.gateway,
                "dhcp": primary.dhcp,
                "dns": list(primary.dns_v4),
                "mtu": primary.mtu,
            },
        )
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        primary = require_primary(ctx)
        alias = primary.name
        # verify 阶段要复核"同一块网卡"，先把 GUID 记下来
        remember_target_guid(ctx, self.action_id, primary.interface_guid)
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        before_ip = primary.primary_ipv4 or "无"

        rc_rel, out_rel = pw.run_cmd(["ipconfig", "/release", alias],
                                     timeout=self.release_timeout)
        result.detail.append(f"ipconfig /release \"{alias}\" -> 返回码 {rc_rel}")
        if out_rel:
            result.detail.extend(line for line in out_rel.splitlines() if line.strip())

        # release 失败不直接中止：某些网卡（尤其 USB 网卡 / 虚拟机）不支持 release，
        # 但 renew 仍然有效。真正决定成败的是 renew 之后有没有拿到可用地址。
        if rc_rel != 0:
            result.detail.append(
                f"警告：release 返回 {rc_rel}，继续尝试 renew（部分网卡不支持释放租约）"
            )

        time.sleep(self.settle_seconds)

        rc_new, out_new = pw.run_cmd(["ipconfig", "/renew", alias],
                                     timeout=self.renew_timeout)
        result.detail.append(f"ipconfig /renew \"{alias}\" -> 返回码 {rc_new}")
        if out_new:
            result.detail.extend(line for line in out_new.splitlines() if line.strip())
        result.finished_at = pw.now()

        if rc_new != 0:
            result.state = ActionState.FAILED
            result.message = "重新获取 IP 地址失败，网络可能仍不可用"
            result.error = (
                f"ipconfig /renew 返回码 {rc_new}：{out_new or '（无输出）'}\n"
                f"原地址 {before_ip}；请检查网线 / Wi-Fi 连接与路由器 DHCP 服务"
            )
            return result

        # 现采集一次，用真实结果说话（renew 返回 0 也可能拿到 APIPA）
        latest = _adapter_by_guid(primary.interface_guid) or _adapter_by_alias(alias)
        if latest is None:
            result.state = ActionState.FAILED
            result.message = "重新获取地址后无法定位该网卡"
            result.error = f"按 GUID {primary.interface_guid} 与别名 {alias} 均未找到网卡"
            return result

        new_ip = latest.primary_ipv4
        if not new_ip:
            result.state = ActionState.FAILED
            result.message = "网络已恢复，但网卡仍未获得 IPv4 地址"
            result.error = "renew 返回成功但网卡无 IPv4 地址，请检查路由器 DHCP 是否开启"
            return result
        if new_ip.startswith("169.254."):
            result.state = ActionState.FAILED
            result.message = "重新获取后仍是 169.254 开头的无效地址，DHCP 未响应"
            result.error = f"当前地址 {new_ip}；请检查路由器 DHCP 服务与网线连接"
            return result

        result.message = (
            f"网络已恢复，IP 从 {before_ip} 变为 {new_ip}；"
            f"若仍无法上网请检查路由器 DHCP 与网关配置"
        )
        result.detail.append(f"新地址 {new_ip}/{latest.prefix_len}，网关 {latest.gateway or '无'}")
        if before_ip and before_ip != new_ip:
            result.detail.append(f"地址已变化，旧地址 {before_ip} 记录在备份中")
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        # verify 是对 apply 结果的独立复核，必须重新采集而不是读 ctx 缓存
        latest = _adapter_by_guid(_remembered_guid(ctx, self.action_id)) or _try_primary()
        if latest is None:
            return False, "未找到任何已连接的网卡"
        ip = latest.primary_ipv4
        if not ip:
            return False, f"「{latest.name}」当前没有 IPv4 地址"
        if ip.startswith("169.254."):
            return False, f"「{latest.name}」仍为 APIPA 地址 {ip}，DHCP 未分配有效地址"
        return True, f"「{latest.name}」已获得有效地址 {ip}，网关 {latest.gateway or '无'}"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="dhcp",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# adapter.reset_stack
# --------------------------------------------------------------------------- #
@register_action("adapter.reset_stack")
class AdapterResetStackAction(BaseAction):
    """重置 Winsock 目录与 IP 协议栈。

    与 tcp.reset_stack 的区别只在语义侧重：这条是"网卡侧连不上网"时的兜底，
    实际命令相同，因此两者同时在计划里时由 plan() 剔除其一。
    """

    action_id = "adapter.reset_stack"

    def preview(self, ctx: Any) -> ChangePreview:
        return ChangePreview(
            target="Winsock 目录与 IPv4 协议栈",
            before="当前 Winsock LSP 注册与 IP 协议栈参数",
            after="Winsock 目录重建、IP 协议栈参数复位；第三方 LSP 被移除，"
                  "相关安全软件可能需重装网络组件",
            note=f"{_RESTART_NOTE}；注册表会整份备份，重启前可用备份页回滚",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        keys: list[str] = []
        keys.append(capture_registry_or_state(
            store, session,
            key="reg:winsock2",
            hive_path=WINSOCK_PARAMS,
            label="WinSock2 参数注册表",
            fallback_payload={"kind": "registry_missing", "what": "WinSock2\\Parameters"},
        ))
        keys.append(capture_registry_or_state(
            store, session,
            key="reg:tcpip",
            hive_path=TCPIP_PARAMS,
            label="TCP/IP 参数注册表",
            fallback_payload={"kind": "registry_missing", "what": "Tcpip\\Parameters"},
        ))
        return keys

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        result.detail.append(f"⚠ {_RESTART_NOTE}")

        rc_winsock, out_winsock = pw.run_cmd(["netsh", "winsock", "reset"], timeout=60)
        result.detail.append(f"netsh winsock reset -> 返回码 {rc_winsock}")
        if out_winsock:
            result.detail.extend(line for line in out_winsock.splitlines() if line.strip())

        rc_ip, out_ip = pw.run_cmd(["netsh", "int", "ip", "reset"], timeout=60)
        result.detail.append(f"netsh int ip reset -> 返回码 {rc_ip}")
        if out_ip:
            result.detail.extend(line for line in out_ip.splitlines() if line.strip())
        result.finished_at = pw.now()

        if rc_winsock != 0 or rc_ip != 0:
            result.state = ActionState.FAILED
            result.message = "网络组件重置未完全下发"
            result.error = (
                f"netsh winsock reset 返回码 {rc_winsock}：{out_winsock or '（无输出）'}\n"
                f"netsh int ip reset 返回码 {rc_ip}：{out_ip or '（无输出）'}"
            )
            result.detail.append(f"⚠ {_RESTART_NOTE}")
            return result

        result.message = "Winsock 与 IP 协议栈已重置，需要重启计算机才能完全生效"
        result.detail.append("已在 reset 前后记录注册表快照；相关安全软件的 LSP 组件建议重装")
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        rc, out = pw.run_cmd(["netsh", "winsock", "show", "catalog"], timeout=30)
        if rc != 0:
            return False, f"重置后 `netsh winsock show catalog` 返回 {rc}：{out[:300]}"
        return True, "已下发，需重启生效（Winsock 目录仅重启后重建完成）"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="registry",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# 辅助
# --------------------------------------------------------------------------- #
def _adapter_by_guid(guid: str) -> pw.AdapterInfo | None:
    if not guid:
        return None
    for adapter in pw.collect_adapters():
        if adapter.interface_guid.lower() == guid.lower():
            return adapter
    return None


def _adapter_by_alias(alias: str) -> pw.AdapterInfo | None:
    if not alias:
        return None
    for adapter in pw.collect_adapters():
        if adapter.name == alias:
            return adapter
    return None


def _try_primary() -> pw.AdapterInfo | None:
    try:
        return pw.primary_adapter(pw.collect_adapters())
    except RuntimeError:
        return None


def _remembered_guid(ctx: Any, key: str) -> str:
    """apply 阶段把目标 GUID 记在 ctx 缓存里，供 verify 精确定位同一块网卡。

    为什么不在 verify 里再调 ctx.primary：renew 之后 primary 可能已经换了
    （比如原先主网卡暂时掉线），那会变成"校验了另一块网卡"。
    """
    store = getattr(ctx, "_cache", None)
    if isinstance(store, dict):
        return str(store.get(f"repair:target_guid:{key}") or "")
    return ""


def remember_target_guid(ctx: Any, key: str, guid: str) -> None:
    store = getattr(ctx, "_cache", None)
    if isinstance(store, dict):
        store[f"repair:target_guid:{key}"] = guid


__all__ = ["AdapterRenewDhcpAction", "AdapterResetStackAction", "remember_target_guid"]
