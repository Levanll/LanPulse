"""LanPulse 共享数据模型。

本模块是全部子系统（检测引擎 / 修复引擎 / UI / 报告）的唯一契约来源。
任何改动必须保持向后兼容：字段只增不改，序列化保持 dict 结构。
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# --------------------------------------------------------------------------- #
# 基础枚举
# --------------------------------------------------------------------------- #
class Severity(str, Enum):
    OK = "ok"
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"
    SKIP = "skip"

    @property
    def rank(self) -> int:
        return {"skip": 0, "ok": 1, "info": 2, "warn": 3, "critical": 4}[self.value]

    @property
    def label(self) -> str:
        return {
            "ok": "正常",
            "info": "提示",
            "warn": "异常",
            "critical": "严重",
            "skip": "跳过",
        }[self.value]

    @classmethod
    def worst(cls, items: list["Severity"]) -> "Severity":
        if not items:
            return cls.SKIP
        return max(items, key=lambda s: s.rank)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def label(self) -> str:
        return {"low": "低风险", "medium": "中风险", "high": "高风险"}[self.value]


class ActionState(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    ROLLBACK_FAILED = "rollback_failed"


# --------------------------------------------------------------------------- #
# 检测结果
# --------------------------------------------------------------------------- #
@dataclass
class Metric:
    """单项可量化指标，用于 UI 表格与报告。

    国际化约定：`name` 与 `note` 存的是 **i18n key**（如 `metric.link_speed`），
    不是最终文案。渲染层用 `tr_or_raw()` 翻译——不是 key 的原样显示，
    这样动态值（网卡名、IP、域名）也能混用同一字段。
    """

    name: str
    value: str
    note: str = ""
    ok: bool | None = None  # None = 中性

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckResult:
    """一个检测单元的完整输出。检测单元必须可独立运行、可独立展示。

    **国际化设计（重要）**：`title` / `category` / `summary` / `detail` / `advice`
    存的是 i18n key 或已本地化文本，取决于产出方式；而 `*_key` 与 `*_args`
    记录"可重新翻译"的来源。原因：体检在后台线程执行，若当场翻译，
    用户切换语言后旧结果会停留在旧语言——这是真实发生过的缺陷。
    渲染层优先用 `*_key` + `*_args` 重新翻译，没有 key 时才用已存的文本。
    """

    check_id: str
    title: str
    category: str
    severity: Severity = Severity.OK
    summary: str = ""
    detail: str = ""  # 人类可读多行说明（可含 Markdown 子集）
    metrics: list[Metric] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)  # 原始证据，供报告与排障
    advice: list[str] = field(default_factory=list)
    action_ids: list[str] = field(default_factory=list)  # 建议关联的修复动作 id
    duration_ms: int = 0
    error: str = ""
    timestamp: float = field(default_factory=time.time)

    #: summary 的 i18n key 与格式化参数。为空表示 summary 已是最终文本。
    summary_key: str = ""
    summary_args: dict[str, Any] = field(default_factory=dict)
    #: detail / advice 的 key 列表（与文本列表一一对应，可为空）
    detail_key: str = ""
    advice_keys: list[str] = field(default_factory=list)
    #: 该结果产出时的语言。渲染层据此判断是否需要重新翻译。
    lang: str = ""

    def localized_summary(self, translate) -> str:
        """返回当前语言下的 summary。

        `translate` 是 `(key, args) -> str` 的回调（由渲染层注入，
        core 不直接依赖 i18n 的具体实现，避免循环 import）。

        优先用 summary_key 现翻译；没有 key 时回退到已存文本——
        后者在切换语言后不会变，这是已知的降级路径，仅用于动态拼接的文案。
        """
        if self.summary_key:
            return translate(self.summary_key, self.summary_args)
        return self.summary

    @property
    def failed(self) -> bool:
        return bool(self.error)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CheckResult":
        d = dict(d)
        d["severity"] = Severity(d.get("severity", "ok"))
        d["metrics"] = [Metric(**m) for m in d.get("metrics") or []]
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class DiagnosticReport:
    """一次完整体检的结果集合。"""

    host: str = ""
    os_name: str = ""
    elevated: bool = False
    started_at: float = field(default_factory=time.time)
    finished_at: float = 0.0
    results: list[CheckResult] = field(default_factory=list)
    report_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    # ---- 派生指标 ----
    @property
    def overall(self) -> Severity:
        return Severity.worst([r.severity for r in self.results if not r.failed])

    @property
    def score(self) -> int:
        """0-100 的健康分。仅用于 UI 观感，不参与任何修复决策。"""
        graded = [r for r in self.results if r.severity is not Severity.SKIP and not r.failed]
        if not graded:
            return 0
        weights = {Severity.OK: 100, Severity.INFO: 88, Severity.WARN: 55, Severity.CRITICAL: 12}
        return round(sum(weights[r.severity] for r in graded) / len(graded))

    def by_severity(self) -> dict[str, int]:
        out = {s.value: 0 for s in Severity}
        for r in self.results:
            out[r.severity.value] += 1
        return out

    def problems(self) -> list[CheckResult]:
        return [r for r in self.results if r.severity in (Severity.WARN, Severity.CRITICAL)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "host": self.host,
            "os_name": self.os_name,
            "elevated": self.elevated,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "overall": self.overall.value,
            "score": self.score,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# --------------------------------------------------------------------------- #
# 修复动作
# --------------------------------------------------------------------------- #
@dataclass
class ChangePreview:
    """修复前的“将要发生什么”，必须先展示给用户再执行。"""

    target: str  # 作用对象，如 "以太网 / DNS 服务器"
    before: str
    after: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ActionResult:
    """单个动作的执行结果。"""

    action_id: str
    state: ActionState = ActionState.PENDING
    message: str = ""
    error: str = ""
    started_at: float = 0.0
    finished_at: float = 0.0
    verified: bool | None = None
    detail: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d


@dataclass
class BackupRecord:
    """备份会话索引项，UI 的“备份与回滚”页直接消费。"""

    session_id: str
    created_at: float
    kind: str  # 手工备份 / 修复前自动备份
    summary: str
    action_ids: list[str] = field(default_factory=list)
    path: str = ""
    restored_at: float | None = None
    restorable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "Severity",
    "RiskLevel",
    "ActionState",
    "Metric",
    "CheckResult",
    "DiagnosticReport",
    "ChangePreview",
    "ActionResult",
    "BackupRecord",
]
