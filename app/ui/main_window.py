"""主窗口：侧栏导航 + 页面容器 + 状态栏 + 全局动作编排。

编排原则：页面只发信号，主窗口负责跨模块调度（体检、修复、回滚、导出），
并且**所有改系统的入口都收敛到 _do_execute / _do_rollback 两个方法**，
便于审计与统一加保护（例如未提权时拦截高危动作）。
"""
from __future__ import annotations

import logging
import os
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from core import platform_win as pw
from core import i18n
from core.context import DiagnosticContext
from core.branding import NAME, NAME_ZH, VERSION
from core.i18n import t
from core.scenarios import checks_for, get_scenario
from core.repair import engine as repair_engine
from app.logging_setup import write_audit
from app.sysutil import WINDOW_TITLE
from app.ui.pages.backup import BackupPage
from app.ui.pages.dashboard import DashboardPage
from app.ui.pages.diagnose import DiagnosePage
from app.ui.pages.dns import DnsPage
from app.ui.pages.hosts import HostsPage
from app.ui.pages.repair import RepairPage
from app.ui.pages.report import ReportPage
from app.ui.pages.scenario import ScenarioPage
from core.rootcause import analyze, grade, health_score
from app.ui.pages.settings import SettingsPage
from app.ui.theme import QSS, T
from app.ui.widgets import Toast
from app.ui.worker import TaskRunner

log = logging.getLogger("netpulse.window")


class MainWindow(QMainWindow):
    """页码常量。顺序必须与 _nav_specs / stack.addWidget 严格一致。"""
    PAGE_SCENARIO = 0
    PAGE_OVERVIEW = 1
    PAGE_DNS = 2
    PAGE_HOSTS = 3
    PAGE_REPAIR = 4
    PAGE_BACKUP = 5
    PAGE_DIAGNOSE = 6
    PAGE_REPORT = 7
    SETTINGS_INDEX = 8

    def __init__(self, state, *, elevated: bool = False, settings=None) -> None:
        super().__init__()
        self.state = state
        self.elevated = elevated
        if settings is None:
            from core.settings import load_settings

            settings = load_settings()
        self.settings = settings
        # state 与设置页共享同一个 Settings 实例，避免两处各存一份导致
        # 「界面上改了、检测仍用旧值」这类难以察觉的不一致。
        if getattr(state, 'settings', None) is None:
            state.settings = settings
        self.setWindowTitle(WINDOW_TITLE)
        self.resize(1280, 820)
        self.setMinimumSize(1080, 700)

        self._runner = TaskRunner(self)
        self._runner.progress.connect(self._on_progress)
        self._runner.finished.connect(self._on_task_done)
        self._runner.failed.connect(self._on_task_failed)

        self._pending_kind = ""
        self._pending_scenario = "full"
        self._pending_servers: list | None = None

        self._build_ui()
        self.setStyleSheet(QSS)
        self._wire()
        self.retranslate()

        # 启动后自动体检一次，让用户打开即见结果（可在设置里关闭）
        if self.settings.get_bool("auto_scan_on_start"):
            QTimer.singleShot(420, self.start_scan)

    # ------------------------------------------------------------------ #
    # 构建
    # ------------------------------------------------------------------ #
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---------------- 侧栏 ----------------
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(214)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 20, 16, 16)
        side.setSpacing(7)

        brand = QLabel(NAME.upper())
        brand.setObjectName("BrandMark")
        side.addWidget(brand)
        sub = QLabel(f"{NAME_ZH} · 网络体检与一键修复")
        sub.setObjectName("BrandSub")
        side.addWidget(sub)
        side.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self._nav_buttons: list[QPushButton] = []
        # (i18n key, 图标)。文案在 retranslate() 里填充，切换语言时整体刷新。
        self._nav_specs = [
            ("◎", "nav.scenario"),
            ("◉", "nav.overview"),
            ("◈", "nav.dns"),
            ("☰", "nav.hosts"),
            ("⚙", "nav.repair"),
            ("⏱", "nav.backup"),
            ("◧", "nav.diagnose"),
            ("⬒", "nav.report"),
        ]
        for idx, (icon, key) in enumerate(self._nav_specs):
            b = QPushButton(icon)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=idx: self.switch_page(i))
            self.nav_group.addButton(b, idx)
            self._nav_buttons.append(b)
            side.addWidget(b)
        self._nav_buttons[0].setChecked(True)

        # ---- 分隔线 + 设置入口（放在导航组之外，视觉上与其他页面区分）----
        side.addSpacing(10)
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background:{T.LINE_SOFT};")
        side.addWidget(divider)
        side.addSpacing(6)

        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setObjectName("NavButton")
        self.btn_settings.setCheckable(True)
        self.btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_settings.clicked.connect(lambda: self.switch_page(self.SETTINGS_INDEX))
        self.nav_group.addButton(self.btn_settings, self.SETTINGS_INDEX)
        self._nav_buttons.append(self.btn_settings)
        side.addWidget(self.btn_settings)

        side.addStretch(1)

        # 环境状态
        self.env_badge = QLabel("")
        self.env_badge.setWordWrap(True)
        self.env_badge.setStyleSheet(
            f"color:{T.ACCENT if self.elevated else T.WARN};font-size:8.5pt;"
            f"background:rgba(255,255,255,0.03);border:1px solid {T.LINE};"
            f"border-radius:7px;padding:7px 9px;"
        )
        self.env_badge.setText(
            "已获得管理员权限" if self.elevated else "普通权限运行\n部分修复不可用"
        )
        side.addWidget(self.env_badge)

        if not self.elevated:
            self.btn_elevate = QPushButton("以管理员身份重启")
            self.btn_elevate.setObjectName("Ghost")
            self.btn_elevate.clicked.connect(self._elevate)
            side.addWidget(self.btn_elevate)

        self.btn_env = QPushButton("环境自检")
        self.btn_env.setObjectName("Ghost")
        self.btn_env.clicked.connect(self._show_env_checks)
        side.addWidget(self.btn_env)

        ver = QLabel(f"v{VERSION}")
        ver.setStyleSheet(f"color:{T.TEXT_FAINT};font-size:8pt;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(ver)

        outer.addWidget(sidebar)

        # ---------------- 主区 ----------------
        main = QWidget()
        main_lay = QVBoxLayout(main)
        main_lay.setContentsMargins(22, 18, 22, 14)
        main_lay.setSpacing(12)

        header = QHBoxLayout()
        self.page_title = QLabel("总览")
        self.page_title.setObjectName("H1")
        header.addWidget(self.page_title)
        header.addStretch(1)
        self.status_chip = QLabel("就绪")
        self.status_chip.setStyleSheet(
            f"color:{T.TEXT_DIM};font-size:9pt;border:1px solid {T.LINE};"
            f"border-radius:9px;padding:3px 11px;"
        )
        header.addWidget(self.status_chip)
        main_lay.addLayout(header)

        self.stack = QStackedWidget()
        self.scenario_page = ScenarioPage(self.state)
        self.dashboard = DashboardPage(self.state)
        self.dns_page = DnsPage(self.state)
        self.hosts_page = HostsPage(self.state)
        self.repair_page = RepairPage(self.state)
        self.backup_page = BackupPage(self.state)
        self.diagnose_page = DiagnosePage(self.state)
        self.report_page = ReportPage(self.state)
        self.settings_page = SettingsPage(self.state, self.settings)
        for w in (self.scenario_page, self.dashboard, self.dns_page, self.hosts_page,
                  self.repair_page, self.backup_page, self.diagnose_page,
                  self.report_page, self.settings_page):
            self.stack.addWidget(w)
        main_lay.addWidget(self.stack, 1)

        outer.addWidget(main, 1)
        self.toast = Toast(root)

        self.pt = QTimer(self)
        self.pt.setInterval(60)
        self.pt.timeout.connect(self._pulse_status)
        self._pulse_phase = 0.0

    # ------------------------------------------------------------------ #
    def _wire(self) -> None:
        self.dashboard.request_scan.connect(self.start_scan)
        self.dashboard.request_repair.connect(self._goto_repair)
        self.dashboard.goto_dns.connect(lambda: self.switch_page(self.PAGE_DNS))
        self.dashboard.goto_hosts.connect(lambda: self.switch_page(self.PAGE_HOSTS))
        self.dashboard.goto_backup.connect(lambda: self.switch_page(self.PAGE_BACKUP))
        self.dashboard.goto_report.connect(lambda: self.switch_page(self.PAGE_REPORT))

        self.dns_page.request_apply_plan.connect(self._apply_dns_plan)
        self.hosts_page.request_clean.connect(lambda: self._execute_ids(["hosts.clean_bad_lines"]))
        self.hosts_page.request_restore.connect(lambda: self._execute_ids(["hosts.restore_default"]))
        self.hosts_page.request_save_text.connect(self._save_hosts_text)

        self.repair_page.request_execute.connect(self._do_execute)

        self.backup_page.request_rollback.connect(self._do_rollback)
        self.backup_page.request_create.connect(self._manual_backup)

        self.report_page.request_export.connect(self._export_report)

        self.settings_page.language_changed.connect(self._on_language_changed)
        self.settings_page.region_changed.connect(self._on_region_changed)
        self.settings_page.settings_changed.connect(self._on_setting_changed)
        self.settings_page.request_open_data_dir.connect(self._open_data_dir)

        self.scenario_page.scenario_chosen.connect(self._on_scenario_chosen)

        self.state.report_changed.connect(self._on_report_set)

    # ------------------------------------------------------------------ #
    # 导航
    # ------------------------------------------------------------------ #
    #: 页面标题的 i18n key，与 stack 索引一一对应
    TITLE_KEYS = [
        "nav.scenario", "nav.overview", "nav.dns", "nav.hosts", "nav.repair",
        "nav.backup", "nav.diagnose", "nav.report", "nav.settings",
    ]

    def switch_page(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        if 0 <= idx < len(self.TITLE_KEYS):
            self.page_title.setText(t(self.TITLE_KEYS[idx]))
        if idx < len(self._nav_buttons):
            self._nav_buttons[idx].setChecked(True)
        if idx == self.PAGE_BACKUP:
            self.backup_page.refresh()
        if idx == self.PAGE_REPORT:
            self.report_page.refresh_audit()

    # ------------------------------------------------------------------ #
    # 国际化
    # ------------------------------------------------------------------ #
    def retranslate(self) -> None:
        """语言切换后刷新所有静态文案，不重建页面。"""
        for i, (icon, key) in enumerate(self._nav_specs):
            if i < len(self._nav_buttons):
                self._nav_buttons[i].setText(f"{icon}   {t(key)}")
        self.btn_settings.setText(f"⚙   {t('nav.settings')}")
        self.page_title.setText(t(self.TITLE_KEYS[self.stack.currentIndex()]))
        self.env_badge.setText(
            t("env.admin_ok") if self.elevated else t("env.admin_limited")
        )
        self.btn_env.setText(t("btn.selfcheck"))
        if hasattr(self, "btn_elevate"):
            self.btn_elevate.setText(t("btn.elevate"))
        for page in (self.dashboard, self.dns_page, self.hosts_page, self.repair_page,
                     self.backup_page, self.diagnose_page, self.report_page,
                     self.settings_page):
            hook = getattr(page, "retranslate", None)
            if callable(hook):
                hook()
        # 状态栏可能正显示上一次的体检结论，重算一次
        if self.state.report is not None:
            self._on_report_set(self.state.report)

    def _on_language_changed(self, lang: str) -> None:
        i18n.set_language(lang)
        self.retranslate()
        write_audit(event="settings", target="language", detail=lang, ok=True)

    def _on_region_changed(self, region: str) -> None:
        """区域改变后，已缓存的环境快照必须失效——否则还在用旧区域的探测集。"""
        if self.state.context is not None:
            self.state.context.region_override = region
        self.toast.show_message(t("settings.region.saved"))
        write_audit(event="settings", target="region", detail=region, ok=True)
        self.toast.show_message(t("settings.region.rerun_hint"))

    def _on_setting_changed(self, key: str) -> None:
        if key in ("*", "backup_keep"):
            # 备份保留数变化后立刻执行一次清理，否则要等下次修复才生效
            try:
                removed = self.state.store.prune(keep=self.settings.get_int("backup_keep"))
            except OSError as exc:
                log.warning("清理旧备份失败: %s", exc)
                return
            if removed:
                self.backup_page.refresh()
                self.toast.show_message(t("settings.cleaned", n=len(removed)))

    def _open_data_dir(self) -> None:
        from core import platform_win as pw2

        try:
            os.startfile(pw2.app_data_dir())  # noqa: S606 - 用户显式点击
        except OSError as exc:
            QMessageBox.warning(self, t("err.open_failed"), str(exc))

    def _goto_repair(self) -> None:
        """从仪表盘点「一键修复」：按当前体检建议重建动作列表后再跳转。

        不能只做 switch_page——那会显示上一次遗留的勾选状态，
        用户可能对早已不存在的动作点下执行。
        """
        if self.state.report is None:
            self.toast.show_message("请先完成一次网络体检")
            return
        ids, params = self._suggested_with_params()
        self.repair_page.show_actions(ids, params)
        self.switch_page(self.PAGE_REPAIR)

    def _suggested_with_params(self) -> tuple[list[str], dict]:
        """把检测建议转成可执行动作，并为需要参数的动作补上实测值。

        mtu.optimize 必须有 target_mtu，取自 mtu 检测项 evidence 里的实测值；
        取不到就不提供该动作——宁可少修，也不能用猜的 MTU 去改系统。
        """
        ids = self.state.suggested_actions()
        params: dict[str, dict] = {}
        out: list[str] = []
        best_mtu = self._best_mtu()
        for aid in ids:
            if aid == "mtu.optimize":
                if best_mtu is None:
                    continue
                params[aid] = {"target_mtu": best_mtu}
            out.append(aid)
        return out, params

    def _best_mtu(self) -> int | None:
        if self.state.report is None:
            return None
        for r in self.state.report.results:
            if r.check_id != "mtu":
                continue
            for key in ("best_mtu", "probed_mtu", "path_mtu"):
                val = (r.evidence or {}).get(key)
                if isinstance(val, int) and 1200 <= val <= 1500:
                    return val
        return None

    # ------------------------------------------------------------------ #
    # 体检
    # ------------------------------------------------------------------ #
    def start_scan(self) -> None:
        if self._runner.busy:
            return
        self._pending_kind = "scan"
        self.dashboard.set_busy(True)
        self._set_status("正在体检…")
        self.pt.start()
        ok = self._runner.run(self._task_scan)
        if not ok:
            self.dashboard.set_busy(False)
            self.pt.stop()

    def _task_scan(self, progress=None):
        return self.state.run_diagnosis(progress=progress,
                                        scenario_id=self._pending_scenario)

    def _on_scenario_chosen(self, scenario_id: str) -> None:
        """用户选了某个场景：记录并按该场景的检测范围开始体检。"""
        self.state.scenario_id = scenario_id
        self._pending_scenario = scenario_id
        self.switch_page(self.PAGE_OVERVIEW)
        self.start_scan()

    def _on_report_set(self, report) -> None:
        self._set_status(f"体检完成｜{len(report.results)} 项｜健康分 {report.score}")
        self.status_chip.setText(f"健康分 {report.score}")
        c = T.ACCENT if report.score >= 85 else (T.WARN if report.score >= 60 else T.DANGER)
        self.status_chip.setStyleSheet(
            f"color:{c};font-size:9pt;border:1px solid {c};border-radius:9px;padding:3px 11px;"
        )
        write_audit(event="scan", target="网络体检",
                    detail=f"{len(report.results)} 项，健康分 {report.score}", ok=True)

    # ------------------------------------------------------------------ #
    # 修复
    # ------------------------------------------------------------------ #
    def _apply_dns_plan(self, plan_id: str, servers: list) -> None:
        if plan_id == "dhcp":
            self._execute_ids(["dns.restore_dhcp"], servers=[])
        else:
            self._execute_ids(["dns.set_public"], servers=servers)

    def _execute_ids(self, ids: list[str], servers: list | None = None) -> None:
        """供页面直接调用（HOSTS 清理、DNS 方案）——同样走统一执行通道。"""
        self._pending_servers = servers
        self._do_execute(ids, dry_run=False)

    def _do_execute(self, ids: list[str], dry_run: bool = False) -> None:
        if not ids:
            return
        if self._runner.busy:
            self.toast.show_message("正在执行其它任务，请稍候")
            return
        if not self.elevated and any(_needs_elevation(i) for i in ids):
            self.toast.show_message("该操作需要管理员权限，请先点「以管理员身份重启」")
            return
        ctx = self.state.context or self.state.create_context()
        self._pending_kind = "dryrun" if dry_run else "repair"
        self.repair_page.set_running(True, "正在创建备份…")
        self.switch_page(self.PAGE_REPAIR)
        self.pt.start()

        servers = self._pending_servers
        self._pending_servers = None
        ok = self._runner.run(self._task_repair, ids=list(ids), dry_run=dry_run,
                              ctx=ctx, servers=servers)
        if not ok:
            self.repair_page.set_running(False)
            self.pt.stop()

    def _task_repair(self, ids, dry_run, ctx, servers, progress=None):
        eng = repair_engine.RepairEngine(dry_run=dry_run)
        plan = eng.plan(ids, ctx, servers=servers)

        def _cb(index: int, total: int, action_id: str, phase: str) -> None:
            label = {"backup": "备份", "apply": "执行", "verify": "校验"}.get(phase, phase)
            if progress:
                progress(index, total, f"{label}：{action_id}")

        return eng.execute(plan, ctx, progress=_cb)

    # ------------------------------------------------------------------ #
    def _do_rollback(self, session_id: str) -> None:
        if self._runner.busy:
            self.toast.show_message("正在执行其它任务，请稍候")
            return
        ctx = self.state.context or self.state.create_context()
        self._pending_kind = "rollback"
        self.pt.start()
        self._set_status("正在回滚…")
        self._runner.run(self._task_rollback, session_id=session_id, ctx=ctx)

    def _task_rollback(self, session_id, ctx, progress=None):
        eng = repair_engine.RepairEngine()
        return eng.rollback(session_id, ctx)

    def _manual_backup(self) -> None:
        if self._runner.busy:
            return
        self._pending_kind = "backup"
        self.pt.start()
        self._runner.run(self._task_manual_backup)

    def _task_manual_backup(self, progress=None):
        ctx = self.state.context or self.state.create_context()
        return repair_engine.create_manual_backup(self.state.store, ctx)

    def _save_hosts_text(self, text: str) -> None:
        if not self.elevated:
            self.toast.show_message("修改 HOSTS 需要管理员权限")
            return
        box = QMessageBox(self)
        box.setWindowTitle("确认保存 HOSTS")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(
            "将用编辑后的内容覆盖 HOSTS 文件。\n\n"
            "保存前会自动备份当前文件，可在「备份与回滚」中还原。\n"
            "错误的内容可能导致部分网站无法访问。\n\n是否保存？"
        )
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.button(QMessageBox.StandardButton.Yes).setText("确认保存")
        box.button(QMessageBox.StandardButton.No).setText("取消")
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        if self._runner.busy:
            return
        self._pending_kind = "hosts_save"
        self.pt.start()
        self._runner.run(self._task_save_hosts, text=text)

    def _task_save_hosts(self, text: str, progress=None):
        from core.repair.hosts_actions import save_hosts_text

        session, result = save_hosts_text(self.state.store, text)
        return {"session": session, "result": result}

    # ------------------------------------------------------------------ #
    # 报告导出
    # ------------------------------------------------------------------ #
    def _export_report(self, fmt: str) -> None:
        if not self.state.report:
            self.toast.show_message("还没有体检结果，先做一次体检")
            return
        from app.report import ReportExporter

        try:
            path = ReportExporter().export(self.state.report, fmt)
        except Exception as exc:  # noqa: BLE001 - 导出失败要让用户看到原因
            log.exception("报告导出失败")
            QMessageBox.warning(self, "导出失败", f"无法生成报告：\n{exc}")
            return
        write_audit(event="export", target=f"{fmt.upper()} 报告", detail=path, ok=True)
        self.report_page.refresh_audit()
        box = QMessageBox(self)
        box.setWindowTitle("导出成功")
        box.setText(f"报告已保存到：\n{path}")
        box.setStandardButtons(QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Ok)
        if box.exec() == QMessageBox.StandardButton.Open:
            pw.run_cmd(["explorer", "/select,", path], timeout=5)

    # ------------------------------------------------------------------ #
    # 任务回调
    # ------------------------------------------------------------------ #
    def _on_progress(self, done: int, total: int, text: str) -> None:
        self._set_status(text)
        if self._pending_kind in ("repair", "dryrun"):
            self.repair_page.set_progress(done, total, text)

    def _on_task_done(self, value) -> None:
        self.pt.stop()
        kind, self._pending_kind = self._pending_kind, ""

        if kind == "scan":
            self.dashboard.set_busy(False)
            self.state.set_report(value)
            return

        if kind in ("repair", "dryrun"):
            self.repair_page.set_running(False)
            self._render_repair_report(value, dry_run=(kind == "dryrun"))
            return

        if kind == "rollback":
            self._render_rollback(value)
            return

        if kind == "backup":
            self.state.set_last_backup(value)
            self.backup_page.refresh()
            write_audit(event="backup", target="手动备份",
                        detail=value.session_id, ok=True, session_id=value.session_id)
            self.toast.show_message("已创建备份快照")
            return

        if kind == "hosts_save":
            payload = value or {}
            session = payload.get("session")
            self.hosts_page.reload()
            self.backup_page.refresh()
            write_audit(event="hosts_edit", target="HOSTS 手工编辑",
                        detail=f"已保存并备份，会话 {getattr(session, 'session_id', '')}",
                        ok=True, session_id=getattr(session, "session_id", ""))
            self.toast.show_message("HOSTS 已保存，原始文件已备份")
            return

    def _on_task_failed(self, msg: str) -> None:
        self.pt.stop()
        kind, self._pending_kind = self._pending_kind, ""
        if kind == "scan":
            self.dashboard.set_busy(False)
        if kind in ("repair", "dryrun"):
            self.repair_page.set_running(False)
        self._set_status("任务失败")
        log.error("任务失败[%s]: %s", kind, msg)
        QMessageBox.critical(
            self, "任务失败",
            f"操作未能完成：\n\n{msg}\n\n若反复出现，请到「报告与日志」导出诊断报告。"
        )

    def _render_repair_report(self, report, dry_run: bool) -> None:
        for r in getattr(report, "results", []):
            self.repair_page.update_result(r)
        if dry_run:
            self.repair_page.set_running(False, "")
            QMessageBox.information(
                self, "演练完成",
                f"演练未修改任何系统设置。\n\n"
                f"已创建备份会话：{report.session_id}\n"
                f"共 {len(report.results)} 项动作，全部通过备份阶段校验。\n\n"
                f"确认无误后可直接点「执行修复」。"
            )
            self.backup_page.refresh()
            return

        ok = report.ok_count
        fail = report.fail_count
        self.repair_page.refresh()
        self.backup_page.refresh()
        lines = [f"执行完成：成功 {ok} 项" + (f"，失败 {fail} 项" if fail else "")]
        if getattr(report, "partial", False):
            lines.append("")
            lines.append("⚠ 部分动作未成功，建议到「备份与回滚」回滚本次会话。")
        lines.append("")
        lines.append(f"备份会话：{report.session_id}")
        write_audit(event="repair", target="一键修复",
                    detail=f"成功 {ok}，失败 {fail}", ok=(fail == 0),
                    session_id=report.session_id)
        QMessageBox.information(self, "修复完成", "\n".join(lines))

    def _render_rollback(self, report) -> None:
        self.backup_page.refresh()
        ok = getattr(report, "ok_count", 0)
        fail = getattr(report, "fail_count", 0)
        msg = f"回滚完成：成功 {ok} 项" + (f"，失败 {fail} 项" if fail else "")
        if fail:
            msg += "\n\n部分项目未能还原，详情见下方与 report 日志。"
        write_audit(event="rollback", target="回滚备份",
                    detail=f"成功 {ok}，失败 {fail}", ok=(fail == 0),
                    session_id=getattr(report, "session_id", ""))
        QMessageBox.information(self, "回滚结果", msg)

    # ------------------------------------------------------------------ #
    # 杂项
    # ------------------------------------------------------------------ #
    def _set_status(self, text: str) -> None:
        self.status_chip.setText(text[:46])

    def _pulse_status(self) -> None:
        self._pulse_phase += 0.35
        dots = "." * (int(self._pulse_phase) % 4)
        base = self.status_chip.text().rstrip(".")
        self.status_chip.setText(base + dots)

    def _elevate(self) -> None:
        try:
            from app.sysutil import relaunch_as_admin
        except ImportError as exc:
            QMessageBox.warning(self, "不可用", f"提权模块不可用：{exc}")
            return
        if relaunch_as_admin():
            self.close()
        else:
            QMessageBox.information(
                self, "已取消",
                "未获得管理员权限，软件将以只读模式继续运行。\n"
                "体检、报告导出、备份查看仍然可用。"
            )

    def _show_env_checks(self) -> None:
        try:
            from app.sysutil import run_env_checks
        except ImportError as exc:
            QMessageBox.warning(self, "不可用", f"环境自检模块不可用：{exc}")
            return
        try:
            checks = run_env_checks()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "自检失败", str(exc))
            return
        dlg = _EnvDialog(checks, self)
        dlg.exec()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._runner.busy:
            box = QMessageBox(self)
            box.setWindowTitle("任务进行中")
            box.setText("仍有任务在执行，立即退出可能中断系统修改并留下未完成的配置。\n\n确定退出？")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.No)
            if box.exec() != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.pt.stop()
        super().closeEvent(event)


class _EnvDialog(QDialog):
    def __init__(self, checks, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("环境自检")
        self.setMinimumWidth(620)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(9)
        title = QLabel("运行环境自检")
        title.setObjectName("H2")
        lay.addWidget(title)

        for c in checks:
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 3, 0, 3)
            dot = QLabel("●")
            color = {"ok": T.ACCENT, "warn": T.WARN, "critical": T.DANGER}.get(c.severity, T.TEXT_FAINT)
            dot.setStyleSheet(f"color:{color};")
            h.addWidget(dot)
            name = QLabel(c.name)
            name.setFixedWidth(130)
            name.setStyleSheet(f"color:{T.TEXT};")
            h.addWidget(name)
            det = QLabel(c.detail)
            det.setWordWrap(True)
            det.setObjectName("Caption")
            h.addWidget(det, 1)
            lay.addWidget(row)
            if not c.ok and c.fix_hint:
                hint = QLabel(f"    → {c.fix_hint}")
                hint.setStyleSheet(f"color:{T.TEXT_FAINT};font-size:8.5pt;")
                hint.setWordWrap(True)
                lay.addWidget(hint)

        lay.addStretch(1)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btns.rejected.connect(self.reject)
        btns.accepted.connect(self.accept)
        lay.addWidget(btns)


def _needs_elevation(action_id: str) -> bool:
    """查动作元数据判断是否需要提权。未登记的动作按需要提权处理（保守）。"""
    from core.action_ids import ACTIONS

    meta = ACTIONS.get(action_id)
    return True if meta is None else meta.requires_elevation


__all__ = ["MainWindow", "WINDOW_TITLE"]
