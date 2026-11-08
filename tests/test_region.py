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
        """非大陆区域必须至少有一个全球 anycast 锚点可用于连通性基准。"""
        g = R.PROFILES[R.REGION_NA]
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
        na = R.PROFILES[R.REGION_NA]
        assert na.rtt_normal_ms > cn.rtt_normal_ms
        assert na.resolve_normal_ms > cn.resolve_normal_ms

    def test_other_is_most_tolerant_profile(self):
        """other 是兜底剖面，阈值必须是所有区域里最宽松的。

        它承接"识别不出来"的所有网络。若它的阈值比某个真实区域更严，
        就无法识别区域的用户会被误报成网络故障——这比判错区域更糟。
        """
        other = R.PROFILES[R.REGION_OTHER]
        for key in R.ALL_REGIONS:
            p = R.PROFILES[key]
            assert other.rtt_normal_ms >= p.rtt_normal_ms, f"{key} 的 RTT 阈值比 other 更宽松"
            assert other.resolve_normal_ms >= p.resolve_normal_ms, \
                f"{key} 的解析阈值比 other 更宽松"


class TestRegionGranularity:
    """11 套剖面的结构约束。

    v1.2.0 把原来的 cn / global / apac 三套粗粒度剖面拆成按国家/地区细分。
    这些测试锁住"拆分后没有退化"：每个区域确实不同、没有重复、旧值能兼容。
    """

    def test_every_region_has_a_profile(self):
        """ALL_REGIONS 与 PROFILES 必须完全对应，不多不少。

        这里刻意不写死区域数量：v1.2.0 加了澳门就得改一次测试，而数量本身
        不是契约，"每一个声明的区域都有剖面、每一个剖面都被声明"才是。
        """
        assert set(R.ALL_REGIONS) == set(R.PROFILES)
        assert len(R.ALL_REGIONS) >= 3, "至少要有中国大陆 + 一个海外剖面 + other"

    def test_greater_china_regions_present(self):
        """港澳台必须各自独立。

        它们共用 Windows 的 China Standard Time，若合并成一个剖面，
        三地用户会被当成同一个网络环境，探测目标与阈值都不再适用。
        """
        for key in (R.REGION_CN, R.REGION_HK, R.REGION_MO, R.REGION_TW):
            assert key in R.ALL_REGIONS, f"{key} 缺失"
            assert R.get_profile(key).key == key

    def test_no_duplicate_profiles(self):
        """不能有两个区域共用完全相同的探测目标——那等于没拆分。"""
        seen = {}
        for key in R.ALL_REGIONS:
            p = R.PROFILES[key]
            sig = (p.resolve_domains, p.ping_targets)
            assert sig not in seen, f"{key} 与 {seen[sig]} 的探测目标完全相同"
            seen[sig] = key

    def test_every_region_has_distinct_name_key(self):
        keys = [R.PROFILES[k].name_key for k in R.ALL_REGIONS]
        assert len(set(keys)) == len(keys)

    def test_legacy_names_normalize(self):
        """v1.1.0 存的 global / apac 必须能映射到新值，不能变成空。"""
        assert R.normalize_region("global") in R.ALL_REGIONS
        assert R.normalize_region("apac") in R.ALL_REGIONS
        assert R.normalize_region("apac") == R.REGION_OTHER

    def test_unknown_region_normalizes_to_other(self):
        assert R.normalize_region("mars") == R.REGION_OTHER
        assert R.normalize_region("") == R.REGION_OTHER
        assert R.normalize_region("auto") == R.REGION_AUTO

    def test_get_profile_accepts_legacy_names(self):
        """旧配置文件里的 global 不能让 get_profile 抛异常或返回 None。"""
        assert R.get_profile("global").key == R.REGION_OTHER
        assert R.get_profile("apac").key == R.REGION_OTHER


class TestGetProfile:
    def test_unknown_region_falls_back_other(self):
        p = R.get_profile("mars")
        assert p.key == R.REGION_OTHER

    def test_known_region_returns_itself(self):
        for key in R.ALL_REGIONS:
            assert R.get_profile(key).key == key

    def test_each_region_resolves_to_itself(self):
        """逐区域验证，避免 ALL_REGIONS 与 PROFILES 的键漂移。"""
        for key in R.ALL_REGIONS:
            assert R.get_profile(key).key == key
            assert R.region_display_key(key) == f"region.{key}"


class TestLocaleRegion:
    """语言 → 区域的映射。

    这是港澳台唯一的可靠区分手段：三地在 Windows 上都用
    China Standard Time，时区键完全一样，只有系统地区码能把它们分开。
    映射错了，三地用户就会拿到彼此的网络阈值。
    """

    def _patch_locale(self, monkeypatch, loc):
        import locale

        monkeypatch.setattr(locale, "getdefaultlocale", lambda *a, **k: (loc, None))
        monkeypatch.delenv("LANG", raising=False)

    def test_greater_china_locales_split_apart(self, monkeypatch):
        cases = {
            "zh_CN": R.REGION_CN,
            "zh_SG": R.REGION_CN,
            "zh_HK": R.REGION_HK,
            "zh_MO": R.REGION_MO,
            "zh_TW": R.REGION_TW,
        }
        for loc, expected in cases.items():
            self._patch_locale(monkeypatch, loc)
            assert R._locale_region() == expected, f"{loc} 应映射到 {expected}"

    def test_macau_is_not_folded_into_hong_kong(self, monkeypatch):
        """澳门曾经与香港合并在同一个分支里，这条测试锁住它们必须分开。"""
        self._patch_locale(monkeypatch, "zh_MO")
        assert R._locale_region() == R.REGION_MO
        assert R._locale_region() != R.REGION_HK

    def test_other_locales(self, monkeypatch):
        cases = {
            "ja_JP": R.REGION_JP,
            "ko_KR": R.REGION_KR,
            "th_TH": R.REGION_SG,
            "hi_IN": R.REGION_IN,
            "en_AU": R.REGION_AU,
            "en_GB": R.REGION_EU,
            "en_US": R.REGION_NA,
            "de_DE": R.REGION_EU,
            "sw_KE": R.REGION_OTHER,
        }
        for loc, expected in cases.items():
            self._patch_locale(monkeypatch, loc)
            assert R._locale_region() == expected, f"{loc} 应映射到 {expected}"


class TestMacauProfile:
    """澳门剖面的具体约束。"""

    def test_macau_profile_complete(self):
        p = R.PROFILES[R.REGION_MO]
        assert len(p.resolve_domains) >= 2
        assert len(p.dns_plans) >= 2
        assert any(plan.is_dhcp for plan in p.dns_plans), "澳门剖面必须有 DHCP 回退"
        assert p.resolve_excellent_ms < p.resolve_normal_ms < p.resolve_slow_ms
        assert p.rtt_excellent_ms < p.rtt_normal_ms < p.rtt_slow_ms

    def test_macau_dns_servers_are_macau_addresses(self):
        """本地方案必须真的是澳门地址段，不能拿香港或大陆的充数。

        澳门只有 CTM 与 MTel 两家固网运营商，地址集中在 202.175 / 182.93 /
        205.198。用别处的地址会让「本地 DNS」名不副实。
        """
        from core.platform_win import is_valid_ipv4

        p = R.PROFILES[R.REGION_MO]
        local = [pl for pl in p.dns_plans if pl.plan_id == "mo_local"]
        assert local, "缺少 mo_local 方案"
        for srv in local[0].servers:
            assert is_valid_ipv4(srv), f"非法 IP: {srv}"
            assert srv.startswith(("202.175.", "182.93.", "205.198.")), \
                f"{srv} 不属于澳门运营商地址段"

    def test_macau_dns_is_in_vendor_table(self):
        """本地 DNS 必须能被界面识别出归属，否则会显示「自定义/运营商」。"""
        p = R.PROFILES[R.REGION_MO]
        local = [pl for pl in p.dns_plans if pl.plan_id == "mo_local"][0]
        for srv in local.servers:
            assert p.vendor_key(srv) == "dns.vendor.mo", \
                f"{srv} 未登记为澳门 DNS"

    def test_macau_timezone_alias(self):
        """IANA 的 Asia/Macau 与 Asia/Macao 都必须能识别。"""
        for tz in ("Asia/Macau", "Asia/Macao", "Macao"):
            assert R._TZ_HINTS.get(tz) == R.REGION_MO, f"{tz} 未映射到澳门"


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


class TestAnchorProbing:
    """锚点探测的成本契约。

    区域识别是每次冷启动都要付一次的全局准备。它曾经耗时 12.5s：min() 把生成器
    完整消费导致三个全球锚点全测（8.8.8.8 / 9.9.9.9 在国内被阻断，各付满超时），
    外加每个端口盲重试。这些测试锁住"短路"与"不重复尝试"，防止改回去。
    """

    def test_first_rtt_stops_at_first_usable_anchor(self, monkeypatch):
        """取到第一个可用锚点即返回，不得继续探测后面的。"""
        probed: list[str] = []

        def fake_rtt(host, **kwargs):
            probed.append(host)
            return 30.0 if host == "1.1.1.1" else None

        monkeypatch.setattr(R, "_rtt_ms", fake_rtt)
        rtt, host = R._first_rtt_ms(("1.1.1.1", "8.8.8.8", "9.9.9.9"))

        assert (rtt, host) == (30.0, "1.1.1.1")
        assert probed == ["1.1.1.1"], "第一个锚点已可用，不应再探测其余锚点"

    def test_first_rtt_skips_unreachable_anchors(self, monkeypatch):
        """前面的锚点不可达时继续找下一个，全部失败返回 (None, "")。"""
        calls: list[str] = []

        def fake_rtt(host, **kwargs):
            calls.append(host)
            return None

        monkeypatch.setattr(R, "_rtt_ms", fake_rtt)

        assert R._first_rtt_ms(("1.1.1.1", "8.8.8.8")) == (None, "")
        assert calls == ["1.1.1.1", "8.8.8.8"]

    def test_rtt_does_not_retry_after_port_failure(self, monkeypatch):
        """单个端口失败后直接换下一个端口，不对同一端口重试。

        盲目重试是被阻断锚点把耗时放大数倍的原因。
        """
        import socket

        connected: list[tuple] = []

        class _FakeSock:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake_create_connection(addr, timeout=None):
            connected.append(addr)
            if addr[1] == 443:
                raise OSError("blocked")
            return _FakeSock()

        monkeypatch.setattr(socket, "create_connection", fake_create_connection)
        rtt = R._rtt_ms("1.1.1.1")

        assert rtt is not None
        # 443 只试一次就放弃，然后 80 成功；总共两次连接
        assert [p for _, p in connected] == [443, 80]

    def test_rtt_returns_none_when_all_ports_fail(self, monkeypatch):
        import socket

        attempts: list[tuple] = []

        def fake_create_connection(addr, timeout=None):
            attempts.append(addr)
            raise OSError("blocked")

        monkeypatch.setattr(socket, "create_connection", fake_create_connection)

        assert R._rtt_ms("8.8.8.8") is None
        assert len(attempts) == 2, "443 与 80 各试一次即放弃，不应重复尝试"

    def test_region_verdict_unchanged_by_probe_cost(self, monkeypatch):
        """优化探测成本不能改变判定结论：cn 锚点快就仍判 cn。"""
        def fake_rtt(host, **kwargs):
            return {"223.5.5.5": 8.0, "1.1.1.1": 130.0}.get(host)

        monkeypatch.setattr(R, "_rtt_ms", fake_rtt)
        key, evidence = R.detect_region(probe=True)

        assert key == R.REGION_CN
        assert evidence["reason"] == "latency:cn_faster"
        assert evidence["global_anchor_host"] == "1.1.1.1"


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
