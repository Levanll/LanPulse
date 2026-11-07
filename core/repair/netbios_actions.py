r"""NetBIOS over TCP/IP 修复动作。

为什么要关：NetBIOS 名字服务会在局域网内广播主机名，在咖啡厅 / 酒店等公共
Wi-Fi 上等于主动外泄"这台机器叫什么、开着哪些共享"，而它对接入互联网毫无帮助
（上网只依赖 IP + DNS）。

写的是 `NetbiosOptions` DWORD：
    0 = 由 DHCP 决定（默认）
    1 = 启用
    2 = 禁用   <- 本动作
注册表路径是 `NetBT\Parameters\Interfaces\Tcpip_{GUID}`。注意大小写不敏感，
但 `{GUID}` 必须与网卡 InterfaceGuid 完全一致（含花括号）。
"""
from __future__ import annotations

from typing import Any

from ..models import ActionState, ActionResult, ChangePreview
from .base import BaseAction, register_action, require_primary

NETBT_ROOT = r"SYSTEM\CurrentControlSet\Services\NetBT\Parameters\Interfaces"
# 写注册表用 HKLM 缩写形式；读用 winreg 常量。
NETBIOS_DISABLED = 2


def _interface_key(guid: str) -> str:
    """NetBT 下的子键名形如 Tcpip_{BCA1...}。

    网卡 InterfaceGuid 通常自带花括号；这里统一补齐，避免出现 Tcpip_{BCA1..}
    与 Tcpip_BCA1.. 两种拼法导致"写了但没生效"。
    """
    core = guid.strip().strip("{}")
    if not core:
        raise ValueError("网卡 GUID 为空，无法定位 NetBIOS 注册表项")
    return f"Tcpip_{{{core.upper()}}}"


def _full_path(guid: str) -> str:
    return f"{NETBT_ROOT}\\{_interface_key(guid)}"


def _read_options(guid: str) -> int | None:
    """读取当前 NetbiosOptions，键或值不存在返回 None（不编造默认值 0）。"""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _full_path(guid)) as key:
            value, _ = winreg.QueryValueEx(key, "NetbiosOptions")
            return int(value)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RuntimeError(f"读取 NetBIOS 配置失败（{_full_path(guid)}）：{exc}") from exc


def _write_options(guid: str, value: int) -> None:
    import winreg

    path = _full_path(guid)
    # 子键可能尚未创建（网卡刚装上、NetBT 还没写自己的配置）。这是 Windows
    # 约定的标准位置，创建它并写入是正确的做法；备份里已记录"原本不存在"。
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, "NetbiosOptions", 0, winreg.REG_DWORD, int(value))


@register_action("netbios.disable_public")
class NetbiosDisablePublicAction(BaseAction):
    """在公网网卡上禁用 NetBIOS over TCP/IP。"""

    action_id = "netbios.disable_public"

    def preview(self, ctx: Any) -> ChangePreview:
        primary = require_primary(ctx)
        is_public = _looks_public(primary.primary_ipv4)
        current = _read_options(primary.interface_guid)
        if current is None:
            before = "未配置（等同由 DHCP 决定，通常为启用）"
        else:
            before = {0: "0（由 DHCP 决定）", 1: "1（启用）", 2: "2（已禁用）"}.get(
                str(current), str(current)
            )
        return ChangePreview(
            target=f"{primary.name} / NetBIOS over TCP/IP",
            before=before,
            after=f"{NETBIOS_DISABLED}（禁用）",
            note="仅影响局域网名字广播，不影响上网、DNS 与现代 SMB 文件共享；"
                 + ("当前地址看起来是公网地址" if is_public else
                    "当前是内网地址，若依赖「网上邻居」按名字访问共享请谨慎"),
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        primary = require_primary(ctx)
        path = _full_path(primary.interface_guid)
        key = "reg:netbt"
        try:
            store.capture_registry(
                session, f"HKLM\\{path}", key=key, label="NetBIOS 网卡配置"
            )
            return [key]
        except (RuntimeError, FileNotFoundError) as exc:
            # 子键不存在时 reg export 必然失败。此时必须记录"原本不存在"，
            # 回滚才知道应当删除该值而不是改成某个数字。
            # 退化 key 用 `.snapshot` 后缀：Windows 文件名里的冒号是 NTFS
            # 备用数据流分隔符，key 里再叠冒号会让 capture_state 直接 OSError。
            alt_key = f"{key}.snapshot"
            store.capture_state(
                session,
                key=alt_key,
                kind="netbios",
                label="NetBIOS 网卡配置（原注册表项不存在）",
                payload={
                    "interface_guid": primary.interface_guid,
                    "alias": primary.name,
                    "hive_path": f"HKLM\\{path}",
                    "existed": False,
                    "applied_value": NETBIOS_DISABLED,
                    "registry_export_error": str(exc),
                },
            )
            return [alt_key]

    def apply(self, ctx: Any) -> ActionResult:
        primary = require_primary(ctx)
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        before = _read_options(primary.interface_guid)
        if before == NETBIOS_DISABLED:
            result.state = ActionState.SKIPPED
            result.message = "该网卡的 NetBIOS 已是禁用状态，无需修改"
            result.finished_at = pw.now()
            return result

        _write_options(primary.interface_guid, NETBIOS_DISABLED)
        result.finished_at = pw.now()
        result.message = f"已在「{primary.name}」上禁用 NetBIOS over TCP/IP"
        result.detail.append(
            f"NetbiosOptions: {before if before is not None else '未配置'} -> {NETBIOS_DISABLED}"
        )
        result.detail.append(f"注册表项：HKLM\\{_full_path(primary.interface_guid)}")
        result.detail.append("该改动对当前连接即时生效，无需重启")
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        primary = require_primary(ctx)
        current = _read_options(primary.interface_guid)
        if current == NETBIOS_DISABLED:
            return True, f"读回 NetbiosOptions={current}（已禁用）"
        if current is None:
            return False, "读回时注册表值不存在，写入可能被安全软件拦截"
        return False, f"读回 NetbiosOptions={current}，期望 {NETBIOS_DISABLED}"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="registry",
                                      action_id=self.action_id)


def _looks_public(ip: str) -> bool:
    """粗判是否是公网地址。只用于 preview 文案，不参与任何决策。"""
    if not ip:
        return False
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts):
        return False
    a, b = int(parts[0]), int(parts[1])
    if a == 10 or a == 127:
        return False
    if a == 172 and 16 <= b <= 31:
        return False
    if a == 192 and b == 168:
        return False
    if a == 169 and b == 254:
        return False
    return True


__all__ = ["NETBIOS_DISABLED", "NETBT_ROOT", "NetbiosDisablePublicAction"]
