"""跨区域自适应的单元测试。

核心命题：探测目标与判定阈值必须随区域变化，否则软件只能在单一地区可用。
这些测试锁住"区域剖面确实不同"以及"未知区域有安全回退"两件事。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.region as R  # noqa: E402


class TestProfiles:
    def test_all_regions_defined(self):
        for key in R.ALL_REGIONS:
            assert key in R.PROFILES

    def test_profiles_differ_in_targets(self):
        """三个区域的探测目标不能相同——否则等于没做区域适配。"""
        seen = set()
        for key in R.ALL_REGIONS:
            p = R.PROFILES[key]
            seen.add((p.resolve_domains, p.ping_targets, p.mtu_target))
        assert len(seen) == len(R.ALL_REGIONS)

    def test_cn_does_not_use_overseas_anchors_only(self):
        cn = R.PROFILES[R.REGION_CN]
        assert any(ip.startswith("223.") or ip.startswith("119.")
                   for ip, _ in cn.ping_targets)

    def test_global_uses_anycast_anchors(self):
        g = R.PROFILES[R.REGION_GLOBAL]
        assert any(ip in ("1.1.1.1", "8.8.8.8", "9.9.9.9") for ip, _ in g.ping_targets)

    def test_every_profile_has_dhcp_plan(self):
        """每个区域都必须提供"恢复自动获取"这条退路。"""
        for key in R.ALL_REGIONS:
            plans = R.PROFILES[key].dns_plans
            assert any(p.is_dhcp for p in plans), f"{key} 缺少 DHCP 方案"

    def test_dns_plan_servers_are_valid_ipv4(self):
        from core.platform_win import is_valid_ipv4

        for key in R.ALL_REGIONS:
            for plan in R.PROFILES[key].dns_plans:
                for srv in plan.servers:
                    assert is_valid_ipv4(srv), f"{key}/{plan.plan_id} 非法 IP: {srv}"

    def test_no_duplicate_plan_ids_within_profile(self):
        for key in R.ALL_REGIONS:
            ids = [p.plan_id for p in R.PROFILES[key].dns_plans]
            assert len(ids) == len(set(ids)), f"{key} 存在重复 plan_id"

    def test_thresholds_are_ordered(self):
        for key in R.ALL_REGIONS:
            p = R.PROFILES[key]
            assert p.resolve_excellent_ms < p.resolve_normal_ms < p.resolve_slow_ms
            assert p.rtt_excellent_ms < p.rtt_normal_ms < p.rtt_slow_ms

    def test_global_tolerates_higher_latency_than_cn(self):
        """跨境的基线延迟更高，阈值必须放宽，否则正常网络会被误判。"""
        cn = R.PROFILES[R.REGION_CN]
        g = R.PROFILES[R.REGION_GLOBAL]
        assert g.rtt_normal_ms > cn.rtt_normal_ms
        assert g.resolve_normal_ms > cn.resolve_normal_ms


class TestGetProfile:
    def test_unknown_region_falls_back_global(self):
        p = R.get_profile("mars")
        assert p.key == R.REGION_GLOBAL

    def test_known_region_returns_itself(self):
        for key in R.ALL_REGIONS:
            assert R.get_profile(key).key == key


class TestVendorTable:
    def test_covers_china_dns(self):
        for ip in ("223.5.5.5", "119.29.29.29", "114.114.114.114"):
            assert ip in R.DNS_VENDOR_KEYS

    def test_covers_international_dns(self):
        for ip in ("1.1.1.1", "8.8.8.8", "9.9.9.9", "208.67.222.222"):
            assert ip in R.DNS_VENDOR_KEYS

    def test_all_values_are_strings(self):
        for k, v in R.DNS_VENDOR_KEYS.items():
            assert isinstance(v, str) and v, k


class TestRegionDetection:
    def test_timezone_key_is_readable(self):
        """中文系统上 StandardName 是 "@tzres.dll,-572" 这种资源串，不可用。

        必须读 TimeZoneKeyName（如 "China Standard Time"），
        否则时区推断永远失败，只能退化到语言判断。
        """
        tz = R._system_timezone()
        if tz:
            assert not tz.startswith("@"), f"时区读到资源串: {tz}"
            assert "tzres.dll" not in tz, f"时区读到资源串: {tz}"

    def test_detect_without_probe_returns_valid_region(self):
        key, evidence = R.detect_region(probe=False)
        assert key in R.ALL_REGIONS
        assert "reason" in evidence

    def test_probe_disabled_recorded_in_evidence(self):
        _, evidence = R.detect_region(probe=False)
        assert evidence["probe_enabled"] is False


class TestNetworkEnvironment:
    def _adapter(self, **kw):
        from core.platform_win import AdapterInfo

        base = dict(name="eth0", status="Up", gateway="192.168.1.1", ipv4=["192.168.1.5"])
        base.update(kw)
        return AdapterInfo(**base)

    def test_vpn_detected_when_virtual_up_with_gateway(self):
        adapters = [self._adapter(is_virtual=True)]
        env = R.detect_network_environment(adapters, probe=False)
        assert env.vpn_active is True
        assert "env.vpn_active" in env.notes

    def test_no_vpn_for_physical_adapter(self):
        env = R.detect_network_environment([self._adapter()], probe=False)
        assert env.vpn_active is False

    def test_proxy_flag_propagates(self):
        env = R.detect_network_environment([self._adapter()], proxy_enabled=True, probe=False)
        assert env.behind_proxy is True
        assert "env.proxy" in env.notes

    def test_ipv6_only_detection(self):
        adapters = [
            self._adapter(
                ipv4=[],
                ipv6=["2408:8207:1234::1"],
                gateway="",
            )
        ]
        env = R.detect_network_environment(adapters, probe=False)
        assert env.ipv6_only is True
