"""TCP/IP 全局参数与协议栈重置。

三个动作的破坏性依次上升：
    tcp.autotuning  -> 只改一个全局开关，可精确回滚
    tcp.heuristics  -> 同上
    tcp.reset_stack -> 重置协议栈，必须重启，回滚只能靠注册表整体导入

reset_stack 的回滚边界要在报告里说清：netsh ip reset 会重写注册表项，
而"导回备份"只能在重启前把参数恢复，已经生效的协议栈状态无法在线撤销。
"""
from __future__ import annotations

from typing import Any

from .. import platform_win as pw
from ..models import ActionState, ActionResult, ChangePreview
from .base import (
    BaseAction,
    capture_registry_or_state,
    netsh_tcp_set,
    read_tcp_global,
    register_action,
    run_or_raise,
    tcp_value,
)

TCPIP_PARAMS = r"HKLM\SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
WINSOCK_PARAMS = r"HKLM\SYSTEM\CurrentControlSet\Services\WinSock2\Parameters"

_RESTART_NOTE = "该操作需要重启计算机才能完全生效"


def _tcp_global(ctx: Any) -> dict[str, str]:
    cached = getattr(ctx, "cached", None)
    if callable(cached):
        return cached("repair:tcp_global", read_tcp_global)
    return read_tcp_global()


# --------------------------------------------------------------------------- #
# tcp.autotuning
# --------------------------------------------------------------------------- #
@register_action("tcp.autotuning")
class TcpAutotuningAction(BaseAction):
    """恢复 TCP 接收窗口自动调节为 normal。

    被手动关成 disabled/restricted 后，高延迟链路（跨运营商、出国）吞吐会塌到
    原来的几分之一，而用户通常完全不知道是自己或某个"优化软件"关的。
    """

    action_id = "tcp.autotuning"
    target_value = "normal"
    _keywords = ("autotuning", "自动调谐", "自动调节")

    def preview(self, ctx: Any) -> ChangePreview:
        values = _tcp_global(ctx)
        current = tcp_value(values, *self._keywords) or "未知"
        return ChangePreview(
            target="TCP 接收窗口自动调节级别",
            before=current,
            after=self.target_value,
            note="只改全局参数，不重置协议栈，无需重启",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        values = _tcp_global(ctx)
        current = tcp_value(values, *self._keywords)
        if not current:
            # 拿不到当前值就等于"无法回滚"，这种情况下宁可中止，也不要盲改
            raise RuntimeError(
                "无法从 `netsh int tcp show global` 解析出当前的 autotuning 级别，"
                f"原始输出：{values or '（空）'}"
            )
        key = "tcp:autotuning"
        store.capture_state(
            session,
            key=key,
            kind="tcp",
            label="TCP 自动调谐级别",
            payload={"level": current, "source": "netsh int tcp show global"},
        )
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        out = netsh_tcp_set("autotuninglevel", self.target_value)
        result.finished_at = pw.now()
        result.message = f"TCP 自动调谐级别已设为 {self.target_value}"
        if out:
            result.detail.extend(line for line in out.splitlines() if line.strip())
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        # 现读，不复用 ctx 缓存：verify 的意义就是绕开缓存看真实状态
        values = read_tcp_global()
        current = tcp_value(values, *self._keywords)
        if current.strip().lower().startswith(self.target_value):
            return True, f"读回 autotuning = {current}"
        return False, f"读回 autotuning = {current or '解析失败'}，期望 {self.target_value}"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="tcp",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# tcp.heuristics
# --------------------------------------------------------------------------- #
@register_action("tcp.heuristics")
class TcpHeuristicsAction(BaseAction):
    """关闭 Windows 的窗口缩放启发式禁用策略。

    【命令形态很重要】这条设置不在 `set global` 里。`set global heuristics=...`
    在本机直接报"'heuristics' 不是这个指令的有效参数"，而正确写法是：
        netsh int tcp set heuristics wsh=disabled
    注意 netsh 此时**返回码仍为 0**，只在文本里报错，因此 base.run_or_raise
    会额外扫描输出内容，不能只看返回码。

    【为什么本动作通常被 plan() 剔除】Win10 1803 之后系统已不再实际使用该参数，
    `set heuristics ?` 自己就写着 "will have no effect"。available() 据此把本项
    判为"无需修复"，避免为了一个不影响行为的数字去改注册表，也避免它拖累整轮修复。
    """

    action_id = "tcp.heuristics"
    target_value = "disabled"
    _keywords = ("窗口缩放启发", "window scaling heuristics", "启发")

    def _show(self) -> dict[str, str]:
        """读取 `netsh int tcp show heuristics`，返回 {键: 值}。

        实测（Win11 26300）：这条命令**存在**，输出首行为「TCP 窗口缩放启发参数」，
        其中「窗口缩放启发 : disabled」。所以不能用"命令不存在"来判断可用性。
        """
        out = run_or_raise(["netsh", "int", "tcp", "show", "heuristics"],
                           timeout=25, what="读取窗口缩放启发式参数")
        values: dict[str, str] = {}
        for line in out.splitlines():
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            values[key.strip()] = value.strip()
        return values

    def _current(self, values: dict[str, str]) -> str:
        return tcp_value(values, *self._keywords)

    def available(self, ctx: Any) -> tuple[bool, str]:
        """判定本机是否需要/能够修复窗口缩放启发式。

        判据不是"参数是否存在"（它确实存在），而是"改了会不会有效"：
        `netsh int tcp set heuristics ?` 在本机明确输出
            "Window scaling heuristics are not supported in this version of Windows.
             Changing window scaling heuristics settings will have no effect."
        这种情况下执行修复只是把注册表状态改成一个不影响行为的数字，属于
        对用户无收益的系统改动，按"不必要就不动系统"原则直接标为不可用。
        """
        try:
            values = self._show()
        except RuntimeError as exc:
            return False, f"无法读取窗口缩放启发式参数，跳过该项：{exc}"
        if not self._current(values):
            return False, "当前输出中未识别到窗口缩放启发式参数，该项无需修复"

        rc, help_out = pw.run_cmd(["netsh", "int", "tcp", "set", "heuristics", "?"],
                                  timeout=20)
        # 中文系统输出「此版本的 Windows 不支持窗口缩放启发。更改窗口缩放启发设置将没有任何效果。」
        # 英文系统输出 "...not supported in this version of Windows ... will have no effect."
        # 两种都要认，只匹配英文会在本机漏判。
        ineffective_marks = ("no effect", "没有任何效果", "无任何效果", "not supported",
                             "不支持窗口缩放启发")
        if rc == 0 and any(mark in help_out.lower() or mark in help_out
                           for mark in ineffective_marks):
            return False, (
                "当前 Windows 版本已不再实际使用窗口缩放启发式（系统自带说明："
                "更改窗口缩放启发设置将没有任何效果），该项无需修复"
            )
        return True, ""

    def preview(self, ctx: Any) -> ChangePreview:
        try:
            current = self._current(self._show()) or "未知"
        except RuntimeError as exc:
            current = f"读取失败（{exc}）"
        return ChangePreview(
            target="TCP 窗口缩放启发式（wsh）",
            before=current,
            after=self.target_value,
            note="该设置在新版 Windows 上不再影响行为，仅记录状态；旧版系统可改善高延迟吞吐",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        values = self._show()
        current = self._current(values)
        if not current:
            raise RuntimeError(
                "无法从 `netsh int tcp show heuristics` 解析出窗口缩放启发式级别，"
                f"已中止以免无法回滚。原始输出：{values or '（空）'}"
            )
        key = "tcp:heuristics"
        store.capture_state(
            session,
            key=key,
            kind="tcp",
            label="TCP 窗口缩放启发式级别",
            payload={"level": current, "source": "netsh int tcp show heuristics"},
        )
        return [key]

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        before = self._current(self._show())
        if before.strip().lower() == self.target_value:
            result.state = ActionState.SKIPPED
            result.message = f"窗口缩放启发式已是 {self.target_value}，无需修改"
            result.finished_at = pw.now()
            return result

        # wsh 是这条设置的实际参数名；forcews 与本动作无关，不碰
        out = run_or_raise(["netsh", "int", "tcp", "set", "heuristics",
                            f"wsh={self.target_value}"],
                           timeout=25, what="设置窗口缩放启发式为 disabled")
        result.finished_at = pw.now()
        result.message = f"窗口缩放启发式已设为 {self.target_value}（原值 {before}）"
        if out:
            result.detail.extend(line for line in out.splitlines() if line.strip())
        result.detail.append(
            "说明：Windows 10/11 已不再实际使用该参数（系统提示 changing window scaling "
            "heuristics settings will have no effect），本项仅为对齐旧系统与状态一致性"
        )
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        values = self._show()
        current = self._current(values)
        if current.strip().lower() == self.target_value:
            return True, f"读回窗口缩放启发式 = {current}"
        return False, f"读回窗口缩放启发式 = {current or '解析失败'}，期望 {self.target_value}"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="tcp",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# tcp.reset_stack
# --------------------------------------------------------------------------- #
@register_action("tcp.reset_stack")
class TcpResetStackAction(BaseAction):
    """重置 TCP/IP 协议栈 + Winsock 目录。

    这是"最后一招"：修复 LSP 残留、驱动挂接错乱、以及 netsh 参数已经改不动的
    情况。代价是必须重启，且部分安全软件的过滤驱动需要重装。
    """

    action_id = "tcp.reset_stack"

    def preview(self, ctx: Any) -> ChangePreview:
        return ChangePreview(
            target="TCP/IP 协议栈与 Winsock 目录",
            before="当前协议栈状态（含第三方 LSP / 过滤驱动注册）",
            after="协议栈参数复位为系统默认，Winsock 目录重建；"
                  "第三方 LSP 注册被清除，相关安全软件可能需重装组件",
            note=f"{_RESTART_NOTE}；注册表会整份备份，重启前可用备份页回滚",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        keys: list[str] = []
        keys.append(capture_registry_or_state(
            store, session,
            key="reg:tcpip",
            hive_path=TCPIP_PARAMS,
            label="TCP/IP 参数注册表",
            fallback_payload={"kind": "registry_missing", "what": "Tcpip\\Parameters"},
        ))
        keys.append(capture_registry_or_state(
            store, session,
            key="reg:winsock2",
            hive_path=WINSOCK_PARAMS,
            label="WinSock2 参数注册表",
            fallback_payload={"kind": "registry_missing", "what": "WinSock2\\Parameters"},
        ))
        return keys

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        result.detail.append(f"⚠ {_RESTART_NOTE}")

        rc_ip, out_ip = pw.run_cmd(["netsh", "int", "ip", "reset"], timeout=60)
        rc_winsock, out_winsock = pw.run_cmd(["netsh", "winsock", "reset"], timeout=60)
        result.finished_at = pw.now()

        result.detail.append(f"netsh int ip reset -> 返回码 {rc_ip}")
        if out_ip:
            result.detail.extend(line for line in out_ip.splitlines() if line.strip())
        result.detail.append(f"netsh winsock reset -> 返回码 {rc_winsock}")
        if out_winsock:
            result.detail.extend(line for line in out_winsock.splitlines() if line.strip())

        if rc_ip != 0 or rc_winsock != 0:
            result.state = ActionState.FAILED
            result.message = "协议栈重置未完全下发"
            result.error = (
                f"netsh int ip reset 返回码 {rc_ip}：{out_ip or '（无输出）'}\n"
                f"netsh winsock reset 返回码 {rc_winsock}：{out_winsock or '（无输出）'}"
            )
            result.detail.append(f"⚠ {_RESTART_NOTE}")
            return result

        result.message = "TCP/IP 协议栈与 Winsock 已重置，需要重启计算机才能完全生效"
        result.detail.append(f"⚠ 回滚只能恢复注册表参数，已生效的协议栈状态需重启后才能被备份覆盖")
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        """只核对"命令已成功下发"，不谎称"已生效"。

        netsh ip reset 的生效时机在下次启动，当前进程无论如何都读不到变化。
        把"需要重启"写成 verified 的说明，比给一个假的 True 更有用。
        """
        rc, out = pw.run_cmd(["netsh", "int", "ip", "show", "global"], timeout=20)
        if rc != 0:
            return False, f"协议栈重置后 `netsh int ip show global` 返回 {rc}：{out[:300]}"
        return True, "已下发，需重启生效（当前进程无法观测生效结果）"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="registry",
                                      action_id=self.action_id)


__all__ = ["TCPIP_PARAMS", "TcpAutotuningAction", "TcpHeuristicsAction",
           "TcpResetStackAction", "WINSOCK_PARAMS"]
