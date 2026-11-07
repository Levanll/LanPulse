r"""独立回滚工具 —— 因测试脚本崩溃而需要手动收尾时使用。

用法：
    python tools/rollback_session.py                       # 列出所有会话
    python tools/rollback_session.py <session_id>          # 回滚指定会话
    python tools/rollback_session.py <session_id> --dry     # 只看会做什么

设计上刻意保持极简：它直接调 `RepairEngine.rollback()`，
与 UI 里「备份与回滚」页走的是同一条代码路径，因此这次执行
本身就是对真实回滚通道的验证。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import platform_win as pw  # noqa: E402
from core.backup import BackupStore  # noqa: E402
from core.context import DiagnosticContext  # noqa: E402
from core.i18n import set_language  # noqa: E402
from core.repair import engine as E  # noqa: E402

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()


def out(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc, errors="replace"))


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    set_language("zh")

    store = BackupStore()
    sessions = store.list_sessions()

    if not argv:
        out(f"备份根目录：{store.root}")
        out(f"会话数：{len(sessions)}\n")
        for s in sessions:
            restored = "（已还原）" if s.restored_at else ""
            out(f"  {s.session_id}  {s.kind}{restored}")
            out(f"    项数={len(s.items)}  说明={s.note[:60]}")
            for it in s.items:
                out(f"      · [{it.kind}] {it.label}")
            out("")
        out("用法：python tools/rollback_session.py <session_id>")
        return 0

    sid = argv[0]
    dry = "--dry" in argv

    try:
        session = store.load(sid)
    except FileNotFoundError:
        out(f"[错误] 会话不存在：{sid}")
        return 1

    out(f"会话：{session.session_id}")
    out(f"类型：{session.kind}")
    out(f"创建：{session.session_path if hasattr(session, 'session_path') else session.path}")
    out(f"备份项（{len(session.items)}）：")
    for it in session.items:
        out(f"  · [{it.kind}] {it.label}")
        out(f"    payload = {it.payload}")

    if dry:
        out("\n--dry 模式，未执行回滚。")
        return 0

    if not pw.is_elevated():
        out("\n[警告] 当前非管理员。注册表/DNS/防火墙类回滚会被跳过；")
        out("       建议以管理员身份运行以完整还原。")

    ctx = DiagnosticContext()
    eng = E.RepairEngine(store=store)
    rb = eng.rollback(sid, ctx)

    out(f"\n回滚结果：成功 {rb.ok_count} / 失败 {rb.fail_count} / "
        f"跳过 {getattr(rb, 'skipped_count', '?')}")
    for r in rb.results:
        out(f"  · {r.action_id}: {r.state.value}")
        out(f"    {r.message[:100]}")
        if r.error:
            out(f"    错误：{r.error[:200]}")

    return 0 if rb.fail_count == 0 else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
