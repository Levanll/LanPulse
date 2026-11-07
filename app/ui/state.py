"""应用状态中枢。

为什么需要这一层：仪表盘、诊断详情、修复页、报告导出都要读同一份体检结果，
而体检本身是异步的。把所有可变状态收敛到 AppState，用 Qt 信号广播变化，
避免页面之间互相引用（那会导致循环 import 与刷新时序 bug）。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from core.backup import BackupStore, BackupSession
from core.context import DiagnosticContext
from core.models import CheckResult, DiagnosticReport
from core.registry import load_checks, run_all
from core.scenarios import checks_for


class AppState(QObject):
    """全局单例状态。所有写操作必须在 UI 线程完成；后台只返回结果。"""

    report_changed = Signal(object)     # DiagnosticReport
    progress = Signal(int, int, str)    # done, total, label
    status = Signal(str)                # 状态栏短消息
    busy_changed = Signal(bool)
    backups_changed = Signal()
    repair_done = Signal(object)        # RepairReport

    def __init__(self, parent: QObject | None = None, settings=None) -> None:
        super().__init__(parent)
        self.report: DiagnosticReport | None = None
        #: 当前场景 id（决定跑哪些检测项）
        self.scenario_id: str = "full"
        #: 最近一次根因分析结果
        self.analysis = None
        self.context: DiagnosticContext | None = None
        self.store = BackupStore()
        self._last_backup: BackupSession | None = None
        #: 设置对象。AppState 只读它，写操作统一在设置页完成。
        self.settings = settings

    # ------------------------------------------------------------------ #
    # 体检
    # ------------------------------------------------------------------ #
    def create_context(self) -> DiagnosticContext:
        """创建检测上下文，把用户设置（区域 / 超时 / 是否允许联网探测）带进去。

        这一步决定了「设置改了以后检测行为真的跟着变」，而不是只存了个偏好值。
        """
        if self.settings is not None:
            ctx = DiagnosticContext(
                region_override=str(self.settings.get("region", "auto")),
                allow_probe=self.settings.get_bool("allow_network_probe"),
                timeout_scale=self.settings.get_float("timeout_scale"),
            )
        else:
            ctx = DiagnosticContext()
        self.context = ctx
        return ctx

    def run_diagnosis(self, progress: Any = None,
                      scenario_id: str = "full") -> DiagnosticReport:
        """在后台线程执行检测。progress 是 worker._Runnable.report。

        scenario_id 决定跑哪些检测项（见 core/scenarios.py）。
        场景只影响"选哪些项"，不影响"每项怎么判"——同一个检测项
        在任何场景下产出的数据完全一致，避免"换个场景结论就变"的困惑。
        """
        ctx = self.create_context()
        wanted = set(checks_for(scenario_id))
        all_checks = load_checks()
        # 保持检测项的原始注册顺序（UI 表格顺序稳定），只做过滤
        checks = [c for c in all_checks if c.check_id in wanted]
        if not checks:
            checks = all_checks
        total = len(checks)

        def _cb(done: int, all_: int, check: Any) -> None:
            # check.title 存的是 i18n key（如 check.adapter.title），
            # 直接显示会在状态栏露出原始 key。
            from core.i18n import t

            raw = getattr(check, "title", "") if check is not None else ""
            label = t(raw) if raw else t("status.summarizing")
            if progress is not None:
                progress(done, all_,
                         t("status.checking", name=label) if done < all_
                         else t("status.summarizing"))

        results = run_all(ctx, checks, progress=_cb)
        report = DiagnosticReport(
            host=ctx.hostname, os_name=ctx.os_name, elevated=ctx.elevated,
            results=results,
        )
        report.finished_at = __import__("time").time()
        self.report = report
        # 后台线程里就做完根因分析：UI 线程拿到结果即可渲染，
        # 不必再等一次计算（规则是纯函数，很快，但保持职责集中）。
        from core.rootcause import analyze

        self.analysis = analyze(report.results)
        return report

    def set_report(self, report: DiagnosticReport) -> None:
        """保存报告并立即做根因分析（供仪表盘与报告页消费）。"""
        from core.rootcause import analyze

        self.report = report
        self.analysis = analyze(report.results)
        self.report_changed.emit(report)

    # ------------------------------------------------------------------ #
    # 备份
    # ------------------------------------------------------------------ #
    def refresh_backups(self) -> list[BackupSession]:
        sessions = self.store.list_sessions()
        self.backups_changed.emit()
        return sessions

    def set_last_backup(self, session: BackupSession | None) -> None:
        self._last_backup = session
        self.backups_changed.emit()

    @property
    def last_backup(self) -> BackupSession | None:
        return self._last_backup

    # ------------------------------------------------------------------ #
    # 派生
    # ------------------------------------------------------------------ #
    def problems(self) -> list[CheckResult]:
        return self.report.problems() if self.report else []

    def suggested_actions(self) -> list[str]:
        """按检测结果聚合建议动作，去重并保持出现顺序。"""
        seen: list[str] = []
        if not self.report:
            return seen
        for r in self.report.problems():
            for aid in r.action_ids:
                if aid not in seen:
                    seen.append(aid)
        return seen


__all__ = ["AppState"]
