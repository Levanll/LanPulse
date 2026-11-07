"""根因分析引擎 —— 把 N 个检测项的证据合成少数几条结论。

为什么需要：用户看到"11 项里 3 项异常"并不知道根因是什么。
DNS 慢、MTU 不对、网关丢包这三件事可能指向同一个原因，也可能各自独立。
逐项罗列把"判断"这件事推给了用户——而普通用户不该被要求做判断。

设计：
  * **规则驱动**，不是启发式猜测。每条规则明确写出"看到什么证据 → 判定为什么"。
  * **证据链可追溯**：每条根因附带命中证据与"已排除的可能"，用户能核对。
  * **置信度分级**而非伪精确百分比：高 / 中 / 低。
  * **直接映射修复动作**：根因 → action_ids，与修复引擎闭环。

与检测项的关系：检测项负责"测量"，本模块负责"解释"。两者解耦——
新增检测项不会自动产生根因，需要显式加规则（这是刻意的，
避免臆造因果）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .models import CheckResult, DiagnosticReport, Severity


class Confidence:
    """置信度档位。用档位而非百分比，避免给出经不起追问的精确数字。"""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    LABELS_ZH = {HIGH: "高", MEDIUM: "中", LOW: "低"}
    RANK = {HIGH: 3, MEDIUM: 2, LOW: 1}

    @classmethod
    def label(cls, value: str) -> str:
        return cls.LABELS_ZH.get(value, "?")


@dataclass
class RootCause:
    """一条根因结论。"""

    rule_id: str
    #: i18n key：一句话结论
    title_key: str
    #: i18n key：影响说明（"这会导致什么现象"）
    impact_key: str
    #: i18n key：建议怎么做
    advice_key: str
    confidence: str = Confidence.MEDIUM
    #: 命中的证据（人类可读，来自各检测项的具体值）
    evidence: list[str] = field(default_factory=list)
    #: 已排除的可能（"为什么不是别的原因"）——这是可信度的关键
    excluded: list[str] = field(default_factory=list)
    #: 直接可执行的修复动作
    action_ids: list[str] = field(default_factory=list)
    #: 涉及哪些检测项
    check_ids: list[str] = field(default_factory=list)
    #: 排序权重（越大越靠前），由规则自己给
    weight: int = 50

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "title_key": self.title_key,
            "impact_key": self.impact_key,
            "advice_key": self.advice_key,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "excluded": list(self.excluded),
            "action_ids": list(self.action_ids),
            "check_ids": list(self.check_ids),
            "weight": self.weight,
        }


# --------------------------------------------------------------------------- #
# 规则
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Rule:
    """一条根因判定规则。

    `evaluate(results)` 返回 RootCause 或 None。None 表示本规则不成立。
    """

    rule_id: str
    #: 需要哪些检测项在场才评估（缺任一则跳过，不误判）
    requires: tuple[str, ...]
    evaluate: Callable[[dict[str, CheckResult]], RootCause | None]


def _by_id(results: list[CheckResult]) -> dict[str, CheckResult]:
    return {r.check_id: r for r in results}


def _sev(r: CheckResult | None) -> Severity:
    return r.severity if r is not None else Severity.SKIP


def _metric_value(r: CheckResult | None, contains: str) -> str:
    """从 metrics 里按名称模糊取一个值，用于证据展示。"""
    if r is None:
        return ""
    for m in r.metrics:
        if contains in m.name or contains in m.note:
            return m.value
    return ""


# ---- 规则 1：DNS 解析慢 ----------------------------------------------------
def _rule_dns_slow(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("dns_resolve")
    if r is None or r.severity not in (Severity.WARN, Severity.CRITICAL):
        return None
    # 只有 DNS 慢，而链路本身正常时，才是真正的 DNS 问题
    link_ok = _sev(results.get("connectivity")) is Severity.OK
    gateway_ok = _sev(results.get("gateway")) is Severity.OK
    evidence = [r.summary]
    if r.detail:
        evidence.append(r.detail.splitlines()[0])
    return RootCause(
        rule_id="dns_slow",
        title_key="rootcause.dns_slow.title",
        impact_key="rootcause.dns_slow.impact",
        advice_key="rootcause.dns_slow.advice",
        confidence=Confidence.HIGH if (link_ok and gateway_ok) else Confidence.MEDIUM,
        evidence=evidence,
        excluded=(
            ["链路与网关均正常，可排除物理链路问题"] if (link_ok and gateway_ok)
            else ["链路或网关同时存在异常，DNS 慢可能是其结果而非原因"]
        ),
        action_ids=["dns.flush_cache", "dns.set_public"],
        check_ids=["dns_resolve", "dns_server"],
        weight=90,
    )


# ---- 规则 2：HOSTS 劫持 ----------------------------------------------------
def _rule_hosts_hijack(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("hosts")
    if r is None or r.severity is not Severity.CRITICAL:
        return None
    return RootCause(
        rule_id="hosts_hijack",
        title_key="rootcause.hosts_hijack.title",
        impact_key="rootcause.hosts_hijack.impact",
        advice_key="rootcause.hosts_hijack.advice",
        confidence=Confidence.HIGH,
        evidence=[r.summary] + (r.advice[:2] if r.advice else []),
        excluded=["该问题与 DNS 服务器配置无关，改 DNS 不能解决"],
        action_ids=["hosts.clean_bad_lines"],
        check_ids=["hosts"],
        weight=100,      # 安全问题优先级最高
    )


# ---- 规则 3：DNS 污染（多服务器结果不一致）--------------------------------
def _rule_dns_hijack(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("dns_hijack")
    if r is None or r.severity not in (Severity.WARN, Severity.CRITICAL):
        return None
    return RootCause(
        rule_id="dns_hijack",
        title_key="rootcause.dns_hijack.title",
        impact_key="rootcause.dns_hijack.impact",
        advice_key="rootcause.dns_hijack.advice",
        confidence=Confidence.HIGH if r.severity is Severity.CRITICAL else Confidence.MEDIUM,
        evidence=[r.summary] + (r.detail.splitlines()[:3] if r.detail else []),
        excluded=["本机 HOSTS 已检查，排除本地静态映射导致的差异"],
        action_ids=["dns.set_public", "dns.flush_cache"],
        check_ids=["dns_hijack", "hosts"],
        weight=95,
    )


# ---- 规则 4：网关丢包 / 高延迟 ---------------------------------------------
def _rule_gateway_poor(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("gateway")
    if r is None or r.severity not in (Severity.WARN, Severity.CRITICAL):
        return None
    return RootCause(
        rule_id="gateway_poor",
        title_key="rootcause.gateway_poor.title",
        impact_key="rootcause.gateway_poor.impact",
        advice_key="rootcause.gateway_poor.advice",
        confidence=Confidence.HIGH,
        evidence=[r.summary] + (r.advice[:2] if r.advice else []),
        excluded=["问题发生在到网关这一段，与 DNS、外网、代理无关"],
        action_ids=[],
        check_ids=["gateway", "adapter"],
        weight=88,
    )


# ---- 规则 5：APIPA / DHCP 失败 ---------------------------------------------
def _rule_dhcp_failed(results: dict[str, CheckResult]) -> RootCause | None:
    ip = results.get("ip")
    adapter = results.get("adapter")
    hit = False
    evidence: list[str] = []
    for r in (ip, adapter):
        if r is None:
            continue
        for m in r.metrics:
            if "169.254" in str(m.value):
                hit = True
                evidence.append(f"{m.name}: {m.value}")
    if not hit:
        return None
    return RootCause(
        rule_id="dhcp_failed",
        title_key="rootcause.dhcp_failed.title",
        impact_key="rootcause.dhcp_failed.impact",
        advice_key="rootcause.dhcp_failed.advice",
        confidence=Confidence.HIGH,
        evidence=evidence[:3],
        excluded=["这不是 DNS 或 MTU 问题：地址本身就是无效的"],
        action_ids=["adapter.renew_dhcp"],
        check_ids=["ip", "adapter"],
        weight=98,       # 完全上不了网，优先级极高
    )


# ---- 规则 6：MTU 黑洞风险 --------------------------------------------------
def _rule_mtu_mismatch(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("mtu")
    if r is None or r.severity not in (Severity.WARN, Severity.CRITICAL):
        return None
    return RootCause(
        rule_id="mtu_mismatch",
        title_key="rootcause.mtu_mismatch.title",
        impact_key="rootcause.mtu_mismatch.impact",
        advice_key="rootcause.mtu_mismatch.advice",
        confidence=Confidence.MEDIUM,
        evidence=[r.summary],
        excluded=["小包能通、大包被丢是 MTU 问题的典型特征，与 DNS 无关"],
        action_ids=r.action_ids or ["mtu.optimize"],
        check_ids=["mtu"],
        weight=80,
    )


# ---- 规则 7：残留代理 ------------------------------------------------------
def _rule_proxy_residual(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("proxy")
    if r is None or r.severity is not Severity.CRITICAL:
        return None
    return RootCause(
        rule_id="proxy_residual",
        title_key="rootcause.proxy_residual.title",
        impact_key="rootcause.proxy_residual.impact",
        advice_key="rootcause.proxy_residual.advice",
        confidence=Confidence.HIGH,
        evidence=[r.summary],
        excluded=["IP 层与网关通常正常——这能解释「能 ping 通但网页打不开」"],
        action_ids=["proxy.reset"],
        check_ids=["proxy"],
        weight=92,
    )


# ---- 规则 8：防火墙全关（安全但不影响上网）--------------------------------
def _rule_firewall_off(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("firewall")
    if r is None or r.severity not in (Severity.WARN, Severity.CRITICAL):
        return None
    return RootCause(
        rule_id="firewall_off",
        title_key="rootcause.firewall_off.title",
        impact_key="rootcause.firewall_off.impact",
        advice_key="rootcause.firewall_off.advice",
        confidence=Confidence.HIGH,
        evidence=[r.summary],
        excluded=["这是安全风险，不是网络故障——不会导致网页打不开"],
        action_ids=["firewall.ensure_enabled"],
        check_ids=["firewall"],
        weight=60,       # 安全问题但不影响当前可用性，排在网络故障之后
    )


# ---- 规则 9：缓冲膨胀（游戏/语音卡顿）-------------------------------------
def _rule_bufferbloat(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("bufferbloat")
    if r is None or r.severity not in (Severity.WARN, Severity.CRITICAL):
        return None
    return RootCause(
        rule_id="bufferbloat",
        title_key="rootcause.bufferbloat.title",
        impact_key="rootcause.bufferbloat.impact",
        advice_key="rootcause.bufferbloat.advice",
        confidence=Confidence.HIGH,
        evidence=[r.summary] + (r.metrics[:2] and [f"{m.name}: {m.value}" for m in r.metrics[:2]] or []),
        excluded=["空闲时延迟正常、有负载时才飙高，是缓冲膨胀的典型特征"],
        action_ids=["tcp.autotuning"],
        check_ids=["bufferbloat"],
        weight=75,
    )


# ---- 规则 10：网页分层断层 ------------------------------------------------
def _rule_web_break(results: dict[str, CheckResult]) -> RootCause | None:
    r = results.get("web_timing")
    if r is None or r.severity not in (Severity.WARN, Severity.CRITICAL):
        return None
    return RootCause(
        rule_id="web_break",
        title_key="rootcause.web_break.title",
        impact_key="rootcause.web_break.impact",
        advice_key="rootcause.web_break.advice",
        confidence=Confidence.HIGH,
        evidence=[r.summary] + (r.detail.splitlines()[:3] if r.detail else []),
        excluded=["分层计时已定位到具体环节，不必再逐项排查"],
        action_ids=r.action_ids or [],
        check_ids=["web_timing"],
        weight=85,
    )


RULES: tuple[Rule, ...] = (
    Rule("dhcp_failed", ("ip", "adapter"), _rule_dhcp_failed),
    Rule("hosts_hijack", ("hosts",), _rule_hosts_hijack),
    Rule("dns_hijack", ("dns_hijack", "hosts"), _rule_dns_hijack),
    Rule("proxy_residual", ("proxy",), _rule_proxy_residual),
    Rule("gateway_poor", ("gateway",), _rule_gateway_poor),
    Rule("dns_slow", ("dns_resolve", "connectivity", "gateway"), _rule_dns_slow),
    Rule("web_break", ("web_timing",), _rule_web_break),
    Rule("mtu_mismatch", ("mtu",), _rule_mtu_mismatch),
    Rule("bufferbloat", ("bufferbloat",), _rule_bufferbloat),
    Rule("firewall_off", ("firewall",), _rule_firewall_off),
)


# --------------------------------------------------------------------------- #
# 分析入口
# --------------------------------------------------------------------------- #
@dataclass
class Analysis:
    """一次根因分析的产出。"""

    root_causes: list[RootCause] = field(default_factory=list)
    #: 已被规则消费掉的检测项（剩下的异常项属于"孤立异常"）
    explained: set[str] = field(default_factory=set)
    #: 没有归入任何根因的异常检测项（仍要展示，但不臆测原因）
    unexplained: list[CheckResult] = field(default_factory=list)

    def actions(self) -> list[str]:
        """汇总所有根因建议的动作，去重保序。"""
        seen: list[str] = []
        for rc in self.root_causes:
            for a in rc.action_ids:
                if a not in seen:
                    seen.append(a)
        return seen

    def to_dict(self) -> dict:
        return {
            "root_causes": [rc.to_dict() for rc in self.root_causes],
            "explained": sorted(self.explained),
            "unexplained": [
                {"check_id": r.check_id, "severity": r.severity.value,
                 "summary": r.summary}
                for r in self.unexplained
            ],
        }


def analyze(results: list[CheckResult]) -> Analysis:
    """对一次体检结果做根因分析。

    规则按定义顺序评估；同一检测项可被多条规则引用（例如 hosts 同时
    服务于 hosts_hijack 与 dns_hijack 的排除证据），但"已解释"只记一次。
    """
    idx = _by_id(results)
    causes: list[RootCause] = []
    explained: set[str] = set()

    for rule in RULES:
        if not all(k in idx for k in rule.requires):
            continue
        try:
            rc = rule.evaluate(idx)
        except (KeyError, TypeError, ValueError, AttributeError):
            # 规则是纯函数，异常说明规则本身写错了；跳过它而不是让整轮分析失败
            continue
        if rc is None:
            continue
        causes.append(rc)
        explained.update(rc.check_ids)

    # 按权重排序；同权重时高置信度优先
    causes.sort(key=lambda c: (c.weight, Confidence.RANK.get(c.confidence, 0)),
                reverse=True)

    unexplained = [
        r for r in results
        if r.severity in (Severity.WARN, Severity.CRITICAL)
        and r.check_id not in explained
    ]
    return Analysis(root_causes=causes, explained=explained, unexplained=unexplained)


def health_score(results: list[CheckResult], *, exempt: set[str] | None = None) -> int:
    """0-100 健康分。扣分制，缺口（SKIP）不扣分。

    借鉴参考项目的扣分规则，但改为按严重度分级扣分而非固定值，
    避免"3 个警告"和"3 个错误"得分相同。
    环境相关检测项（IPv6/缓冲膨胀等）可豁免，因为它们常因环境不可用而非故障。
    """
    exempt = exempt or set()
    score = 100
    for r in results:
        if r.check_id in exempt:
            continue
        if r.severity is Severity.CRITICAL:
            score -= 30
        elif r.severity is Severity.WARN:
            score -= 15
        elif r.severity is Severity.INFO:
            score -= 3
        # OK / SKIP 不扣分：SKIP 是环境缺测，不该记过
    return max(0, min(100, score))


def grade(score: int) -> str:
    """A/B/C/D/F 等级。比单纯分数更易理解。"""
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


__all__ = [
    "Confidence", "RootCause", "Rule", "RULES", "Analysis",
    "analyze", "health_score", "grade",
]
