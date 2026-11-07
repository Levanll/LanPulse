"""DNS 相关修复动作。

三条动作覆盖了现实里最常见的 DNS 故障：
    * 缓存被污染 / 过期      -> 清缓存（无状态变更）
    * 路由器下发的 DNS 有问题 -> 换公共 DNS（要备份原配置）
    * 用户手工设过静态 DNS     -> 退回 DHCP 自动获取（要备份原配置）

换 DNS 和退回 DHCP 是互斥的两条路，冲突在 base.CONFLICTS 里声明，由 plan() 剔除。
"""
from __future__ import annotations

from typing import Any, Sequence

from .. import platform_win as pw
from ..models import ActionState, ActionResult, ChangePreview
from .base import (
    BaseAction,
    netsh_dns_dhcp,
    netsh_dns_static,
    read_dns_config,
    register_action,
    require_primary,
)

# 默认方案：阿里 + 腾讯。国内可达性最好，且两家互为备份（单家故障时仍有解析）。
DEFAULT_PUBLIC_DNS: tuple[str, ...] = ("223.5.5.5", "119.29.29.29")


def _validate_servers(servers: Sequence[str]) -> list[str]:
    """逐个校验并规范化 DNS 地址。

    必须在构造期就拒绝非法值：netsh 对非法地址的行为是按参数错误整体失败，
    用户会看到"修复失败"却不知道是 DNS 地址写错了。
    """
    if not servers:
        raise ValueError("DNS 服务器列表为空：至少需要一个 IPv4 地址")
    cleaned: list[str] = []
    for raw in servers:
        text = (raw or "").strip()
        if not pw.is_valid_ipv4(text):
            raise ValueError(f"非法的 DNS 服务器地址: {raw!r}，只接受 IPv4 点分十进制")
        if text not in cleaned:
            cleaned.append(text)
    return cleaned


def _dns_snapshot(ctx: Any, alias: str) -> tuple[list[str], bool]:
    """带缓存的 DNS 现状读取（preview 与 backup 共用，避免重复调 netsh）。"""
    cached = getattr(ctx, "cached", None)
    if callable(cached):
        return cached(f"repair:dns:{alias}", lambda: read_dns_config(alias))
    return read_dns_config(alias)


def _format_servers(servers: Sequence[str], was_dhcp: bool) -> str:
    if not servers:
        return "自动获取（DHCP 下发的服务器未记录）" if was_dhcp else "未配置"
    text = "、".join(servers)
    return f"{text}（由 DHCP 自动下发）" if was_dhcp else f"{text}（手动配置）"


def _read_dns_by_index(if_index: int) -> list[str]:
    """用 PowerShell 读回某网卡的 IPv4 DNS 列表（verify 专用，必须现读）。"""
    script = (
        f"Get-DnsClientServerAddress -InterfaceIndex {int(if_index)} "
        f"-AddressFamily IPv4 | Select-Object -ExpandProperty ServerAddresses"
    )
    data = pw.run_ps_json(script, timeout=25)
    if isinstance(data, str):
        return [data] if pw.is_valid_ipv4(data) else []
    if isinstance(data, list):
        return [str(x) for x in data if pw.is_valid_ipv4(str(x))]
    return []


# --------------------------------------------------------------------------- #
# dns.flush_cache
# --------------------------------------------------------------------------- #
@register_action("dns.flush_cache")
class DnsFlushCacheAction(BaseAction):
    """清空 DNS 解析缓存。

    这是唯一一个"不需要备份"的动作：它不改变任何持久化配置，重启解析器即可
    回到原状。backup() 返回空列表是契约的一部分，engine 据此不会误报备份失败。
    """

    action_id = "dns.flush_cache"

    def preview(self, ctx: Any) -> ChangePreview:
        entries = 0
        cached = getattr(ctx, "cached", None)
        try:
            if callable(cached):
                entries = int(cached("repair:dns_cache_count", _dns_cache_entry_count) or 0)
            else:
                entries = _dns_cache_entry_count()
        except (RuntimeError, ValueError):
            # 条目数只用于展示"缓存里有多少条"，读不到不影响清理本身
            entries = 0
        return ChangePreview(
            target="本机 DNS 解析缓存",
            before=f"当前缓存约 {entries} 条记录" if entries else "当前缓存条目数未知",
            after="缓存清空，后续域名解析重新向 DNS 服务器查询",
            note="不修改任何网络配置，可反复执行",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        return []  # 无状态变更，无需备份

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        rc, out = pw.flush_dns_cache()
        result.finished_at = pw.now()
        if rc != 0:
            result.state = ActionState.FAILED
            result.message = "清空 DNS 缓存失败"
            result.error = f"ipconfig /flushdns 返回码 {rc}：{out or '（无输出）'}"
            return result
        result.message = "DNS 缓存已清空"
        if out:
            result.detail.append(out.strip())
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        # 缓存清空没有可读回的目标状态；用"命令仍可正常执行"作为最基本证据，
        # 不谎称"已验证缓存为空"。
        rc, out = pw.run_cmd(["ipconfig", "/displaydns"], timeout=15)
        if rc != 0:
            return False, f"读取 DNS 缓存失败（返回码 {rc}）：{out or '（无输出）'}"
        return True, "缓存已清空，DNS 客户端可正常响应"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        # 无备份项 = 无可回滚内容。这里如实返回 SKIPPED，而不是假装恢复成功。
        return ActionResult(
            action_id=self.action_id,
            state=ActionState.SKIPPED,
            message="该动作不修改任何持久化配置，无需回滚",
            started_at=pw.now(),
            finished_at=pw.now(),
        )


def _dns_cache_entry_count() -> int:
    rc, out = pw.run_cmd(["ipconfig", "/displaydns"], timeout=15)
    if rc != 0:
        return 0
    return sum(1 for line in out.splitlines() if "记录名称" in line or "Record Name" in line)


# --------------------------------------------------------------------------- #
# dns.set_public
# --------------------------------------------------------------------------- #
@register_action("dns.set_public")
class DnsSetPublicAction(BaseAction):
    """把当前上网网卡的 DNS 切成公共 DNS。

    servers 必须可由调用方覆盖：不同地区、不同运营商对公共 DNS 的连通性差异很大，
    用户可能指定 114 或 Cloudflare。默认值只是"开箱可用"的保守选择。
    """

    action_id = "dns.set_public"

    def __init__(self, servers: Sequence[str] | None = None) -> None:
        self.servers = _validate_servers(list(servers) if servers else list(DEFAULT_PUBLIC_DNS))

    def preview(self, ctx: Any) -> ChangePreview:
        primary = require_primary(ctx)
        current, was_dhcp = _dns_snapshot(ctx, primary.name)
        return ChangePreview(
            target=f"{primary.name} / DNS 服务器",
            before=_format_servers(current, was_dhcp),
            after="、".join(self.servers) + "（手动配置，静态）",
            note="原 DNS 配置会完整备份，可在备份页一键还原；IPv6 DNS 不受影响",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        primary = require_primary(ctx)
        servers, was_dhcp = _dns_snapshot(ctx, primary.name)
        key = f"dns:{primary.interface_guid}"
        store.capture_state(
            session,
            key=key,
            kind="dns",
            label=f"{primary.name} 的 DNS 配置",
            payload={
                "interface_guid": primary.interface_guid,
                "interface_index": primary.if_index,
                "alias": primary.name,
                "servers": servers,
                # 回滚时"原本是 DHCP"和"原本是静态列表"走不同命令，这个字段不能省
                "was_dhcp": was_dhcp,
            },
        )
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        primary = require_primary(ctx)
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        out = netsh_dns_static(primary.name, self.servers)
        result.finished_at = pw.now()
        result.message = f"已将「{primary.name}」的 DNS 设置为 {'、'.join(self.servers)}"
        if out:
            result.detail.extend(line for line in out.splitlines() if line.strip())
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        primary = require_primary(ctx)
        expected = set(self.servers)
        last: list[str] = []
        # DNS 设置是异步生效的（DNS 客户端服务的注册有短暂延迟），给两次机会
        for attempt in range(2):
            last = _read_dns_by_index(primary.if_index)
            if set(last) == expected:
                return True, f"读回 DNS 为 {'、'.join(last)}，与目标一致"
            if attempt == 0:
                import time

                time.sleep(1.0)
        return False, (
            f"读回 DNS 为 {'、'.join(last) or '空'}，与目标 {'、'.join(self.servers)} 不一致"
        )

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="dns",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# dns.restore_dhcp
# --------------------------------------------------------------------------- #
@register_action("dns.restore_dhcp")
class DnsRestoreDhcpAction(BaseAction):
    """把 DNS 退回 DHCP 自动下发。

    公司 / 校园网常要求使用内网 DNS，此时手工设的公共 DNS 会导致内网域名解析失败，
    这条动作就是给那种场景的退路。
    """

    action_id = "dns.restore_dhcp"

    def preview(self, ctx: Any) -> ChangePreview:
        primary = require_primary(ctx)
        current, was_dhcp = _dns_snapshot(ctx, primary.name)
        after = "自动获取（沿用 DHCP 下发的 DNS）" if was_dhcp else "自动获取（改为由 DHCP 下发）"
        return ChangePreview(
            target=f"{primary.name} / DNS 服务器",
            before=_format_servers(current, was_dhcp),
            after=after + "，DNS 后缀按 DHCP 选项注册",
            note="原 DNS 配置会完整备份；若当前已是自动获取，执行后无变化",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        primary = require_primary(ctx)
        servers, was_dhcp = _dns_snapshot(ctx, primary.name)
        key = f"dns:{primary.interface_guid}"
        store.capture_state(
            session,
            key=key,
            kind="dns",
            label=f"{primary.name} 的 DNS 配置",
            payload={
                "interface_guid": primary.interface_guid,
                "interface_index": primary.if_index,
                "alias": primary.name,
                "servers": servers,
                "was_dhcp": was_dhcp,
            },
        )
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        primary = require_primary(ctx)
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        out = netsh_dns_dhcp(primary.name)
        result.finished_at = pw.now()
        result.message = f"「{primary.name}」的 DNS 已改为自动获取"
        if out:
            result.detail.extend(line for line in out.splitlines() if line.strip())
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        primary = require_primary(ctx)
        _, was_dhcp = read_dns_config(primary.name)
        if was_dhcp:
            return True, "已确认为 DHCP 自动获取"
        servers = _read_dns_by_index(primary.if_index)
        if not servers:
            return True, "配置源已切换为自动获取（当前未下发服务器）"
        return False, f"仍为手动配置：{'、'.join(servers)}"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="dns",
                                      action_id=self.action_id)


__all__ = ["DEFAULT_PUBLIC_DNS", "DnsFlushCacheAction", "DnsRestoreDhcpAction",
           "DnsSetPublicAction"]
