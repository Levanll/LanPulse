"""场景化诊断 Profile —— 让用户按"症状"而不是"技术名词"使用软件。

问题：普通用户不知道"我应该检测 DNS 还是网关"。他们只知道
"网络很慢""网页打不开""打游戏卡"。

做法：把"症状"映射到"跑哪些检测 + 关注哪些结论"。检测项本身不变
（保持独立可复用），只是选择与排序不同。

设计约束：
  * Profile 只影响**选择与展示**，不影响检测逻辑本身——同一个检测项
    在不同场景下产出的数据完全一致，避免"换个场景结论就变"的困惑。
  * 每个场景必须能只用**现成检测项**表达；不能表达的场景（如 Bufferbloat）
    单独标记为需要额外检测。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scenario:
    """一个使用场景。"""

    scenario_id: str
    #: i18n key：场景名称（用户看到的第一行）
    name_key: str
    #: i18n key：场景描述（帮用户确认"这就是我遇到的情况"）
    desc_key: str
    #: 该场景下要跑的检测项 check_id，按重要性排序
    checks: tuple[str, ...]
    #: 该场景最关心的结论优先级（用于根因排序加权）
    focus: tuple[str, ...] = ()
    #: 该场景下需要额外运行的检测（目前留空，供 v1.2 扩展）
    extra_probes: tuple[str, ...] = ()
    #: 图标字符（用于界面）
    icon: str = "◆"

    @property
    def check_ids(self) -> list[str]:
        return list(self.checks)


#: 场景定义。顺序即界面展示顺序。
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        scenario_id="slow",
        name_key="scenario.slow.name",
        desc_key="scenario.slow.desc",
        # 变慢通常是 DNS 解析慢、MTU 不对、或链路本身差
        checks=("connectivity", "dns_resolve", "dns_server", "mtu",
                "tcp", "gateway", "adapter"),
        focus=("dns_resolve", "mtu", "connectivity"),
        icon="⏱",
    ),
    Scenario(
        scenario_id="disconnect",
        name_key="scenario.disconnect.name",
        desc_key="scenario.disconnect.desc",
        # 掉线优先看链路稳定性：APIPA、网关、丢包、代理残留
        checks=("adapter", "ip", "gateway", "connectivity", "proxy", "tcp"),
        focus=("adapter", "ip", "gateway"),
        icon="⚡",
    ),
    Scenario(
        scenario_id="web",
        name_key="scenario.web.name",
        desc_key="scenario.web.desc",
        # 网页打不开：DNS 解析、HOSTS 劫持、代理、网页分层计时
        checks=("web_timing", "dns_resolve", "hosts", "proxy",
                "dns_server", "connectivity"),
        focus=("web_timing", "hosts", "dns_resolve"),
        icon="🌐",
    ),
    Scenario(
        scenario_id="gaming",
        name_key="scenario.gaming.name",
        desc_key="scenario.gaming.desc",
        # 游戏卡顿：延迟抖动、NAT、MTU、缓冲膨胀
        checks=("bufferbloat", "connectivity", "mtu", "gateway", "tcp"),
        focus=("bufferbloat", "gateway"),
        icon="🎮",
    ),
    Scenario(
        scenario_id="security",
        name_key="scenario.security.name",
        desc_key="scenario.security.desc",
        # 安全排查：HOSTS 劫持、DNS 污染、防火墙、代理
        checks=("hosts", "dns_hijack", "dns_server", "firewall",
                "proxy", "dns_resolve"),
        focus=("hosts", "dns_hijack", "firewall"),
        icon="🛡",
    ),
    Scenario(
        scenario_id="full",
        name_key="scenario.full.name",
        desc_key="scenario.full.desc",
        # 完整体检
        checks=("adapter", "ip", "gateway", "dns_server", "dns_resolve",
                "hosts", "proxy", "tcp", "mtu", "firewall", "connectivity",
                "web_timing", "dns_hijack", "bufferbloat"),
        focus=(),
        icon="◎",
    ),
)

_BY_ID = {s.scenario_id: s for s in SCENARIOS}


def get_scenario(scenario_id: str) -> Scenario:
    """取场景。未知 id 回退到完整体检（最保守，不漏检）。"""
    return _BY_ID.get(scenario_id) or _BY_ID["full"]


def all_scenarios() -> tuple[Scenario, ...]:
    return SCENARIOS


def checks_for(scenario_id: str) -> list[str]:
    return get_scenario(scenario_id).check_ids


__all__ = ["Scenario", "SCENARIOS", "get_scenario", "all_scenarios", "checks_for"]
