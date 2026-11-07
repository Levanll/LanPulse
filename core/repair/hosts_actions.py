"""HOSTS 文件修复动作。

为什么这里对"字节级保留"要求这么高：
    HOSTS 是用户唯一能手工维护的解析入口。清一条广告屏蔽记录却顺手把用户
    手动排版的注释、空行、BOM 或 CRLF 改掉，会被当成"软件乱改我文件"，而且
    用户很难复原。所以本模块只做一件事：删掉指定行号，其余字节原样拼回。

解析口径复用 core/checks/hosts_check.parse_hosts —— 检测说"可疑"、修复才删，
两处共用同一套规则，避免出现"检测报了但清理不动"或反之的错位。
"""
from __future__ import annotations

from typing import Any

from .. import platform_win as pw
from ..models import ActionState, ActionResult, ChangePreview
from .base import BaseAction, register_action

# Windows 默认 hosts 模板。行尾必须是 CRLF、编码为 UTF-8 无 BOM：
# 部分老旧网络组件（以及不少用户常用的记事本）对 LF-only 的 hosts 会有兼容性问题。
DEFAULT_HOSTS_TEXT = (
    "# Copyright (c) 1993-2009 Microsoft Corp.\r\n"
    "#\r\n"
    "# This is a sample HOSTS file used by Microsoft TCP/IP for Windows.\r\n"
    "#\r\n"
    "# This file contains the mappings of IP addresses to host names. Each\r\n"
    "# entry should be kept on an individual line. The IP address should\r\n"
    "# be placed in the first column followed by the corresponding host name.\r\n"
    "# The IP address and the host name should be separated by at least one\r\n"
    "# space.\r\n"
    "#\r\n"
    "# Additionally, comments (such as these) may be inserted on individual\r\n"
    "# lines or following the machine name denoted by a '#' symbol.\r\n"
    "#\r\n"
    "# For example:\r\n"
    "#\r\n"
    "#      102.54.94.97     rhino.acme.com          # source server\r\n"
    "#       38.25.63.10     x.acme.com              # x client host\r\n"
    "\r\n"
    "# localhost name resolution is handled within DNS itself.\r\n"
    "#\t127.0.0.1       localhost\r\n"
    "#\t::1             localhost\r\n"
)


def _parse(text: str):
    """统一入口，避免各处 import 路径写法不一致。"""
    from ..checks.hosts_check import parse_hosts

    return parse_hosts(text)


def _read_hosts() -> str:
    return pw.read_text_file(pw.HOSTS_PATH)


def _split_keepends(text: str) -> list[str]:
    """按与 parse_hosts 完全一致的行切分规则切分，并保留行尾。

    parse_hosts 用的是 str.splitlines()，这里用 splitlines(keepends=True)：
    两者的分行位置严格相同，因此行号可以安全地跨函数对应。
    """
    return text.splitlines(keepends=True)


# --------------------------------------------------------------------------- #
# hosts.clean_bad_lines
# --------------------------------------------------------------------------- #
@register_action("hosts.clean_bad_lines")
class HostsCleanBadLinesAction(BaseAction):
    """只删除可疑行，其余内容一个字节都不动。"""

    action_id = "hosts.clean_bad_lines"

    def preview(self, ctx: Any) -> ChangePreview:
        analysis = _parse(_read_hosts())
        suspicious = analysis.suspicious
        if not suspicious:
            return ChangePreview(
                target=f"HOSTS 文件（{pw.HOSTS_PATH}）",
                before=f"{len(analysis.entries)} 条有效映射，未发现可疑记录",
                after="内容不变（执行时该动作会被跳过）",
                note="没有需要清理的记录时不会写入文件",
            )
        sample = "；".join(
            f"第 {e.line_no} 行 {e.ip} {' '.join(e.hostnames[:2])}" for e in suspicious[:3]
        )
        if len(suspicious) > 3:
            sample += f"；…共 {len(suspicious)} 行"
        return ChangePreview(
            target=f"HOSTS 文件（{pw.HOSTS_PATH}）",
            before=f"{len(analysis.entries)} 条有效映射，其中 {len(suspicious)} 条可疑：{sample}",
            after=f"删除这 {len(suspicious)} 行，剩余 "
                  f"{len(analysis.entries) - len(suspicious)} 条映射与全部注释原样保留",
            note="仅删除可疑行号，注释、空行、行尾格式、BOM 均按字节保留；"
                 "原文件整份备份，可一键还原",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        # 这是本动作唯一且不可省略的备份：用户手工写的映射没有第二个副本。
        store.capture_file(session, pw.HOSTS_PATH, key="hosts", label="HOSTS 文件原文")
        return ["hosts"]

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        text = _read_hosts()
        analysis = _parse(text)

        if not analysis.suspicious:
            result.state = ActionState.SKIPPED
            result.message = "未发现需要清理的记录"
            result.finished_at = pw.now()
            return result

        drop = {entry.line_no for entry in analysis.suspicious}

        # 安全防线：解析异常会让可疑行"看起来很多"，此时整份文件的删除是灾难性的。
        # 用"要删的行数超过有效映射总数"作为解析错乱的信号，直接拒绝。
        if len(drop) > len(analysis.entries):
            raise RuntimeError(
                f"安全检查未通过：解析出 {len(drop)} 行需删除，"
                f"但文件只有 {len(analysis.entries)} 条有效映射（总行数 {analysis.total_lines}）。"
                f"这通常说明 HOSTS 格式异常或解析出错，为避免误删整份文件已中止。"
            )

        lines = _split_keepends(text)
        if lines and len(lines) != analysis.total_lines:
            # splitlines 与 splitlines(keepends=True) 应当长度一致；不一致说明
            # 文本里有异常控制字符，此时按行号删除有错位风险，宁可不动
            raise RuntimeError(
                f"HOSTS 行切分结果不一致（{len(lines)} vs {analysis.total_lines}），"
                f"文件可能包含非常规控制字符，为避免删错行已中止"
            )

        kept = [line for index, line in enumerate(lines, start=1) if index not in drop]
        new_text = "".join(kept)

        # 最后一道闸：原文件非空、清理后却变成空文件，说明行号映射或切分出了问题。
        # 空 hosts 虽然不是致命故障，但让用户看到"文件被清空"是极差的体验，
        # 且几乎一定是本模块的 bug，宁可中止并保留现场。
        if text.strip() and not new_text.strip():
            raise RuntimeError(
                "安全检查未通过：清理后文件将不剩任何内容，疑似行号映射错误，已中止（原文件未修改）"
            )

        # 二次确认：删完之后必须仍然"没有可疑行"，否则说明行号映射错了
        recheck = _parse(new_text)
        if recheck.suspicious:
            raise RuntimeError(
                f"清理后仍解析出 {len(recheck.suspicious)} 条可疑记录，"
                f"行号映射可能不一致，已中止写入（原文件未被修改）"
            )

        pw.atomic_write(pw.HOSTS_PATH, new_text)
        result.finished_at = pw.now()
        result.message = f"已删除 {len(drop)} 条异常记录，其余内容原样保留"
        for entry in analysis.suspicious[:10]:
            result.detail.append(f"删除第 {entry.line_no} 行：{entry.raw.strip()}｜{entry.reason}")
        if len(analysis.suspicious) > 10:
            result.detail.append(f"…另有 {len(analysis.suspicious) - 10} 条同类记录")
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        import os

        if not os.path.isfile(pw.HOSTS_PATH):
            return False, f"HOSTS 文件不存在：{pw.HOSTS_PATH}"
        analysis = _parse(_read_hosts())
        if analysis.suspicious:
            return False, f"仍存在 {len(analysis.suspicious)} 条可疑记录"
        if analysis.byte_size <= 0:
            return False, "HOSTS 变成空文件"
        # 行数偏少只作为提示，不作为失败依据：用户完全可能只有两三行自定义映射，
        # 把它判成失败会让"清理成功"被误报为失败。真正的空文件已由上面两条拦住。
        note = ""
        if analysis.total_lines < 3:
            note = f"（文件行数较少：{analysis.total_lines} 行，请自行核对是否完整）"
        return True, f"已确认可疑记录为 0；剩余 {len(analysis.entries)} 条有效映射{note}"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="hosts",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# hosts.restore_default
# --------------------------------------------------------------------------- #
@register_action("hosts.restore_default")
class HostsRestoreDefaultAction(BaseAction):
    """用系统默认模板整份覆盖。

    高风险：用户自定义的内网映射会全部消失。因此默认不勾选，preview 必须把
    "会丢什么"说清楚，且 note 里要说明只能从备份页回滚（撤销栈里没有它）。
    """

    action_id = "hosts.restore_default"

    def preview(self, ctx: Any) -> ChangePreview:
        analysis = _parse(_read_hosts())
        detail = "、".join(
            f"{e.ip} {' '.join(e.hostnames[:2])}" for e in analysis.entries[:5]
        )
        if len(analysis.entries) > 5:
            detail += f" 等 {len(analysis.entries)} 条"
        return ChangePreview(
            target=f"HOSTS 文件（{pw.HOSTS_PATH}）",
            before=f"当前 {len(analysis.entries)} 条有效映射"
                   + (f"：{detail}" if detail else ""),
            after="仅系统默认模板（全部为注释，无任何映射），用户自定义记录全部丢失",
            note="此操作不可通过撤销恢复，但可在备份页回滚。"
                 "执行前会把当前文件整份备份。",
        )

    def backup(self, store: Any, session: Any, ctx: Any) -> list[str]:
        store.capture_file(session, pw.HOSTS_PATH, key="hosts", label="HOSTS 文件原文")
        return ["hosts"]

    def apply(self, ctx: Any) -> ActionResult:
        result = ActionResult(action_id=self.action_id, state=ActionState.APPLIED,
                              started_at=pw.now())
        before = _parse(_read_hosts())
        pw.atomic_write(pw.HOSTS_PATH, DEFAULT_HOSTS_TEXT)
        result.finished_at = pw.now()
        result.message = f"HOSTS 已恢复为系统默认模板（清除 {len(before.entries)} 条映射）"
        result.detail.append("已写入 Windows 默认模板（CRLF 行尾，UTF-8 无 BOM）")
        result.detail.append("用户自定义映射已清除；如需找回请在备份页回滚本次会话")
        return result

    def verify(self, ctx: Any) -> tuple[bool, str]:
        analysis = _parse(_read_hosts())
        if analysis.entries:
            return False, f"模板中仍解析出 {len(analysis.entries)} 条有效映射，写入可能未生效"
        if analysis.total_lines <= 0:
            return False, "HOSTS 为空文件，默认模板未写入"
        return True, f"已确认为系统默认模板（{analysis.total_lines} 行，0 条映射）"

    def rollback(self, store: Any, session: Any, ctx: Any) -> ActionResult:
        from .rollback import rollback_items_of_kind

        return rollback_items_of_kind(store, session, ctx, kind="hosts",
                                      action_id=self.action_id)


# --------------------------------------------------------------------------- #
# 外部调用入口（UI 直接使用）
# --------------------------------------------------------------------------- #
def save_hosts_text(store: Any, new_text: str):
    """备份现有 hosts → 用 new_text 覆盖写入 → 返回 (会话, 结果)。

    UI 的"手工编辑 hosts"功能走这里，是为了保证它和自动修复共用同一条
    备份链路：任何写入之前，原文一定已经被整份快照保存。

    写入前必须能正常解析 new_text：解析出 0 行说明内容为空或全是噪声，
    此时覆盖会毁掉用户的 hosts，所以直接拒绝。
    """
    from ..models import ActionState as _State

    if not isinstance(new_text, str):
        raise ValueError(f"new_text 必须是字符串，收到 {type(new_text).__name__}")
    analysis = _parse(new_text)
    if analysis.total_lines <= 0:
        raise ValueError(
            "拒绝写入：新内容为空文件。覆盖后 HOSTS 将不含任何行，"
            "这通常意味着输入被截断或编码错误"
        )
    if analysis.byte_size <= 0:
        raise ValueError("拒绝写入：新内容字节数为 0")
    # 只有空白/换行的内容能通过上面的行数检查（有行、但没有任何映射或注释），
    # 覆盖上去等于把用户的 hosts 变成一堆空行。这里再拦一次。
    if not new_text.strip():
        raise ValueError("拒绝写入：新内容只包含空白字符，没有可保留的内容")

    session = store.begin(kind="手工编辑 HOSTS", note="写入前自动备份 HOSTS 原文")
    try:
        store.capture_file(session, pw.HOSTS_PATH, key="hosts", label="HOSTS 文件原文")
    except Exception:
        # 备份失败就绝不能写：会话目录保留，便于用户看到"备份到哪一步失败"
        raise
    store.save(session)

    before = _parse(_read_hosts())
    pw.atomic_write(pw.HOSTS_PATH, new_text)
    result = ActionResult(
        action_id="hosts.save_text",
        state=_State.APPLIED,
        message=f"HOSTS 已写入（{analysis.total_lines} 行，{len(analysis.entries)} 条映射）",
        started_at=pw.now(),
        finished_at=pw.now(),
    )
    result.detail.append(f"写入前有 {len(before.entries)} 条有效映射")
    if analysis.suspicious:
        result.detail.append(f"注意：新内容里仍有 {len(analysis.suspicious)} 条可疑记录")
    return session, result


__all__ = [
    "DEFAULT_HOSTS_TEXT",
    "HostsCleanBadLinesAction",
    "HostsRestoreDefaultAction",
    "save_hosts_text",
]
