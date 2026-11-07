"""备份与回滚中间层 —— 全软件唯一允许修改系统的入口。

铁律（违反即为缺陷）：
  1. 任何写操作前必须先 BackupStore.capture(...)，capture 失败 => 动作不得执行；
  2. 备份内容必须是“恢复所需的全部状态”，而不是差异；
  3. 回滚只依赖备份目录，不依赖当时的进程内存；
  4. 备份目录可在软件外直接打开、阅读、手工还原（.reg / .txt / 原始 hosts）。

目录结构（%LOCALAPPDATA%\\LanPulse\\backups\\<ts>_<sid>\\）：
    manifest.json          会话索引（人可读）
    files/hosts.<key>.txt  原始文件快照
    reg/<key>.reg          reg export 导出
    state/<key>.json       结构化状态快照（DNS/MTU/NetBIOS 等）
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from . import platform_win as pw
from .models import BackupRecord

BACKUP_ROOT_NAME = "backups"
MANIFEST_NAME = "manifest.json"

# 文件名中不允许出现的字符。Windows 上最危险的是 ':'——它会被 NTFS 解释为
# 交替数据流分隔符（"reg:tcpip.reg" 实际指向文件 "reg" 的 ADS 流 "tcpip.reg"），
# 结果是目录里出现一个 0 字节的 "reg"，真实备份内容藏在不可见的流里，
# os.path.isfile 仍返回 True、getsize 也正确，但 reg.exe / 资源管理器都读不到。
# 这是会让回滚在"看起来备份成功"的情况下彻底失效的隐蔽缺陷，必须在此拦死。
_UNSAFE_CHARS = ':\\/*?"<>|'
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_name(key: str, *, fallback: str = "item") -> str:
    """把任意稳定 key 映射为可安全落盘的文件名主干。

    只做字符替换，不做哈希——备份目录需要人能直接读懂、手工还原。
    替换后为空、或命中 Windows 设备名时，追加 fallback 前缀。
    """
    cleaned = "".join("_" if (c in _UNSAFE_CHARS or ord(c) < 32) else c for c in key)
    cleaned = cleaned.strip(" .")
    if not cleaned:
        cleaned = fallback
    if cleaned.upper().split(".")[0] in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #
@dataclass
class BackupItem:
    """一个可恢复状态单元。"""

    key: str                 # 稳定唯一键，如 dns:{guid}、hosts、tcp:autotuning
    kind: str                # dns / hosts / registry / mtu / netbios / firewall / tcp / proxy
    label: str               # 人类可读，如 “以太网 的 DNS 配置”
    payload: dict[str, Any]  # 结构化状态（可直接 JSON 序列化）
    file_name: str = ""      # 关联快照文件名（files/ 或 reg/ 下的相对路径）

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "label": self.label,
            "payload": self.payload,
            "file_name": self.file_name,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BackupItem":
        return cls(
            key=d["key"],
            kind=d["kind"],
            label=d.get("label", d["key"]),
            payload=d.get("payload") or {},
            file_name=d.get("file_name", ""),
        )


@dataclass
class BackupSession:
    session_id: str
    created_at: float
    kind: str
    path: str
    host: str = ""
    elevated: bool = False
    note: str = ""
    items: list[BackupItem] = field(default_factory=list)
    restored_at: float | None = None

    @property
    def manifest_path(self) -> str:
        return os.path.join(self.path, MANIFEST_NAME)

    def to_record(self) -> BackupRecord:
        return BackupRecord(
            session_id=self.session_id,
            created_at=self.created_at,
            kind=self.kind,
            summary=self.note or "、".join(sorted({i.label for i in self.items}))[:120],
            action_ids=sorted({i.kind for i in self.items}),
            path=self.path,
            restored_at=self.restored_at,
        )


# --------------------------------------------------------------------------- #
# 存储
# --------------------------------------------------------------------------- #
class BackupStore:
    def __init__(self, root: str | None = None) -> None:
        self.root = root or os.path.join(pw.app_data_dir(), BACKUP_ROOT_NAME)
        os.makedirs(self.root, exist_ok=True)

    # ---- 创建会话 ----
    def begin(self, *, kind: str, note: str = "") -> BackupSession:
        ts = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        sid = f"{ts}_{uuid.uuid4().hex[:6]}"
        path = os.path.join(self.root, sid)
        for sub in ("files", "reg", "state"):
            os.makedirs(os.path.join(path, sub), exist_ok=True)
        session = BackupSession(
            session_id=sid,
            created_at=time.time(),
            kind=kind,
            path=path,
            host=pw.computer_name(),
            elevated=pw.is_elevated(),
            note=note,
        )
        return session

    def save(self, session: BackupSession) -> None:
        doc = {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "created_at_text": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(session.created_at)),
            "kind": session.kind,
            "host": session.host,
            "elevated": session.elevated,
            "note": session.note,
            "restored_at": session.restored_at,
            "items": [i.to_dict() for i in session.items],
        }
        pw.atomic_write(session.manifest_path, json.dumps(doc, ensure_ascii=False, indent=2))

    # ---- 采集各类状态 ----
    def capture_file(self, session: BackupSession, path: str, *, key: str, label: str,
                     kind: str = "hosts") -> BackupItem:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"待备份文件不存在: {path}")
        rel = os.path.join("files", f"{safe_name(key)}.bak")
        dest = os.path.join(session.path, rel)
        shutil.copy2(path, dest)
        # 记录哈希，回滚前可用于完整性校验，也便于用户核对
        data = open(dest, "rb").read()
        item = BackupItem(
            key=key,
            kind=kind,
            label=label,
            payload={
                "source_path": path,
                "size": len(data),
                "sha256": _sha256(data),
            },
            file_name=rel,
        )
        session.items.append(item)
        self.save(session)
        return item

    def capture_registry(self, session: BackupSession, hive_path: str, *, key: str,
                         label: str) -> BackupItem:
        """用 reg export 生成 .reg，回滚时 reg import 即可，用户也能手工双击还原。"""
        rel = os.path.join("reg", f"{safe_name(key)}.reg")
        dest = os.path.join(session.path, rel)
        rc, out = pw.run_cmd(["reg", "export", hive_path, dest, "/y"], timeout=25)
        if rc != 0 or not os.path.isfile(dest):
            raise RuntimeError(f"注册表备份失败({hive_path}): {out}")
        item = BackupItem(
            key=key,
            kind="registry",
            label=label,
            payload={"hive_path": hive_path},
            file_name=rel,
        )
        session.items.append(item)
        self.save(session)
        return item

    def capture_state(self, session: BackupSession, *, key: str, kind: str, label: str,
                      payload: dict[str, Any]) -> BackupItem:
        """结构化状态快照（DNS 服务器列表、MTU、NetBIOS 选项等）。"""
        rel = os.path.join("state", f"{safe_name(key)}.json")
        dest = os.path.join(session.path, rel)
        pw.atomic_write(dest, json.dumps(payload, ensure_ascii=False, indent=2))
        item = BackupItem(key=key, kind=kind, label=label, payload=payload, file_name=rel)
        session.items.append(item)
        self.save(session)
        return item

    # ---- 读取 ----
    def list_sessions(self) -> list[BackupSession]:
        out: list[BackupSession] = []
        if not os.path.isdir(self.root):
            return out
        for name in os.listdir(self.root):
            mp = os.path.join(self.root, name, MANIFEST_NAME)
            if not os.path.isfile(mp):
                continue
            try:
                out.append(self._load(mp))
            except (OSError, KeyError, ValueError, json.JSONDecodeError):
                # 损坏的备份目录不应让整个列表失败，但它必须从列表里“消失”并留痕
                continue
        out.sort(key=lambda s: s.created_at, reverse=True)
        return out

    def load(self, session_id: str) -> BackupSession:
        mp = os.path.join(self.root, session_id, MANIFEST_NAME)
        if not os.path.isfile(mp):
            raise FileNotFoundError(f"备份会话不存在: {session_id}")
        return self._load(mp)

    def _load(self, manifest_path: str) -> BackupSession:
        with open(manifest_path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        return BackupSession(
            session_id=doc["session_id"],
            created_at=float(doc["created_at"]),
            kind=doc.get("kind", "unknown"),
            path=os.path.dirname(manifest_path),
            host=doc.get("host", ""),
            elevated=bool(doc.get("elevated")),
            note=doc.get("note", ""),
            items=[BackupItem.from_dict(i) for i in doc.get("items") or []],
            restored_at=doc.get("restored_at"),
        )

    def mark_restored(self, session: BackupSession) -> None:
        session.restored_at = time.time()
        self.save(session)

    def prune(self, keep: int = 30) -> list[str]:
        """只清理最旧的整份会话，绝不删单个文件。返回被清理的会话 id。"""
        sessions = self.list_sessions()
        if len(sessions) <= keep:
            return []
        removed: list[str] = []
        for s in sessions[keep:]:
            shutil.rmtree(s.path, ignore_errors=False)
            removed.append(s.session_id)
        return removed


def _sha256(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


__all__ = ["BackupStore", "BackupSession", "BackupItem", "BACKUP_ROOT_NAME", "safe_name"]
