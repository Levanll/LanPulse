"""系统代理（WinINET / WinHTTP）修复动作。

为什么用 winreg 而不是 `reg add`：
    Internet Settings 下的值是混合类型（ProxyEnable 是 DWORD，ProxyServer 是
    REG_SZ，ProxyOverride 是带分号的 REG_SZ）。走命令行要处理三层引号转义，
    在中文路径/含空格的值上极易写坏，而写坏代理键会直接让用户彻底无法上网。
    直接用 winreg 能精确控制类型，且删除/保留是显式操作。

两个动作的分工：
    proxy.reset        —— 清掉残留代理，恢复直连（最常见的"网页打不开但 QQ 能上"）
    proxy.restore_auto —— 清代理 + 重置 WinHTTP 直连（企业环境常用 WinHTTP 代理）
"""
from __future__ import annotations

import ctypes
from typing import Any

from .. import platform_win as pw
from ..models import ActionState, ActionResult, ChangePreview
from .base import BaseAction, register_action, run_or_raise

WININET_KEY = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
WININET_KEY_FULL = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

# INTERNET_OPTION_* 常量（WinINET API），让改动立即对其他进程生效
INTERNET_OPTION_REFRESH = 37
INTERNET_OPTION_SETTINGS_CHANGED = 39


# --------------------------------------------------------------------------- #
# 注册表读写
# --------------------------------------------------------------------------- #
def _open_wininet(write: bool):
    import winreg

    return winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        WININET_KEY,
        0,
        winreg.KEY_READ | (winreg.KEY_WRITE if write else 0),
    )


def read_proxy_state() -> dict[str, Any]:
    """读取当前 WinINET 代理状态。值不存在记为 None，不编造默认值。"""
    import winreg

    state: dict[str, Any] = {"ProxyEnable": None, "ProxyServer": None, "ProxyOverride": None}
    try:
        with _open_wininet(write=False) as key:
            for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
                try:
                    value, _ = winreg.QueryValueEx(key, name)
                    state[name] = value
                except FileNotFoundError:
                    state[name] = None
                except OSError as exc:
                    raise RuntimeError(f"读取注册表项 {name} 失败：{exc}") from exc
    except FileNotFoundError:
        # 整个 Internet Settings 键都不存在（极精简系统），按"全未配置"处理
        return state
    return state


def _write_dword(name: str, value: int) -> None:
    import winreg

    with _open_wininet(write=True) as key:
        winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, int(value))


def _delete_value(name: str) -> bool:
    """删除值，返回是否真的存在并删除。不存在不算错误。"""
    import winreg

    try:
        with _open_wininet(write=True) as key:
            winreg.DeleteValue(key, name)
            return True
    except FileNotFoundError:
        return False


def notify_proxy_changed() -> tuple[bool, str]:
    """通知系统代理设置已变更。

    失败不算动作失败：注册表已经写对了，只是其它进程（浏览器）需要等下一次
    自己读取设置才会生效。但必须把失败原因写进 detail，不能让用户以为已生效。
    """
    try:
        wininet = ctypes.WinDLL("wininet.dll")
        internet_set_option = wininet.InternetSetOptionW
        internet_set_option.argtypes = [ctypes.c_void_p, ctypes.c_ulong,
                                        ctypes.c_void_p, ctypes.c_ulong]
        internet_set_option.restype = ctypes.c_bool
    except (OSError, AttributeError) as exc:
        return False, f"加载 wininet.dll 失败：{exc}"

    errors: list[str] = []
    for option, label in (
        (INTERNET_OPTION_SETTINGS_CHANGED, "SETTINGS_CHANGED"),
        (INTERNET_OPTION_REFRESH, "REFRESH"),
    ):
        try:
            if not internet_set_option(None, option, None, 0):
                errors.append(f"{label} 返回失败（GetLastError={ctypes.get_last_error()}）")
        except OSError as exc:
            errors.append(f"{label} 调用异常：{exc}")

    if errors:
        return False, "；".join(errors)
    return True, "已通知系统刷新代理设置"


def _describe(state: dict[str, Any]) -> str:
    enable = state.get("ProxyEnable")
    server = state.get("ProxyServer")
    if enable in (0, None) and not server:
        return "直连（未启用代理）"
    parts = [f"ProxyEnable={enable}"]
    if server:
        parts.append(f"ProxyServer={server}")
    return "、".join(parts) + "（已启用代理）"


# --------------------------------------------------------------------------- #
# proxy.reset
# --------------------------------------------------------------------------- #
@register_action("proxy.reset")
class ProxyResetAction(BaseAction):
    """关闭残留的系统代理。

    典型故障：代理软件被强制结束后，WinINET 里仍留着 ProxyEnable=1 指向一个
    已经没人监听的本地端口。症状是浏览器全部报连接失败，而 QQ / 微信正常。
    """

    action_id = "proxy.reset"

    def preview(self, ctx: Any) -> ChangePreview:
        state = read_proxy_state()
        keep = state.get("ProxyOverride")
        return ChangePreview(
            target="系统代理（WinINET：HKCU Internet Settings）",
            before=_describe(state),
            after="直连（ProxyEnable=0，ProxyServer 删除）"
                  + (f"；保留例外列表 {keep}" if keep else ""),
            note="不改动 WinHTTP 代理与自动检测设置；原值会完整备份，可一键还原",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        key = "reg:wininet"
        # reg export 会连 ProxyOverride 等所有值一起带走，回滚时 reg import 即可整项还原。
        # 这比逐个值记录更可靠：我们改的是"一项配置"，就该整项备份。
        store.capture_registry(session, WININET_KEY_FULL, key=key,
                               label="系统代理设置（Internet Settings）")
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        before = read_proxy_state()

        # 先写 ProxyEnable=0 再删 ProxyServer：顺序反过来的话，中间那一瞬
        # 可能出现"代理启用但服务器为空"，某些客户端会直接判定网络不可用。
        _write_dword("ProxyEnable", 0)
        deleted = _delete_value("ProxyServer")
        after = read_proxy_state()
        result.finished_at = pw.now()

        result.detail.append(f"ProxyEnable: {before.get('ProxyEnable')} -> 0")
        result.detail.append(
            f"ProxyServer: {before.get('ProxyServer')} -> 已删除" if deleted
            else "ProxyServer: 原本就不存在"
        )
        if before.get("ProxyOverride"):
            result.detail.append(f"保留 ProxyOverride={before.get('ProxyOverride')}")

        ok, message = notify_proxy_changed()
        result.detail.append(("代理设置刷新：" if ok else "代理设置刷新失败（不影响本次修改）：") + message)

        if after.get("ProxyEnable") != 0:
            result.state = ActionState.FAILED
            result.message = "写入 ProxyEnable=0 后读回仍不为 0"
            result.error = f"读回 ProxyEnable={after.get('ProxyEnable')}"
            return result

        result.message = "系统代理已关闭，浏览器将直接连接网络"
        result.verified = None  # 由 engine 在 verify 阶段回填
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        state = read_proxy_state()
        if state.get("ProxyEnable") != 0:
            return False, f"ProxyEnable 读回为 {state.get('ProxyEnable')}，期望 0"
        if state.get("ProxyServer"):
            return False, f"ProxyServer 仍存在：{state.get('ProxyServer')}"
        return True, "ProxyEnable=0 且 ProxyServer 已清除"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="registry",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# proxy.restore_auto
# --------------------------------------------------------------------------- #
@register_action("proxy.restore_auto")
class ProxyRestoreAutoAction(BaseAction):
    """恢复代理为"自动"形态。

    【实现范围刻意收窄】自动检测开关的权威存储是 DefaultConnectionSettings 的
    二进制第 9 字节 bit3。直接改这段二进制风险远高于收益（结构随系统版本变化、
    写错会让 IE 组件与 WinHTTP 都失效），所以这里只做两件安全的事：
        1. 关闭 WinINET 静态代理（用户至少能上网）；
        2. `netsh winhttp reset proxy` 恢复 WinHTTP 直连。
    自动检测的二进制位保持原样，并在 detail 里如实告知用户。
    """

    action_id = "proxy.restore_auto"

    def preview(self, ctx: Any) -> ChangePreview:
        state = read_proxy_state()
        winhttp = _winhttp_proxy_text()
        return ChangePreview(
            target="系统代理（WinINET 静态代理 + WinHTTP 代理配置）",
            before=f"WinINET：{_describe(state)}；WinHTTP：{winhttp}",
            after="WinINET 静态代理关闭；WinHTTP 恢复为直接访问",
            note="不改动「自动检测设置」的二进制开关（DefaultConnectionSettings），"
                 "该位保持原样",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        keys: list[str] = []
        keys.append(store.capture_registry(
            session, WININET_KEY_FULL, key="reg:wininet",
            label="系统代理设置（Internet Settings）",
        ).key)
        # WinHTTP 是另一套配置，必须单独记录；否则回滚后 WinHTTP 代理会永久丢失
        keys.append(store.capture_state(
            session,
            key="winhttp:proxy",
            kind="winhttp",
            label="WinHTTP 代理配置",
            payload={"show_proxy_output": _winhttp_proxy_text()},
        ).key)
        return keys

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        before = read_proxy_state()
        _write_dword("ProxyEnable", 0)
        result.detail.append(f"ProxyEnable: {before.get('ProxyEnable')} -> 0（静态代理已关闭）")

        out = run_or_raise(["netsh", "winhttp", "reset", "proxy"], timeout=30,
                           what="恢复 WinHTTP 直连")
        result.finished_at = pw.now()
        if out:
            result.detail.extend(line for line in out.splitlines() if line.strip())

        ok, message = notify_proxy_changed()
        result.detail.append(("代理设置刷新：" if ok else "代理设置刷新失败（不影响本次修改）：") + message)
        result.detail.append(
            "自动检测设置（DefaultConnectionSettings 第 9 字节 bit3）未改动："
            "直接编辑该二进制在版本升级后可能损坏连接配置，故保持原样。"
        )
        result.message = "已关闭静态代理并恢复 WinHTTP 直连（自动检测开关未改动）"
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        state = read_proxy_state()
        if state.get("ProxyEnable") not in (0, None):
            return False, f"ProxyEnable 读回为 {state.get('ProxyEnable')}，期望 0"
        text = _winhttp_proxy_text().lower()
        direct_marks = ("直接访问", "direct access", "没有代理服务器", "no proxy server")
        if not any(mark in text for mark in direct_marks):
            return False, f"WinHTTP 仍非直连：{text.strip()[:200]}"
        return True, "WinINET 直连，WinHTTP 为直接访问"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="registry",
                                      action_id=self.action_id)


def _winhttp_proxy_text() -> str:
    rc, out = pw.run_cmd(["netsh", "winhttp", "show", "proxy"], timeout=20)
    if rc != 0:
        return f"（读取失败，返回码 {rc}）{out.strip()[:200]}"
    return out.strip()


__all__ = [
    "INTERNET_OPTION_REFRESH",
    "INTERNET_OPTION_SETTINGS_CHANGED",
    "ProxyResetAction",
    "ProxyRestoreAutoAction",
    "WININET_KEY",
    "WININET_KEY_FULL",
    "notify_proxy_changed",
    "read_proxy_state",
]
