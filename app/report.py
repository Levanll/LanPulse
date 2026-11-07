"""体检报告导出（HTML / JSON / 纯文本）。

三条底线，任何改动都不得突破：
1. 导出的 HTML 必须是**完全离线**的单文件：不引用任何外部字体、脚本、样式表、图片，
   也不发任何网络请求。产品承诺“不收集、不上传”，报告本身也不能偷偷联网，
   因此额外加了 CSP 头，就算将来有人误插外部引用也加载不出来。
2. 所有来自系统的字符串（hosts 行、域名、网卡描述、命令输出）一律 html.escape。
   报告会被用户在浏览器里双击打开，而这些内容全部不可信，必须防 XSS。
3. 报告只是“把检测结果写下来”，不做任何系统修改；写文件统一走
   platform_win.atomic_write，避免磁盘满 / 断电时用户得到一个半截文件。
"""
from __future__ import annotations

import html
import json
import os
import time
import unicodedata
from typing import Any

try:  # 作为 netpulse.app.report 导入（打包入口 / 顶层包为 netpulse 时）
    from core import platform_win as pw
    from core.backup import BACKUP_ROOT_NAME
    from core.models import ChangePreview, CheckResult, DiagnosticReport, Severity
except ImportError:  # 以 PYTHONPATH=<项目根> 导入 app.report 时，上一层包不存在
    from core import platform_win as pw  # type: ignore[no-redef]
    from core.backup import BACKUP_ROOT_NAME  # type: ignore[no-redef]
    from core.models import (  # type: ignore[no-redef]
        ChangePreview,
        CheckResult,
        DiagnosticReport,
        Severity,
    )

from app.ui.theme import T


# --------------------------------------------------------------------------- #
# 通用小工具
# --------------------------------------------------------------------------- #
def _e(text: Any) -> str:
    """统一的 HTML 转义入口。任何拼进 HTML 的动态内容都必须经过它。"""
    return html.escape("" if text is None else str(text), quote=True)


def _sev_color(sev: Severity | str) -> str:
    key = sev.value if isinstance(sev, Severity) else str(sev)
    return T.SEV.get(key, T.TEXT_DIM)


def _time_text(ts: float) -> str:
    if not ts:
        return "—"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))


def _duration_text(seconds: float) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f} 秒"
    return f"{int(seconds // 60)} 分 {int(seconds % 60)} 秒"


def default_out_dir() -> str:
    """桌面优先，没有桌面（Server Core / 重定向失败）时退回程序数据目录。"""
    desktop = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")
    if os.path.isdir(desktop):
        return desktop
    return pw.app_data_dir()


def _default_backup_dir() -> str:
    return os.path.join(pw.app_data_dir(), BACKUP_ROOT_NAME)


# --------------------------------------------------------------------------- #
# HTML 报告
# --------------------------------------------------------------------------- #
# 主题色直接引自 app/ui/theme.py（唯一来源，避免两处维护）。
# 用 CSS 变量承接，避免把整段样式写成 f-string 而到处转义花括号。
_THEME_CSS = f"""
:root {{
  color-scheme: dark;
  --bg-deep: {T.BG_DEEP};
  --bg-base: {T.BG_BASE};
  --bg-panel: {T.BG_PANEL};
  --bg-panel-alt: {T.BG_PANEL_ALT};
  --line: {T.LINE};
  --line-soft: {T.LINE_SOFT};
  --text: {T.TEXT};
  --text-dim: {T.TEXT_DIM};
  --text-faint: {T.TEXT_FAINT};
  --accent: {T.ACCENT};
  --warn: {T.WARN};
  --danger: {T.DANGER};
  --info: {T.INFO};
}}
"""

_BASE_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  background: linear-gradient(135deg, var(--bg-deep) 0%, var(--bg-base) 55%, #0B1220 100%);
  color: var(--text);
  font-family: "Microsoft YaHei UI", "Segoe UI", "PingFang SC", sans-serif;
  font-size: 14px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 980px; margin: 0 auto; padding: 30px 20px 46px; }
.mono { font-family: Consolas, "Cascadia Mono", "Courier New", monospace; }

/* ---- 页头 ---- */
.hero {
  background: rgba(16, 23, 37, 0.94);
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 22px 24px 20px;
  position: relative;
  overflow: hidden;
}
.hero::after {
  content: "";
  position: absolute; inset: 0;
  pointer-events: none;
  background: radial-gradient(680px 220px at 88% -30%, var(--sev-glow, transparent), transparent 70%);
}
.brandline { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.brand {
  font-size: 22px; font-weight: 700; letter-spacing: 1px;
  color: var(--accent);
}
.tagline { color: var(--text-faint); font-size: 12px; letter-spacing: 3px; }
h1 { font-size: 19px; font-weight: 600; margin: 14px 0 4px; }
.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 4px 22px;
  margin: 10px 0 0;
  font-size: 13px;
}
.facts div { display: flex; gap: 8px; }
.facts dt { color: var(--text-faint); white-space: nowrap; }
.facts dd { margin: 0; color: var(--text); }

.scorebox {
  margin-top: 18px;
  display: flex; align-items: flex-end; gap: 18px; flex-wrap: wrap;
}
.score {
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 62px; font-weight: 700; line-height: 0.92;
  color: var(--sev, var(--accent));
}
.score .unit { font-size: 18px; color: var(--text-faint); font-weight: 400; }
.scorecap { color: var(--text-faint); font-size: 11px; letter-spacing: 2px; padding-bottom: 6px; }
.status {
  margin-left: auto;
  padding: 7px 15px;
  border-radius: 999px;
  border: 1px solid var(--sev, var(--accent));
  color: var(--sev, var(--accent));
  background: rgba(255, 255, 255, 0.03);
  font-size: 13px;
}

/* ---- 总体状态色条 ---- */
.bar {
  height: 6px; border-radius: 999px; margin: 16px 0 22px;
  background: var(--sev, var(--accent));
  box-shadow: 0 0 16px -2px var(--sev, var(--accent));
}

/* ---- 摘要 ---- */
h2 {
  font-size: 13px; font-weight: 600; letter-spacing: 2px;
  color: var(--text-faint); margin: 0 0 10px;
}
.summary { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 24px; }
.tile {
  flex: 1 1 150px;
  background: rgba(16, 23, 37, 0.9);
  border: 1px solid var(--line);
  border-top: 3px solid var(--sev, var(--line));
  border-radius: 10px;
  padding: 11px 14px;
}
.tile b {
  display: block;
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 26px; line-height: 1.1;
  color: var(--sev, var(--text));
}
.tile span { color: var(--text-dim); font-size: 12px; }

/* ---- 明细卡片 ---- */
.card {
  background: rgba(16, 23, 37, 0.92);
  border: 1px solid var(--line);
  border-left: 3px solid var(--sev, var(--line));
  border-radius: 12px;
  padding: 15px 18px 16px;
  margin-bottom: 12px;
}
.card-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.card-head h3 { font-size: 15px; font-weight: 600; margin: 0; }
.pill {
  font-size: 12px; padding: 2px 10px; border-radius: 999px;
  color: var(--sev, var(--text-dim));
  border: 1px solid var(--sev, var(--line));
  background: rgba(255, 255, 255, 0.03);
  white-space: nowrap;
}
.cat {
  font-size: 11px; color: var(--text-faint);
  border: 1px solid var(--line-soft); border-radius: 6px; padding: 1px 7px;
}
.card-meta { margin-left: auto; color: var(--text-faint); font-size: 11px; }
.summary-line { margin: 9px 0 0; color: var(--text); }
.detail {
  margin: 9px 0 0; color: var(--text-dim); font-size: 13px;
  white-space: pre-wrap; word-break: break-word;
}
.err {
  margin: 10px 0 0; padding: 9px 12px; border-radius: 8px;
  border: 1px solid rgba(255, 92, 108, 0.45);
  background: rgba(255, 92, 108, 0.08);
  color: var(--danger); font-size: 13px; white-space: pre-wrap;
}
table.kv { width: 100%; border-collapse: collapse; margin-top: 11px; font-size: 13px; }
table.kv th {
  text-align: left; font-weight: 600; color: var(--text-faint);
  font-size: 11px; letter-spacing: 1px;
  border-bottom: 1px solid var(--line); padding: 4px 10px 5px 0;
}
table.kv td {
  padding: 5px 10px 5px 0;
  border-bottom: 1px solid var(--line-soft);
  vertical-align: top;
  word-break: break-word;
}
table.kv tr:last-child td { border-bottom: none; }
td.ok { color: var(--accent); }
td.bad { color: var(--danger); }
td.na { color: var(--text); }
td.note { color: var(--text-dim); }

.advice { margin-top: 12px; }
.advice .label { font-size: 11px; letter-spacing: 1px; color: var(--warn); margin-bottom: 3px; }
.advice ul { margin: 0; padding-left: 20px; }
.advice li { color: var(--text-dim); font-size: 13px; margin: 2px 0; }

details { margin-top: 12px; border-top: 1px dashed var(--line-soft); padding-top: 9px; }
details summary {
  cursor: pointer; color: var(--text-faint); font-size: 12px;
  list-style: none; user-select: none;
}
details summary::-webkit-details-marker { display: none; }
details summary::before { content: "▸ "; }
details[open] summary::before { content: "▾ "; }
details pre {
  margin: 9px 0 0; padding: 10px 12px;
  background: var(--bg-panel-alt);
  border: 1px solid var(--line-soft);
  border-radius: 8px;
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 12px; line-height: 1.5;
  color: var(--text-dim);
  white-space: pre-wrap; word-break: break-all;
  max-height: 420px; overflow: auto;
}

/* ---- 页脚 ---- */
footer {
  margin-top: 26px; padding-top: 14px;
  border-top: 1px solid var(--line-soft);
  color: var(--text-faint); font-size: 12px;
}
footer p { margin: 4px 0; }
footer .mono { color: var(--text-dim); word-break: break-all; }
"""


def _metrics_html(metrics: list[Any]) -> str:
    if not metrics:
        return ""
    rows = []
    for m in metrics:
        cls = "ok" if m.ok is True else ("bad" if m.ok is False else "na")
        rows.append(
            f"<tr><td>{_e(m.name)}</td>"
            f'<td class="mono {cls}">{_e(m.value)}</td>'
            f'<td class="note">{_e(m.note)}</td></tr>'
        )
    return (
        '<table class="kv"><thead><tr><th>指标</th><th>值</th><th>说明</th></tr></thead>'
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )


def _advice_html(items: list[str]) -> str:
    if not items:
        return ""
    lis = "".join(f"<li>{_e(a)}</li>" for a in items)
    return f'<div class="advice"><div class="label">建议处理</div><ul>{lis}</ul></div>'


def _evidence_html(evidence: dict[str, Any]) -> str:
    """原始证据默认折叠：工单排障时要能看全，但平时不该干扰阅读。"""
    if not evidence:
        return ""
    try:
        text = json.dumps(evidence, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError) as exc:
        # evidence 里混入不可序列化对象时，宁可给出可读提示，也不要让整份报告导出失败
        text = f"[证据无法序列化为 JSON: {exc}]"
    return f"<details><summary>原始证据（{len(text)} 字符）</summary><pre>{_e(text)}</pre></details>"


def _card_html(r: CheckResult) -> str:
    sev = r.severity
    color = _sev_color(sev)
    head = (
        f'<div class="card-head"><h3>{_e(r.title)}</h3>'
        f'<span class="pill" style="--sev:{color}">{_e(sev.label)}</span>'
        f'<span class="cat">{_e(r.category)}</span>'
        f'<span class="card-meta mono">{_e(r.check_id)} · {r.duration_ms} ms</span></div>'
    )
    summary = f'<p class="summary-line">{_e(r.summary)}</p>' if r.summary else ""
    detail = f'<div class="detail">{_e(r.detail)}</div>' if r.detail else ""
    err = ""
    if r.error:
        err = f'<div class="err">该检测项执行失败，结论不可用：\n{_e(r.error)}</div>'
    return (
        f'<section class="card" style="--sev:{color}">{head}{summary}{err}{detail}'
        f"{_metrics_html(r.metrics)}{_advice_html(r.advice)}{_evidence_html(r.evidence)}</section>"
    )


def _build_html(report: DiagnosticReport, *, backup_dir: str) -> str:
    overall = report.overall
    color = _sev_color(overall)
    counts = report.by_severity()
    started = report.started_at or time.time()
    finished = report.finished_at or started
    duration = finished - started
    elevated_text = "是（管理员）" if report.elevated else "否（普通用户）"

    tiles = [
        ("正常", counts["ok"], T.ACCENT),
        ("提示", counts["info"], T.INFO),
        ("异常", counts["warn"], T.WARN),
        ("严重", counts["critical"], T.DANGER),
    ]
    if counts["skip"]:
        tiles.append(("跳过", counts["skip"], T.SKIP))
    tiles_html = "".join(
        f'<div class="tile" style="--sev:{c}"><b>{n}</b><span>{_e(label)}</span></div>'
        for label, n, c in tiles
    )

    cards = "".join(_card_html(r) for r in report.results)
    if not report.results:
        cards = '<section class="card"><p class="summary-line">本次没有任何检测结果。</p></section>'

    backup_line = (
        f'<p>配置备份目录：<span class="mono">{_e(backup_dir)}</span>'
        f"（修复前的原始状态按会话保存在此，可直接打开核对或手工还原）</p>"
        if os.path.isdir(backup_dir)
        else '<p>本次尚未产生任何备份 —— 该目录只会在执行修复前自动创建。</p>'
    )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>LanPulse 网络体检报告 · {_e(report.host)}</title>
<style>{_THEME_CSS}{_BASE_CSS}</style>
</head>
<body>
<div class="wrap">

  <header class="hero" style="--sev:{color}; --sev-glow:{color}33">
    <div class="brandline">
      <span class="brand">LanPulse</span>
      <span class="tagline">NETWORK DIAGNOSTICS</span>
    </div>
    <h1>网络体检报告</h1>
    <dl class="facts">
      <div><dt>主机名</dt><dd class="mono">{_e(report.host or "未知")}</dd></div>
      <div><dt>操作系统</dt><dd>{_e(report.os_name or "未知")}</dd></div>
      <div><dt>检测时间</dt><dd class="mono">{_e(_time_text(finished))}</dd></div>
      <div><dt>管理员权限</dt><dd>{_e(elevated_text)}</dd></div>
      <div><dt>检测耗时</dt><dd class="mono">{_e(_duration_text(duration))}</dd></div>
      <div><dt>报告编号</dt><dd class="mono">{_e(report.report_id)}</dd></div>
    </dl>
    <div class="scorebox">
      <div class="score">{report.score}<span class="unit">/100</span></div>
      <div class="scorecap">HEALTH SCORE</div>
      <div class="status">总体状态 · {_e(overall.label)}</div>
    </div>
  </header>

  <div class="bar" style="--sev:{color}"></div>

  <h2>结果概览</h2>
  <div class="summary">{tiles_html}</div>

  <h2>检测明细（共 {len(report.results)} 项）</h2>
  {cards}

  <footer>
    <p><b>本报告仅在本机生成，未上传任何数据。</b>
       报告不包含任何外部链接、脚本或图片，断网状态下可正常查看。</p>
    <p>报告内容是导出时刻的状态快照，网络配置随环境变化，重新体检可能得到不同结论。</p>
    {backup_line}
    <p>LanPulse · 报告编号 <span class="mono">{_e(report.report_id)}</span>
       · 生成于 <span class="mono">{_e(_time_text(time.time()))}</span></p>
  </footer>

</div>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
# 纯文本报告
# --------------------------------------------------------------------------- #
def _char_width(ch: str) -> int:
    """终端里中日韩全角字符占两列，用它来算真实显示宽度。"""
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _display_width(text: str) -> int:
    return sum(_char_width(c) for c in text)


def _pad(text: str, width: int) -> str:
    """按显示宽度左对齐补空格。超长文本不截断（截断会丢排障信息）。"""
    return text + " " * max(0, width - _display_width(text))


_RULE = "=" * 78
_THIN = "-" * 78


def _kv_table(rows: list[tuple[str, str, str]], indent: str = "  ") -> str:
    """三列（指标 / 值 / 说明）对齐表格。"""
    headers = ("指标", "值", "说明")
    w0 = max([_display_width(headers[0])] + [_display_width(r[0]) for r in rows])
    w1 = max([_display_width(headers[1])] + [_display_width(r[1]) for r in rows])
    out = [
        indent + _pad(headers[0], w0) + "  " + _pad(headers[1], w1) + "  " + headers[2],
        indent + "-" * w0 + "  " + "-" * w1 + "  " + "-" * len(headers[2]),
    ]
    for name, value, note in rows:
        out.append(indent + _pad(name, w0) + "  " + _pad(value, w1) + "  " + note)
    return "\n".join(out).rstrip()


def _evidence_lines(evidence: dict[str, Any], limit: int = 1600) -> list[str]:
    """问题项的原始证据按行贴进纯文本报告，方便直接粘贴到工单。"""
    if not evidence:
        return []
    try:
        text = json.dumps(evidence, ensure_ascii=False, indent=2, default=str)
    except (TypeError, ValueError) as exc:
        return [f"     [证据无法序列化为 JSON: {exc}]"]
    if len(text) > limit:
        text = text[:limit] + f"\n…（已截断，完整内容见 JSON / HTML 报告）"
    return ["  原始证据:", *[f"    {line}" for line in text.splitlines()]]


def _build_text(report: DiagnosticReport, *, backup_dir: str) -> str:
    overall = report.overall
    counts = report.by_severity()
    started = report.started_at or time.time()
    finished = report.finished_at or started
    elevated_text = "是（管理员）" if report.elevated else "否（普通用户）"

    lines = [
        _RULE,
        " LanPulse 网络体检报告",
        _RULE,
        f" 主机名       : {report.host or '未知'}",
        f" 操作系统     : {report.os_name or '未知'}",
        f" 检测时间     : {_time_text(finished)}",
        f" 管理员权限   : {elevated_text}",
        f" 检测耗时     : {_duration_text(finished - started)}",
        f" 报告编号     : {report.report_id}",
        f" 健康分       : {report.score} / 100      总体状态: {overall.label}",
        _THIN,
        " 结果统计: 正常 {ok} | 提示 {info} | 异常 {warn} | 严重 {crit} | 跳过 {skip}".format(
            ok=counts["ok"], info=counts["info"], warn=counts["warn"],
            crit=counts["critical"], skip=counts["skip"],
        ),
        _THIN,
        "",
    ]

    if not report.results:
        lines.append("  本次没有任何检测结果。")

    for idx, r in enumerate(report.results, start=1):
        lines.append(f"[{idx}] {r.severity.label} | {r.title}（{r.category} / {r.check_id}）")
        if r.summary:
            lines.append(f"  摘要: {r.summary}")
        if r.error:
            lines.append("  ! 该检测项执行失败，结论不可用:")
            lines.extend(f"    {ln}" for ln in r.error.splitlines())
        if r.detail:
            lines.append("  详情:")
            lines.extend(f"    {ln}" for ln in r.detail.splitlines())
        if r.metrics:
            lines.append("")
            lines.append(_kv_table([(m.name, m.value, m.note) for m in r.metrics]))
        if r.advice:
            lines.append("  建议:")
            lines.extend(f"    - {a}" for a in r.advice)
        if r.severity in (Severity.WARN, Severity.CRITICAL):
            lines.extend(_evidence_lines(r.evidence))
        lines.append("")
        lines.append(_THIN)

    lines.extend([
        "",
        " 说明:",
        "   本报告仅在本机生成，未上传任何数据。",
        "   报告内容是导出时刻的状态快照，重新体检可能得到不同结论。",
        f"   配置备份目录: {backup_dir}",
        f"   生成于 {_time_text(time.time())}",
        "",
    ])
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 修复预览清单
# --------------------------------------------------------------------------- #
def _block(label: str, value: str, indent: str = "   ") -> list[str]:
    """多行值统一按同一缩进续行，避免“改前/改后”错位。"""
    text = (value or "").strip()
    if not text:
        return []
    parts = text.splitlines()
    out = [f"{indent}{label}: {parts[0]}"]
    out.extend(f"{indent}{' ' * _display_width(label)}  {ln}" for ln in parts[1:])
    return out


def build_fix_plan_summary(previews: list[ChangePreview]) -> str:
    """把修复预览渲染成二次确认对话框里的纯文本清单。

    格式刻意保持“人话 + 逐项编号”，因为用户此刻要做的是判断“我要不要让它改这些”，
    不是读技术文档。空列表也给明确结论，不要留一个空白对话框。
    """
    items = list(previews)
    if not items:
        return "没有需要执行的修改。\n\n当前系统未发现需要自动修复的项目，无需做任何改动。"

    lines = [f"将要执行 {len(items)} 项修改：", ""]
    for idx, p in enumerate(items, start=1):
        lines.append(f"{idx}. {p.target}")
        lines.extend(_block("修改前", p.before))
        lines.extend(_block("修改后", p.after))
        if p.note:
            lines.extend(_block("说明", p.note))
        lines.append("")
    lines.extend([
        "执行前会自动备份当前配置；如需还原，可在「备份与回滚」页面一键回滚。",
        "若某项修改与你预期不符，请取消并先查看该检测项的原始证据。",
    ])
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 导出器
# --------------------------------------------------------------------------- #
_EXT = {"html": "html", "json": "json", "text": "txt"}


class ReportExporter:
    """把 DiagnosticReport 落成文件。三种格式共用同一份默认路径规则。"""

    def __init__(self, out_dir: str | None = None, *, backup_root: str | None = None) -> None:
        self._out_dir = os.path.abspath(out_dir) if out_dir else ""
        # None 表示按 BackupStore 的默认位置推导，报告里只做展示，绝不在导出时创建目录
        self._backup_root = backup_root

    # ---- 路径 ----
    @property
    def out_dir(self) -> str:
        return self._out_dir or default_out_dir()

    @property
    def backup_dir(self) -> str:
        return self._backup_root or _default_backup_dir()

    def _resolve(self, ext: str, path: str | None) -> str:
        if path:
            target = os.path.abspath(os.path.expanduser(path))
        else:
            base = self.out_dir
            name = f"LanPulse报告_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"
            target = os.path.join(base, name)
        parent = os.path.dirname(target)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return target

    # ---- 三种格式 ----
    def export_html(self, report: DiagnosticReport, path: str | None = None) -> str:
        target = self._resolve(_EXT["html"], path)
        pw.atomic_write(target, _build_html(report, backup_dir=self.backup_dir))
        return target

    def export_json(self, report: DiagnosticReport, path: str | None = None) -> str:
        target = self._resolve(_EXT["json"], path)
        # to_json 已用 ensure_ascii=False；atomic_write 以 utf-8(无 BOM) 落盘
        pw.atomic_write(target, report.to_json(indent=2))
        return target

    def export_text(self, report: DiagnosticReport, path: str | None = None) -> str:
        target = self._resolve(_EXT["text"], path)
        pw.atomic_write(target, _build_text(report, backup_dir=self.backup_dir))
        return target

    def export(self, report: DiagnosticReport, fmt: str) -> str:
        key = (fmt or "").strip().lower()
        handlers = {"html": self.export_html, "json": self.export_json, "text": self.export_text}
        if key not in handlers:
            raise ValueError(f"不支持的报告格式: {fmt!r}（可选 html / json / text）")
        return handlers[key](report)


__all__ = [
    "ReportExporter",
    "build_fix_plan_summary",
    "default_out_dir",
]
