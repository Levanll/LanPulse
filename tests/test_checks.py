"""检测单元的单元测试。

这些测试锁的是「检测项的记账口径」，不是网络结果本身：不联网、不碰系统配置，
用假的 ctx / 假的探测原语，验证三项契约：

  1. 单项预算只覆盖本检测项自己的探测，不含共享的一次性准备（区域识别）；
  2. 预算真的耗尽时必须报 SKIP 而不是给出虚假结论；
  3. 结论里的数值来自实测，不是硬编码。

第 1 条对应一个真实缺陷：区域识别在 8.8.8.8 / 9.9.9.9 不可达的网络上要跑 12s+，
如果把它算进 connectivity 的 10s 预算，首次体检必然在第一个 TCP 探测前就超时，
于是一个本来正常的网络被报成「结论不完整」。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.checks import _netprobe  # noqa: E402
from core.checks.connectivity_check import ConnectivityCheck  # noqa: E402
from core.models import Severity  # noqa: E402
from core import region as R  # noqa: E402


# --------------------------------------------------------------------------- #
# 测试替身
# --------------------------------------------------------------------------- #
class _SlowProfileCtx:
    """模拟"首次取 profile 很慢"的上下文，其余行为与真实 ctx 一致。"""

    def __init__(self, prepare_seconds: float = 0.0, profile_key: str = R.REGION_CN):
        self._prepare = prepare_seconds
        self._profile = R.get_profile(profile_key)
        self.allow_probe = True
        self.region_key = profile_key
        self.hostname = "TEST-PC"
        self.elevated = False
        self.adapters: list = []

    @property
    def profile(self):
        if self._prepare:
            time.sleep(self._prepare)
        return self._profile


def _ok_ping(target, **kwargs):
    return _netprobe.PingStats(
        target=target, sent=2, received=2, loss_pct=0,
        rtt_avg_ms=6.0, rtt_min_ms=6.0, rtt_max_ms=6.0,
    )


def _ok_tcp(host, port, **kwargs):
    return _netprobe.TcpProbe(host=host, port=port, ok=True, connect_ms=40.0)


def _ok_resolve(name, **kwargs):
    return _netprobe.ResolveProbe(
        name=name, ok=True, ms=12.0, addresses=["192.0.2.42"],
    )


@pytest.fixture
def stub_probes(monkeypatch):
    """把三项探测全部替换为瞬时成功的假实现。"""
    monkeypatch.setattr(_netprobe, "ping", _ok_ping)
    monkeypatch.setattr(_netprobe, "tcp_connect", _ok_tcp)
    monkeypatch.setattr(_netprobe, "resolve_timed", _ok_resolve)


# --------------------------------------------------------------------------- #
# 1. 共享准备时间不得计入本项预算
# --------------------------------------------------------------------------- #
class TestBudgetAccounting:
    def test_slow_profile_does_not_consume_connectivity_budget(
            self, stub_probes, monkeypatch):
        """区域识别再慢，也不能让 connectivity 判超时。

        这是回归测试，参数刻意构造成「准备耗时 > 本项预算」——正是线上那次
        12s 区域识别吃掉 10s 预算的形态。把 TOTAL_BUDGET 缩小只是为了让测试
        跑得快，两者的大小关系才是被验证的东西。
        """
        import core.checks.connectivity_check as C

        monkeypatch.setattr(C, "TOTAL_BUDGET", 0.3)
        ctx = _SlowProfileCtx(prepare_seconds=0.5)  # 准备耗时超出预算
        result = ConnectivityCheck().run(ctx)

        assert result.severity is not Severity.SKIP
        assert result.evidence["tcp"], "区域识别耗时应被排除，TCP 探测必须跑得到"
        assert len(result.evidence["tcp"]) == 2

    def test_budget_still_applies_to_own_probes(self, stub_probes, monkeypatch):
        """预算没有形同虚设：本项自己的 TCP 探测慢到超预算时，仍需报 SKIP。

        两个约束必须同时成立——排除共享准备时间，不等于取消预算。
        """
        import core.checks.connectivity_check as C

        monkeypatch.setattr(C, "TOTAL_BUDGET", 0.0)

        def _slow_tcp(host, port, **kwargs):
            time.sleep(0.05)
            return _ok_tcp(host, port)

        monkeypatch.setattr(_netprobe, "tcp_connect", _slow_tcp)
        result = ConnectivityCheck().run(_SlowProfileCtx(prepare_seconds=0.0))

        assert result.severity is Severity.SKIP
        assert not result.evidence["tcp"]

    def test_elapsed_excludes_profile_preparation(self, stub_probes):
        """报告里的 elapsed_s 是用户可读的耗时，也必须是本项真实探测耗时。"""
        result = ConnectivityCheck().run(_SlowProfileCtx(prepare_seconds=0.4))
        assert result.evidence["elapsed_s"] < 0.4


# --------------------------------------------------------------------------- #
# 2. 结论来自实测
# --------------------------------------------------------------------------- #
class TestConnectivityVerdicts:
    def test_good_network_reports_ok(self, stub_probes):
        result = ConnectivityCheck().run(_SlowProfileCtx(profile_key=R.REGION_CN))
        assert result.severity is Severity.OK
        assert result.summary_key == "check.connectivity.summary_ok"

    def test_all_tcp_fail_is_critical(self, stub_probes, monkeypatch):
        def _fail(host, port, **kwargs):
            return _netprobe.TcpProbe(host=host, port=port, ok=False, error="refused")

        monkeypatch.setattr(_netprobe, "tcp_connect", _fail)
        result = ConnectivityCheck().run(_SlowProfileCtx())
        assert result.severity is Severity.CRITICAL

    def test_unresolvable_dns_is_at_least_warn(self, stub_probes, monkeypatch):
        def _fail(name, **kwargs):
            return _netprobe.ResolveProbe(name=name, ok=False, error="no address")

        monkeypatch.setattr(_netprobe, "resolve_timed", _fail)
        result = ConnectivityCheck().run(_SlowProfileCtx())
        assert result.severity.rank >= Severity.WARN.rank
        # 解析不了要给出可执行建议，而不是只报错
        assert "dns.flush_cache" in result.action_ids
