"""渲染层的国际化辅助。

核心问题：检测在后台线程执行，若当场把文案翻译成字符串，用户切换语言后
旧结果会冻结在旧语言。解法是**渲染时翻译**：结果里存 key，UI/报告显示前
用本模块解析。

`tr_or_raw()` 是关键：同一个字段既可能是 key（`metric.link_speed`），
也可能是动态值（网卡名"以太网"、IP、"www.baidu.com"）。前者翻译，
后者原样返回——用 t() 的缺失标记 ⟦ ⟧ 来区分，不需要额外的类型判断。
"""
from __future__ import annotations

from typing import Any, Iterable

from core.i18n import t
from core.models import CheckResult, Metric, Severity

MISSING_PREFIX = "\u27e6"  # ⟦


def tr_or_raw(text: str) -> str:
    """已知 i18n key 则翻译，否则原样返回。

    用"翻译结果是否带缺失标记"来判断，避免维护一份"哪些字段是 key"的清单——
    那种清单一定会随代码演进失配。
    """
    if not text:
        return text
    out = t(text)
    return text if out.startswith(MISSING_PREFIX) else out


def tr(text: str, **fmt: Any) -> str:
    """明确知道是 key 时用这个；缺 key 会显式暴露 ⟦key⟧。"""
    return t(text, **fmt)


def tr_metric(m: Metric) -> tuple[str, str]:
    """返回 (翻译后的指标名, 翻译后的备注)。"""
    return tr_or_raw(m.name), tr_or_raw(m.note)


def _resolve_args(args: dict[str, Any]) -> dict[str, Any]:
    """委托给 core 层的同一实现。

    曾经这里有一份复制粘贴的解析逻辑，与 core 版本逐渐分叉，
    导致 `profiles_parts` 只在一边支持、界面上出现 `{profiles}` 未填充。
    现在只保留一个实现，UI 与检测层行为严格一致。
    """
    from core.i18n_args import resolve_args

    return resolve_args(args)


def tr_result_summary(r: CheckResult) -> str:
    """优先用 summary_key 重新翻译，保证切换语言后立即跟随。"""
    if r.summary_key:
        return t(r.summary_key, **_resolve_args(r.summary_args))
    return tr_or_raw(r.summary)


def tr_result_title(r: CheckResult) -> str:
    return tr_or_raw(r.title)


def tr_result_category(r: CheckResult) -> str:
    return tr_or_raw(r.category)


def tr_result_advice(r: CheckResult) -> list[str]:
    if r.advice_keys and len(r.advice_keys) == len(r.advice):
        return [t(k) for k in r.advice_keys]
    return [tr_or_raw(a) for a in r.advice]


def tr_result_detail(r: CheckResult) -> str:
    if r.detail_key:
        return t(r.detail_key, **_resolve_args(r.summary_args))
    return tr_or_raw(r.detail)


def retranslate_result(r: CheckResult) -> None:
    """把已存的文案就地刷新成当前语言。

    为什么需要这个：`summary` / `detail` / `advice` 在检测时已按当时的语言
    翻好并保存。切换语言后，若只让渲染层临时翻译 `summary_key`，
    那些**没有 key 的字段**（拼接型 detail、problems 列表）会停留在旧语言，
    界面出现中英混排。这里在语言切换后统一刷新一遍，
    有 key 的用 key 重译，没 key 的保持原样（无法重译，属于已知限制）。
    """
    if r.summary_key:
        r.summary = t(r.summary_key, **_resolve_args(r.summary_args))
    if r.detail_key:
        r.detail = t(r.detail_key, **_resolve_args(r.summary_args))


SEV_KEYS = {
    "ok": "sev.ok",
    "info": "sev.info",
    "warn": "sev.warn",
    "critical": "sev.critical",
    "skip": "sev.skip",
}


def sev_label(sev: str | Severity) -> str:
    key = sev.value if isinstance(sev, Severity) else str(sev)
    return t(SEV_KEYS.get(key, "sev.skip"))


def risk_label(risk: str) -> str:
    return t(f"risk.{risk}")


def action_title(action_id: str) -> str:
    return t(f"action.{action_id}.title")


def action_desc(action_id: str) -> str:
    return t(f"action.{action_id}.desc")


def dns_vendor(ip: str) -> str:
    """DNS 归属名。未知 IP 返回"自定义/运营商"而不是 ⟦key⟧。"""
    from core.region import DNS_VENDOR_KEYS

    key = DNS_VENDOR_KEYS.get(ip)
    if key:
        return t(key)
    return t("dns.vendor.unknown")


def region_name(region_key: str) -> str:
    from core.region import get_profile

    return t(get_profile(region_key).name_key)


def tr_all(texts: Iterable[str]) -> list[str]:
    return [tr_or_raw(x) for x in texts]


__all__ = [
    "tr_or_raw", "tr", "tr_metric", "tr_result_summary", "tr_result_title",
    "tr_result_category", "tr_result_advice", "tr_result_detail",
    "sev_label", "risk_label", "action_title", "action_desc", "dns_vendor",
    "region_name", "tr_all", "MISSING_PREFIX",
]
