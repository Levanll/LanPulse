r"""补全所有页面的硬编码中文文案（i18n 收尾）。

背景：v1.0.0 做 i18n 时只处理了「检测结果」的文案，**UI 骨架**（卡片标题、
按钮文字、提示语）大量直接写中文。中文界面看不出来，但英文界面会露馅——
这正是生成英文截图时发现的。

做法：把每个硬编码串换成 t("key")，并确保 key 在两份语言包里都存在。

约束：
  * key 命名遵循现有约定（page.<page>.*, btn.*, msg.*）
  * 不改变布局，只替换文案来源
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: (文件, 原文, 新表达式, 中文, 英文)
#: 逐条列出而不是正则批量替换——这些文案语义各不相同，
#: 批量替换容易把一个 key 套错到另一句话上。
PATCHES: list[tuple[str, str, str, str, str]] = [
    # ---------------- dashboard ----------------
    ("dashboard.py", '"尚未体检"', 't("dashboard.not_scanned")',
     "尚未体检", "Not scanned yet"),
    ("dashboard.py", 'Card("当前网络状态", "数据来自最近一次体检的快照")',
     'Card(t("dashboard.metrics_title"), t("dashboard.metrics_desc"))',
     "当前网络状态", "Current network state"),
    ("dashboard.py", 'Card("发现的问题")', 'Card(t("dashboard.problems_title"))',
     "发现的问题", "Findings"),
    ("dashboard.py", '"功能入口"', 't("dashboard.entries_title")',
     "功能入口", "Quick actions"),
    ("dashboard.py", '"正在体检…" if busy else "开始网络体检"',
     't("dashboard.scanning") if busy else t("btn.scan")',
     "正在体检…", "Scanning…"),
    ("dashboard.py", '"一键修复"', 't("btn.one_click_fix")',
     "一键修复", "One-click fix"),
    ("dashboard.py", '"没有发现需要处理的网络问题 ✓"',
     't("dashboard.no_problems")', "", ""),
    ("dashboard.py",
     '"所有检测与修复均在本机完成，不联网上传任何数据。每项系统修改前都会自动备份，'
     '可在「备份与回滚」中随时还原。"',
     't("dashboard.footer")',
     "所有检测与修复均在本机完成，不联网上传任何数据。每项系统修改前都会自动备份，可在「备份与回滚」中随时还原。",
     "All checks and repairs run locally with zero upload. Every change is backed up first and can be rolled back at any time."),
    ("dashboard.py", 'f"共检测 {len(report.results)} 项，全部正常"',
     't("dashboard.all_ok", n=len(report.results))',
     "共检测 {n} 项，全部正常", "All {n} checks passed"),
    ("dashboard.py", 'f"共检测 {len(report.results)} 项，发现 {len(problems)} 个问题"',
     't("dashboard.with_problems", n=len(report.results), m=len(problems))',
     "共检测 {n} 项，发现 {m} 个问题", "{n} checks, {m} issues found"),

    # ---------------- backup ----------------
    ("backup.py", '"打开备份目录"', 't("btn.open_backup_dir")',
     "打开备份目录", "Open backup folder"),
    ("backup.py", '"手动创建备份"', 't("btn.manual_backup")',
     "手动创建备份", "Create backup now"),
    ("backup.py", 'f"恢复到 {time.strftime(\'%m-%d %H:%M\', time.localtime(s.created_at))} 的状态"',
     't("backup.restore_btn", ts=time.strftime("%m-%d %H:%M", time.localtime(s.created_at)))',
     "恢复到 {ts} 的状态", "Restore to {ts}"),
    ("backup.py", '"回滚只会还原备份中记录的项目，不会影响备份之后你对系统做的其它修改。"',
     't("backup.rollback_hint")',
     "回滚只会还原备份中记录的项目，不会影响备份之后你对系统做的其它修改。",
     "Rollback only restores the items recorded in this backup; later unrelated changes are untouched."),

    # ---------------- diagnose ----------------
    ("diagnose.py", '"选择左侧任一项查看详情"', 't("diagnose.pick_one")',
     "选择左侧任一项查看详情", "Select a row on the left to see details"),
    ("diagnose.py", '"指标"', 't("diagnose.metrics")', "指标", "Metrics"),
    ("diagnose.py", '"建议"', 't("diagnose.advice")', "建议", "Advice"),
    ("diagnose.py", '"原始证据"', 't("diagnose.evidence")', "原始证据", "Raw evidence"),

    # ---------------- dns ----------------
    ("dns.py", '"域名解析服务决定你访问网站走哪条路，是“网页打不开”的首要排查点"',
     't("dns.subtitle")',
     "域名解析服务决定你访问网站走哪条路，是「网页打不开」的首要排查点",
     "DNS decides the route to every site you visit — the first thing to check when pages fail to open"),
    ("dns.py", 'Card("当前 DNS 配置", "读取自当前承载上网流量的网卡")',
     'Card(t("dns.current_title"), t("dns.current_desc"))',
     "当前 DNS 配置", "Current DNS configuration"),
    ("dns.py", '"选择方案"', 't("dns.choose_plan")', "选择方案", "Choose a plan"),
    ("dns.py", '"应用所选方案"', 't("btn.apply_plan")', "应用所选方案", "Apply selected plan"),
    ("dns.py", '"恢复自动获取"', 't("btn.restore_dhcp")', "恢复自动获取", "Use DHCP again"),

    # ---------------- hosts ----------------
    ("hosts.py", '"重新读取"', 't("btn.reload")', "重新读取", "Reload"),
    ("hosts.py", '"高级编辑"', 't("btn.advanced_edit")', "高级编辑", "Advanced edit"),
    ("hosts.py", '"退出编辑"', 't("btn.exit_edit")', "退出编辑", "Exit editing"),
    ("hosts.py", '"放弃修改"', 't("btn.discard")', "放弃修改", "Discard"),
    ("hosts.py", '"保存（自动备份）"', 't("btn.save_hosts")', "保存（自动备份）", "Save (auto backup)"),
    ("hosts.py", '"清理异常记录"', 't("btn.clean_hosts")', "清理异常记录", "Clean suspicious entries"),
    ("hosts.py", '"恢复系统默认"', 't("btn.restore_hosts")', "恢复系统默认", "Restore default"),
    ("hosts.py", '"内容未变化，无需保存。"', 't("hosts.no_change")',
     "内容未变化，无需保存。", "No changes to save."),

    # ---------------- repair ----------------
    ("repair.py", '"根据体检结果自动勾选，你可以逐项调整；高危项默认不勾选"',
     't("repair.subtitle")',
     "根据体检结果自动勾选，你可以逐项调整；高危项默认不勾选",
     "Preselected from the scan; adjust as you like — high-risk items start unchecked"),
    ("repair.py", '"先做一次网络体检，系统会在这里列出建议的修复项。"',
     't("repair.empty_hint")',
     "先做一次网络体检，系统会在这里列出建议的修复项。",
     "Run a scan first and the suggested fixes will appear here."),
    ("repair.py", '"全不选"', 't("btn.select_none")', "全不选", "Select none"),
    ("repair.py", '"只选低风险"', 't("btn.select_safe")', "只选低风险", "Low risk only"),
    ("repair.py", '"先演练"', 't("btn.dry_run")', "先演练", "Dry run"),
    ("repair.py", '"执行修复"', 't("btn.execute_repair")', "执行修复", "Run repair"),

    # ---------------- report ----------------
    ("report.py", '"尚未体检"', 't("dashboard.not_scanned")', "", ""),
    ("report.py", 'Card("导出本机体检报告"', 'Card(t("report.export_title")',
     "导出本机体检报告", "Export this scan"),
    ("report.py", '"导出 HTML 报告"', 't("btn.export_html")', "导出 HTML 报告", "Export HTML"),
    ("report.py", '"导出 JSON"', 't("btn.export_json")', "导出 JSON", "Export JSON"),
    ("report.py", '"导出 TXT"', 't("btn.export_text")', "导出 TXT", "Export TXT"),
    ("report.py", '"刷新"', 't("btn.refresh")', "刷新", "Refresh"),
]

#: 需要新增到语言包的 key（中文, 英文）
EXTRA_KEYS: dict[str, tuple[str, str]] = {
    "dashboard.not_scanned": ("尚未体检", "Not scanned yet"),
    "dashboard.metrics_title": ("当前网络状态", "Current network state"),
    "dashboard.metrics_desc": ("数据来自最近一次体检的快照",
                               "Taken from the most recent scan"),
    "dashboard.problems_title": ("发现的问题", "Findings"),
    "dashboard.entries_title": ("功能入口", "Quick actions"),
    "dashboard.scanning": ("正在体检…", "Scanning…"),
    "dashboard.no_problems": ("没有发现需要处理的网络问题 ✓",
                              "No network problems found ✓"),
    "dashboard.footer": (
        "所有检测与修复均在本机完成，不联网上传任何数据。每项系统修改前都会自动备份，可在「备份与回滚」中随时还原。",
        "All checks and repairs run locally with zero upload. Every change is backed up first and can be rolled back at any time."),
    "dashboard.all_ok": ("共检测 {n} 项，全部正常", "All {n} checks passed"),
    "dashboard.with_problems": ("共检测 {n} 项，发现 {m} 个问题",
                                "{n} checks, {m} issues found"),
    "dashboard.confidence": ("置信度 {level}", "Confidence: {level}"),
    "dashboard.other_issues": ("其它异常（{n} 项，未归入上述原因）",
                               "Other issues ({n}, not covered above)"),

    "btn.scan": ("开始网络体检", "Run scan"),
    "btn.one_click_fix": ("一键修复", "One-click fix"),
    "btn.open_backup_dir": ("打开备份目录", "Open backup folder"),
    "btn.manual_backup": ("手动创建备份", "Create backup now"),
    "btn.apply_plan": ("应用所选方案", "Apply selected plan"),
    "btn.restore_dhcp": ("恢复自动获取", "Use DHCP again"),
    "btn.reload": ("重新读取", "Reload"),
    "btn.advanced_edit": ("高级编辑", "Advanced edit"),
    "btn.exit_edit": ("退出编辑", "Exit editing"),
    "btn.discard": ("放弃修改", "Discard"),
    "btn.save_hosts": ("保存（自动备份）", "Save (auto backup)"),
    "btn.clean_hosts": ("清理异常记录", "Clean suspicious entries"),
    "btn.restore_hosts": ("恢复系统默认", "Restore default"),
    "btn.select_none": ("全不选", "Select none"),
    "btn.select_safe": ("只选低风险", "Low risk only"),
    "btn.dry_run": ("先演练", "Dry run"),
    "btn.execute_repair": ("执行修复", "Run repair"),
    "btn.export_html": ("导出 HTML 报告", "Export HTML"),
    "btn.export_json": ("导出 JSON", "Export JSON"),
    "btn.export_text": ("导出 TXT", "Export TXT"),
    "btn.refresh": ("刷新", "Refresh"),

    "diagnose.pick_one": ("选择左侧任一项查看详情",
                          "Select a row on the left to see details"),
    "diagnose.metrics": ("指标", "Metrics"),
    "diagnose.advice": ("建议", "Advice"),
    "diagnose.evidence": ("原始证据", "Raw evidence"),

    "backup.restore_btn": ("恢复到 {ts} 的状态", "Restore to {ts}"),
    "backup.rollback_hint": (
        "回滚只会还原备份中记录的项目，不会影响备份之后你对系统做的其它修改。",
        "Rollback only restores the items recorded in this backup; later unrelated changes are untouched."),

    "dns.subtitle": (
        "域名解析服务决定你访问网站走哪条路，是「网页打不开」的首要排查点",
        "DNS decides the route to every site you visit — the first thing to check when pages fail to open"),
    "dns.current_title": ("当前 DNS 配置", "Current DNS configuration"),
    "dns.current_desc": ("读取自当前承载上网流量的网卡",
                         "Read from the adapter currently carrying your traffic"),
    "dns.choose_plan": ("选择方案", "Choose a plan"),

    "hosts.no_change": ("内容未变化，无需保存。", "No changes to save."),

    "repair.subtitle": (
        "根据体检结果自动勾选，你可以逐项调整；高危项默认不勾选",
        "Preselected from the scan; adjust as you like — high-risk items start unchecked"),
    "repair.empty_hint": ("先做一次网络体检，系统会在这里列出建议的修复项。",
                          "Run a scan first and the suggested fixes will appear here."),

    "report.export_title": ("导出本机体检报告", "Export this scan"),

    "scenario.intro": ("先选一个最接近你遇到的情况，系统会只跑相关的检查项",
                       "Pick whatever matches your situation; only the relevant checks will run"),
    "scenario.checks_count": ("{n} 项检查", "{n} checks"),
    "scenario.advanced_hint": ("想逐项查看全部检测？用「诊断详情」页可以选择任意单项",
                               "Want every check individually? Use the Diagnostics page"),
    "scenario.btn_full": ("运行完整体检", "Run full checkup"),

    "nav.scenario": ("场景", "Scenarios"),
}


def apply_patches() -> int:
    changed = 0
    for fname, old, new, _zh, _en in PATCHES:
        path = ROOT / "app" / "ui" / "pages" / fname
        if not path.is_file():
            print(f"  [跳过] {fname} 不存在")
            continue
        src = path.read_text(encoding="utf-8")
        if new in src and old not in src:
            continue
        if old not in src:
            print(f"  [未匹配] {fname}: {old[:50]}")
            continue
        src = src.replace(old, new, 1)
        path.write_text(src, encoding="utf-8")
        changed += 1
    return changed


def inject_keys() -> tuple[int, int]:
    n_zh = n_en = 0
    for fname, idx in (("app/i18n_zh.py", 0), ("app/i18n_en.py", 1)):
        path = ROOT / fname
        src = path.read_text(encoding="utf-8")
        added = {k: v[idx] for k, v in EXTRA_KEYS.items() if f'"{k}"' not in src}
        if not added:
            continue
        block = "\n".join(
            "    " + repr(k) + ": " + repr(v) + "," for k, v in added.items()
        )
        i = src.rfind("}")
        src = (src[:i] + "\n    # ---- UI 骨架文案（v1.1.0 补齐）----\n"
               + block + "\n" + src[i:])
        path.write_text(src, encoding="utf-8")
        if idx == 0:
            n_zh = len(added)
        else:
            n_en = len(added)
    return n_zh, n_en


def ensure_t_import() -> int:
    """所有 pages/*.py 都必须 import t。"""
    fixed = 0
    for path in (ROOT / "app" / "ui" / "pages").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        if "from core.i18n import" in src:
            continue
        if " t(" not in src:
            continue
        # 插在第一个 from app.ui 之前
        m = re.search(r"^from app\.ui", src, re.M)
        if m:
            src = src[: m.start()] + "from core.i18n import t\n" + src[m.start():]
            path.write_text(src, encoding="utf-8")
            fixed += 1
    return fixed


def main() -> int:
    n_zh, n_en = inject_keys()
    print(f"语言包新增：zh {n_zh} 条，en {n_en} 条")
    n = apply_patches()
    print(f"页面替换：{n} 处")
    f = ensure_t_import()
    print(f"补充 import：{f} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
