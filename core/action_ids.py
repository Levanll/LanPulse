"""修复动作 id 与元数据的单一来源。

检测单元只输出 action_id，UI 只按 id 查元数据，修复引擎只按 id 派发实现。
三方解耦，新增修复能力只需在此登记 + 在 core/repair/actions 里实现。
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import RiskLevel


@dataclass(frozen=True)
class ActionMeta:
    action_id: str
    title: str
    risk: RiskLevel
    description: str
    requires_elevation: bool = True
    default_selected: bool = True
    # 同一秒级事务内互相冲突的动作（例如同时改 DNS 到两个不同方案）
    conflicts_with: tuple[str, ...] = ()


ACTIONS: dict[str, ActionMeta] = {
    # ---------------- DNS ----------------
    "dns.flush_cache": ActionMeta(
        action_id="dns.flush_cache",
        title="清空 DNS 解析缓存",
        risk=RiskLevel.LOW,
        description="清除本机 DNS 缓存，解决域名解析结果过期、劫持残留导致的访问异常。"
                    "该操作不影响任何配置，可随时重做。",
        requires_elevation=False,
    ),
    "dns.set_public": ActionMeta(
        action_id="dns.set_public",
        title="切换至公共 DNS 服务器",
        risk=RiskLevel.MEDIUM,
        description="将当前上网网卡的 DNS 改为公共 DNS（默认阿里 223.5.5.5 / 腾讯 119.29.29.29）。"
                    "原 DNS 配置会完整备份，可一键还原。",
    ),
    "dns.restore_dhcp": ActionMeta(
        action_id="dns.restore_dhcp",
        title="DNS 恢复为自动获取",
        risk=RiskLevel.LOW,
        description="把网卡 DNS 改回由路由器 / DHCP 自动下发，适合接入公司或校园网的场景。",
    ),
    # ---------------- HOSTS ----------------
    "hosts.clean_bad_lines": ActionMeta(
        action_id="hosts.clean_bad_lines",
        title="清理 HOSTS 中的异常记录",
        risk=RiskLevel.MEDIUM,
        description="移除非本机写入的可疑映射（指向 0.0.0.0 / 回环地址的屏蔽项、"
                    "与系统关键域名冲突的记录）。原文件整份备份后才会改写。",
    ),
    "hosts.restore_default": ActionMeta(
        action_id="hosts.restore_default",
        title="HOSTS 恢复为系统默认模板",
        risk=RiskLevel.HIGH,
        description="用 Windows 原始默认 hosts 覆盖当前文件。会丢失用户自己添加的全部自定义记录，"
                    "因此默认不勾选，且执行前强制二次确认。",
        default_selected=False,
    ),
    # ---------------- TCP/IP 参数 ----------------
    "tcp.autotuning": ActionMeta(
        action_id="tcp.autotuning",
        title="恢复 TCP 接收窗口自动调节",
        risk=RiskLevel.MEDIUM,
        description="把 TCP autotuning 级别恢复为 normal。被手动关掉会导致高延迟链路吞吐骤降。",
    ),
    "tcp.heuristics": ActionMeta(
        action_id="tcp.heuristics",
        title="关闭启发式窗口缩放限制",
        risk=RiskLevel.MEDIUM,
        description="窗口缩放启发式在 Windows 10 1803 之后已被系统废弃，修改不会产生实际效果。"
                    "保留此项仅为兼容旧系统；在现行 Windows 上执行会被自动跳过。",
        default_selected=False,
    ),
    "tcp.reset_stack": ActionMeta(
        action_id="tcp.reset_stack",
        title="重置 TCP/IP 协议栈",
        risk=RiskLevel.HIGH,
        description="等价于 netsh int ip reset + winsock reset，用于修复协议栈损坏。"
                    "会要求重启计算机才能完全生效，因此默认不勾选。",
        default_selected=False,
    ),
    # ---------------- 代理 ----------------
    "proxy.reset": ActionMeta(
        action_id="proxy.reset",
        title="关闭残留的系统代理",
        risk=RiskLevel.MEDIUM,
        description="清除 WinINET 代理设置并恢复为直连。常见于代理软件异常退出后无法上网。",
    ),
    "proxy.restore_auto": ActionMeta(
        action_id="proxy.restore_auto",
        title="恢复自动检测代理设置",
        risk=RiskLevel.LOW,
        description="把“自动检测设置”恢复为系统默认开启状态。",
    ),
    # ---------------- 网卡 / IP ----------------
    "adapter.renew_dhcp": ActionMeta(
        action_id="adapter.renew_dhcp",
        title="重新获取 IP 地址（DHCP 续租）",
        risk=RiskLevel.LOW,
        description="对当前上网网卡执行 release + renew，修复 169.254 开头的无效地址、"
                    "租约失效等问题。执行期间网络会短暂中断 3-10 秒。",
    ),
    "adapter.reset_stack": ActionMeta(
        action_id="adapter.reset_stack",
        title="重置 Winsock 目录与防火墙规则",
        risk=RiskLevel.HIGH,
        description="netsh winsock reset 会清空第三方网络过滤驱动注册（部分安全软件需重装组件），"
                    "并需要重启。默认不勾选。",
        default_selected=False,
    ),
    # ---------------- MTU ----------------
    "mtu.optimize": ActionMeta(
        action_id="mtu.optimize",
        title="按实测结果修正 MTU",
        risk=RiskLevel.MEDIUM,
        description="仅当实测出更优 MTU 且与当前值不同时才会写入，不会盲目改成固定值。",
    ),
    # ---------------- 其它 ----------------
    "firewall.ensure_enabled": ActionMeta(
        action_id="firewall.ensure_enabled",
        title="重新启用 Windows 防火墙",
        risk=RiskLevel.MEDIUM,
        description="当检测到防火墙域配置被意外关闭时，恢复为开启状态。",
    ),
    "netbios.disable_public": ActionMeta(
        action_id="netbios.disable_public",
        title="在公网网卡上禁用 NetBIOS over TCP/IP",
        risk=RiskLevel.LOW,
        description="降低局域网名称广播带来的暴露面，不影响正常的 DHCP / DNS 上网。",
    ),
}


def meta(action_id: str) -> ActionMeta | None:
    return ACTIONS.get(action_id)


def describe(action_id: str) -> str:
    m = ACTIONS.get(action_id)
    return m.title if m else action_id


__all__ = ["ActionMeta", "ACTIONS", "meta", "describe"]
