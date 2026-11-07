"""日志与操作审计流水。

两类日志严格分开：
  * app.log —— 程序运行日志（异常、耗时），仅本机，用于排障；
  * audit.jsonl —— **操作审计**，每一条系统修改/回滚都落一行 JSON，包含时间、
    操作 id、目标、结果、备份会话 id。它回答“这软件到底对我电脑做了什么”。

同时通过 Qt 信号把日志推给 UI，避免 UI 直接读文件、也避免多线程写竞争。
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from logging.handlers import RotatingFileHandler
from typing import Any

from core import platform_win as pw

_AUDIT_LOCK = threading.Lock()


def log_dir() -> str:
    path = os.path.join(pw.app_data_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


def audit_path() -> str:
    return os.path.join(log_dir(), "audit.jsonl")


def setup_logging(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger("netpulse")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-7s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    fh = RotatingFileHandler(
        os.path.join(log_dir(), "app.log"), maxBytes=2 * 1024 * 1024,
        backupCount=3, encoding="utf-8",
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    if verbose:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(sh)
    return logger


def write_audit(
    *,
    event: str,
    action_id: str = "",
    target: str = "",
    detail: str = "",
    ok: bool | None = None,
    session_id: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """追加一条审计记录并返回该记录，便于调用方同步展示。"""
    record = {
        "ts": time.time(),
        "ts_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "event": event,
        "action_id": action_id,
        "target": target,
        "detail": detail,
        "ok": ok,
        "session_id": session_id,
        "host": pw.computer_name(),
        "elevated": pw.is_elevated(),
    }
    if extra:
        record["extra"] = extra
    line = json.dumps(record, ensure_ascii=False)
    with _AUDIT_LOCK:
        with open(audit_path(), "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return record


def read_audit(limit: int = 200) -> list[dict[str, Any]]:
    """读取最近 N 条审计记录（新的在前）。文件不存在时返回空列表。"""
    path = audit_path()
    if not os.path.isfile(path):
        return []
    out: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # 单行损坏（例如断电截断）不影响其余记录
                continue
    out.reverse()
    return out[:limit]


__all__ = ["setup_logging", "write_audit", "read_audit", "audit_path", "log_dir"]
