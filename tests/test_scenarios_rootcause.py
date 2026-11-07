"""场景与根因分析的单元测试。

锁住三件事：
  1. 场景定义完整，检测项 id 都真实存在（防止改名后场景悄悄空掉）
  2. 根因规则在对应证据下确实触发，且映射到有效动作
  3. 健康分与等级计算符合预期（缺口不扣分、豁免生效）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.models import CheckResult, Metric, Severity  # noqa: E402
from core.rootcause import analyze, grade, health_score  # noqa: E402
from core.scenarios import SCENARIOS, all_scenarios, checks_for, get_scenario  # noqa: E402


def _r(check_id: str, sev: Severity, summary: str = "x",
       metrics: list[Metric] | None = None,
       action_ids: list[str] | None = None) -> CheckResult:
    return CheckResult(
        check_id=check_id, title=f"check.{check_id}.title",
        category="c", severity=sev, summary=summary,
        metrics=metrics or [], action_ids=action_ids or [],
    )


# --------------------------------------------------------------------------- #
class TestScenarios:
    def test_all_scenarios_non_empty(self):
        assert len(all_scenarios()) >= 5

    def test_full_scenario_covers_every_check(self):
        """完整体检必须包含全部已注册检测项，否则会出现"漏检"困惑。"""
        from core.registry import load_checks

        registered = {c.check_id for c in load_checks()}
        full = set(checks_for("full"))
        # 允许 full 只包含"用户可感知"的项，但不能缺注册项
        missing = registered - full
        assert not missing, f"完整体检漏了：{sorted(missing)}"

    def test_scenario_check_ids_resolve(self):
        """每个场景引用的 check_id 必须能在 registry 里找到。"""
        from core.registry import load_checks

        registered = {c.check_id for c in load_checks()}
        for sc in SCENARIOS:
            unknown = [c for c in sc.checks if c not in registered]
            assert not unknown, f"{sc.scenario_id} 引用了不存在检测项：{unknown}"

    def test_unknown_scenario_falls_back_to_full(self):
        assert get_scenario("nonexistent").scenario_id == "full"

    def test_scenario_ids_unique(self):
        ids = [s.scenario_id for s in SCENARIOS]
        assert len(ids) == len(set(ids))

    def test_each_scenario_has_targeted_subset(self):
        """除完整体检外，场景不该等同于全量（否则场景化没意义）。"""
        full_len = len(checks_for("full"))
        for sc in SCENARIOS:
            if sc.scenario_id == "full":
                continue
            assert len(sc.checks) < full_len, f"{sc.scenario_id} 与完整体检无区别"


# --------------------------------------------------------------------------- #
class TestRootCause:
    def test_dhcp_failure_detected(self):
        results = [
            _r("ip", Severity.CRITICAL, "拿到 169.254.13.83",
               metrics=[Metric("metric.ipv4", "169.254.13.83")]),
            _r("adapter", Severity.WARN, "链路异常"),
        ]
        a = analyze(results)
        ids = [rc.rule_id for rc in a.root_causes]
        assert "dhcp_failed" in ids
        rc = next(x for x in a.root_causes if x.rule_id == "dhcp_failed")
        assert rc.action_ids == ["adapter.renew_dhcp"]
        assert rc.confidence == "high"

    def test_hosts_hijack_detected(self):
        a = analyze([_r("hosts", Severity.CRITICAL, "2 条劫持记录")])
        assert [x.rule_id for x in a.root_causes] == ["hosts_hijack"]
        assert a.root_causes[0].action_ids == ["hosts.clean_bad_lines"]

    def test_proxy_residual_detected(self):
        a = analyze([_r("proxy", Severity.CRITICAL, "死端口代理")])
        assert [x.rule_id for x in a.root_causes] == ["proxy_residual"]

    def test_dns_slow_needs_link_ok_for_high_confidence(self):
        link_ok = [
            _r("dns_resolve", Severity.WARN, "解析 420ms"),
            _r("connectivity", Severity.OK, "外网通"),
            _r("gateway", Severity.OK, "网关正常"),
        ]
        rc = next(x for x in analyze(link_ok).root_causes if x.rule_id == "dns_slow")
        assert rc.confidence == "high"

        link_bad = [
            _r("dns_resolve", Severity.WARN, "解析 420ms"),
            _r("connectivity", Severity.CRITICAL, "外网断"),
            _r("gateway", Severity.WARN, "网关丢包"),
        ]
        rc2 = next(x for x in analyze(link_bad).root_causes if x.rule_id == "dns_slow")
        # 链路也不好的时候不能把 DNS 说成根因
        assert rc2.confidence == "medium"

    def test_firewall_off_is_not_network_fault(self):
        """防火墙关闭是安全问题，不能混进"网页打不开"的根因里。"""
        a = analyze([_r("firewall", Severity.WARN, "三个 profile 全关")])
        rc = a.root_causes[0]
        assert rc.rule_id == "firewall_off"
        assert "不会导致" in rc.excluded[0] or "not" in rc.excluded[0].lower()

    def test_no_false_positive_when_all_ok(self):
        results = [
            _r("gateway", Severity.OK), _r("dns_resolve", Severity.OK),
            _r("hosts", Severity.OK), _r("proxy", Severity.OK),
        ]
        assert analyze(results).root_causes == []

    def test_unexplained_collects_uncovered_anomalies(self):
        results = [
            _r("gateway", Severity.OK),
            _r("dns_resolve", Severity.OK),
            _r("connectivity", Severity.OK),
            _r("tcp", Severity.WARN, "协议栈参数异常"),
        ]
        a = analyze(results)
        assert [r.check_id for r in a.unexplained] == ["tcp"]

    def test_rule_ordering_by_weight(self):
        """安全问题（HOSTS 劫持）应排在体验问题（缓冲膨胀）之前。"""
        results = [
            _r("hosts", Severity.CRITICAL, "劫持"),
            _r("bufferbloat", Severity.WARN, "F 级"),
        ]
        ids = [rc.rule_id for rc in analyze(results).root_causes]
        assert ids.index("hosts_hijack") < ids.index("bufferbloat")

    def test_analysis_actions_deduped(self):
        results = [
            _r("hosts", Severity.CRITICAL, "劫持"),
            _r("dns_hijack", Severity.CRITICAL, "污染"),
        ]
        acts = analyze(results).actions()
        assert len(acts) == len(set(acts))


# --------------------------------------------------------------------------- #
class TestHealthScore:
    def test_all_ok_is_100(self):
        assert health_score([_r("a", Severity.OK)]) == 100

    def test_skip_not_penalized(self):
        """环境缺测不该扣分——否则离线机器永远拿不到满分。"""
        assert health_score([_r("a", Severity.OK), _r("b", Severity.SKIP)]) == 100

    def test_critical_costs_more_than_warn(self):
        crit = health_score([_r("a", Severity.CRITICAL)])
        warn = health_score([_r("a", Severity.WARN)])
        assert crit < warn < 100

    def test_exempt_items_not_counted(self):
        results = [_r("a", Severity.OK), _r("ipv6", Severity.WARN)]
        assert health_score(results, exempt={"ipv6"}) == 100

    def test_score_clamped(self):
        many = [_r(f"c{i}", Severity.CRITICAL) for i in range(10)]
        assert health_score(many) == 0

    @pytest.mark.parametrize("score,expected", [
        (95, "A"), (90, "A"), (80, "B"), (75, "B"),
        (65, "C"), (60, "C"), (45, "D"), (40, "D"), (20, "F"),
    ])
    def test_grade_boundaries(self, score, expected):
        assert grade(score) == expected
