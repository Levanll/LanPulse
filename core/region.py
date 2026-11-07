"""区域与网络环境画像 —— 让检测逻辑在任意国家/地区/网络环境下都成立。

为什么需要这一层：检测项里硬编码的"探测目标"和"推荐 DNS"天然带有地域性。
在国内拿 8.8.8.8 当基准、拿 www.baidu.com 当解析样本，到了欧洲会得出完全
错误的结论；反过来在欧美拿 223.5.5.5 当基准也一样。任何"一刀切"的探测集
都会在跨地域时把正常网络误判为异常。

设计原则：
  1. **探测集与判定逻辑分离**。判定阈值是通用的（延迟分档、丢包率），
     只有"往哪里打"是地域相关的，全部收敛到本模块。
  2. **只用任何区域都可用的锚点**。1.1.1.1 / 8.8.8.8 / 9.9.9.9 是全球
     anycast，跨地域可用；区域锚点只作为"地域打分"的补充证据。
  3. **自动识别 + 手动覆盖**。自动只做保守推断（时区 + 语言 + 延迟打分），
     用户可以随时在设置里固定区域，检测与建议立即跟随。
  4. **不依赖任何地理 IP 数据库、不请求外部 API**。隐私约束下不能把用户的
     公网 IP 发给第三方做定位，因此只用本地可观测信号。
"""
from __future__ import annotations

import ipaddress
import locale as _locale
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable


# --------------------------------------------------------------------------- #
# 区域定义
# --------------------------------------------------------------------------- #
REGION_AUTO = "auto"
REGION_CN = "cn"
REGION_GLOBAL = "global"
REGION_APAC = "apac"

ALL_REGIONS = (REGION_CN, REGION_GLOBAL, REGION_APAC)


def region_display_key(region: str) -> str:
    """区域展示名的 i18n key（具体文案在 app/i18n 目录）。"""
    return f"region.{region}"


# --------------------------------------------------------------------------- #
# DNS 方案（按区域给出不同推荐，这是"跨地域可用"的核心）
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DnsPlan:
    """一套可执行的 DNS 方案。

    servers 为空表示"恢复 DHCP 自动获取"。tag/desc 都是 i18n key，
    真实文案在 app/i18n 目录，避免在这里出现双语字符串。
    """

    plan_id: str
    name_key: str
    servers: tuple[str, ...]
    tag_key: str
    desc_key: str
    accent: str

    @property
    def is_dhcp(self) -> bool:
        return not self.servers


# 全球通用的公共 DNS 归属表。key 是 IP，value 是 i18n key。
# 这张表必须覆盖所有区域会出现的已知 DNS，否则界面上会显示"自定义/运营商"。
DNS_VENDOR_KEYS: dict[str, str] = {
    # ---- 中国大陆 ----
    "223.5.5.5": "dns.vendor.aliyun",
    "223.6.6.6": "dns.vendor.aliyun",
    "119.29.29.29": "dns.vendor.tencent",
    "182.254.116.116": "dns.vendor.tencent",
    "114.114.114.114": "dns.vendor.dns114",
    "114.114.115.115": "dns.vendor.dns114",
    "180.76.76.76": "dns.vendor.baidu",
    "180.184.1.1": "dns.vendor.bytedance",
    "101.226.4.6": "dns.vendor.chinatelecom",
    "210.2.4.8": "dns.vendor.chinamobile",
    # ---- 国际 ----
    "8.8.8.8": "dns.vendor.google",
    "8.8.4.4": "dns.vendor.google",
    "1.1.1.1": "dns.vendor.cloudflare",
    "1.0.0.1": "dns.vendor.cloudflare",
    "9.9.9.9": "dns.vendor.quad9",
    "149.112.112.112": "dns.vendor.quad9",
    "208.67.222.222": "dns.vendor.opendns",
    "208.67.220.220": "dns.vendor.opendns",
    "94.140.14.14": "dns.vendor.adguard",
    "94.140.15.15": "dns.vendor.adguard",
    "76.76.2.0": "dns.vendor.controld",
    "76.76.10.0": "dns.vendor.controld",
    "77.88.8.8": "dns.vendor.yandex",
    "77.88.8.1": "dns.vendor.yandex",
    "168.126.63.1": "dns.vendor.korea",
    "168.126.63.2": "dns.vendor.korea",
    "203.80.96.10": "dns.vendor.jp",
    "202.12.27.33": "dns.vendor.jp",
    "203.112.2.4": "dns.vendor.jp",
}


# --------------------------------------------------------------------------- #
# 区域画像
# --------------------------------------------------------------------------- #
@dataclass
class RegionProfile:
    """一个区域下"打哪里、推荐什么"的完整定义。"""

    key: str
    name_key: str
    #: DNS 解析测试域名。必须在该区域解析快且稳定，且不依赖 CDN 就近。
    #: 注意：这些只用于测"解析耗时"，不下载任何内容。
    resolve_domains: tuple[str, ...]
    #: ICMP 连通性探测目标 (ip, 说明key)
    ping_targets: tuple[tuple[str, str], ...]
    #: TCP 443 握手探测目标 (host, port)
    tcp_targets: tuple[tuple[str, int], ...]
    #: MTU 探测目标。必须是允许 ICMP + DF 的地址。
    mtu_target: str
    #: DNS 方案（按推荐顺序）
    dns_plans: tuple[DnsPlan, ...]
    #: 该区域"正常"的解析延迟上限（毫秒）。欧美公共 DNS 的冷查询明显慢于国内，
    #: 用国内的 150ms 阈值去判欧美的 200ms 会把正常网络报成异常。
    resolve_excellent_ms: int = 60
    resolve_normal_ms: int = 150
    resolve_slow_ms: int = 400
    #: 该区域正常的跨境 RTT 期望。用于连通性分级，避免用同一把尺子量全球。
    rtt_excellent_ms: int = 50
    rtt_normal_ms: int = 120
    rtt_slow_ms: int = 300

    def vendor_key(self, ip: str) -> str | None:
        return DNS_VENDOR_KEYS.get(ip)


# 任何区域都可用的全球 anycast 锚点。用作自动识别时的"中立基准"。
_GLOBAL_ANCHORS = ("1.1.1.1", "8.8.8.8", "9.9.9.9")


def _plan(plan_id: str, servers: tuple[str, ...], accent: str) -> DnsPlan:
    return DnsPlan(
        plan_id=plan_id,
        name_key=f"dns.plan.{plan_id}.name",
        servers=servers,
        tag_key=f"dns.plan.{plan_id}.tag",
        desc_key=f"dns.plan.{plan_id}.desc",
        accent=accent,
    )


PROFILES: dict[str, RegionProfile] = {
    REGION_CN: RegionProfile(
        key=REGION_CN,
        name_key="region.cn",
        resolve_domains=("www.baidu.com", "www.qq.com", "www.taobao.com", "www.bilibili.com"),
        ping_targets=(("223.5.5.5", "probe.aliyun"), ("119.29.29.29", "probe.tencent")),
        tcp_targets=(("www.baidu.com", 443), ("www.qq.com", 443)),
        mtu_target="223.5.5.5",
        dns_plans=(
            _plan("ali_tencent", ("223.5.5.5", "119.29.29.29"), "accent"),
            _plan("dns114", ("114.114.114.114", "114.114.115.115"), "info"),
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "warn"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=60,
        resolve_normal_ms=150,
        resolve_slow_ms=400,
        rtt_excellent_ms=50,
        rtt_normal_ms=120,
        rtt_slow_ms=300,
    ),
    REGION_GLOBAL: RegionProfile(
        key=REGION_GLOBAL,
        name_key="region.global",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.wikipedia.org", "www.github.com"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("8.8.8.8", "probe.google")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("opendns", ("208.67.222.222", "208.67.220.220"), "info"),
            _plan("ali_tencent", ("223.5.5.5", "119.29.29.29"), "warn"),
            _plan("dhcp", (), "dim"),
        ),
        # 跨国访问公共 DNS 的冷查询天然更慢，阈值放宽
        resolve_excellent_ms=80,
        resolve_normal_ms=200,
        resolve_slow_ms=500,
        rtt_excellent_ms=60,
        rtt_normal_ms=150,
        rtt_slow_ms=350,
    ),
    REGION_APAC: RegionProfile(
        key=REGION_APAC,
        name_key="region.apac",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.yahoo.co.jp", "www.naver.com"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("9.9.9.9", "probe.quad9")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("apac_local", ("168.126.63.1", "203.80.96.10"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("ali_tencent", ("223.5.5.5", "119.29.29.29"), "warn"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=80,
        resolve_normal_ms=200,
        resolve_slow_ms=500,
        rtt_excellent_ms=60,
        rtt_normal_ms=150,
        rtt_slow_ms=350,
    ),
}


# --------------------------------------------------------------------------- #
# 自动识别
# --------------------------------------------------------------------------- #
# Windows 时区键名 → 区域。用 TimeZoneKeyName（如 "China Standard Time"），
# 而不是 StandardName（后者是本地化资源字符串，中文系统上会返回
# "@tzres.dll,-572" 这种不可读的东西，无法用于匹配）。
_WIN_TZ_HINTS = {
    "China Standard Time": REGION_CN,
    "Taipei Standard Time": REGION_APAC,
    "Tokyo Standard Time": REGION_APAC,
    "Korea Standard Time": REGION_APAC,
    "Singapore Standard Time": REGION_APAC,
    "W. Australia Standard Time": REGION_APAC,
    "AUS Eastern Standard Time": REGION_APAC,
    "India Standard Time": REGION_APAC,
    "SE Asia Standard Time": REGION_APAC,
}

# IANA 时区名 → 区域。跨平台与手动设置 TZ 时使用。
_TZ_HINTS = {
    "Asia/Shanghai": REGION_CN, "Asia/Chongqing": REGION_CN, "Asia/Harbin": REGION_CN,
    "Asia/Urumqi": REGION_CN, "PRC": REGION_CN,
    "Asia/Tokyo": REGION_APAC, "Asia/Seoul": REGION_APAC, "Asia/Singapore": REGION_APAC,
    "Asia/Hong_Kong": REGION_APAC, "Asia/Taipei": REGION_APAC, "Asia/Bangkok": REGION_APAC,
    "Australia/Sydney": REGION_APAC, "Asia/Kolkata": REGION_APAC,
}


def _system_timezone() -> str:
    """读取系统时区键名。

    优先 TimeZoneKeyName（"China Standard Time"，稳定、可匹配）；
    退回 StandardName 时若读到 "@tzres.dll,-NNN" 这类资源引用则视为无效，
    因为它不含任何可用于判断区域的信息。
    """
    tz = os.environ.get("TZ", "").strip()
    if tz:
        return tz
    try:
        import winreg  # type: ignore

        key = r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as h:
            for name in ("TimeZoneKeyName", "StandardName"):
                try:
                    value = str(winreg.QueryValueEx(h, name)[0]).strip()
                except OSError:
                    continue
                if value and not value.startswith("@") and "tzres.dll" not in value:
                    return value
    except (OSError, ImportError):
        pass
    return ""


def _locale_region() -> str:
    """从系统语言推断区域。中文 → CN，其余 → GLOBAL。"""
    try:
        lang = _locale.getdefaultlocale()[0] or ""
    except (ValueError, TypeError):
        lang = ""
    if not lang:
        lang = os.environ.get("LANG", "")
    lang = lang.lower()
    if lang.startswith("zh"):
        return REGION_CN
    if any(lang.startswith(p) for p in ("ja", "ko", "th", "vi", "id")):
        return REGION_APAC
    return REGION_GLOBAL


def _rtt_ms(host: str, *, timeout: float = 1.2, attempts: int = 2) -> float | None:
    """用 TCP 443/80 握手测 RTT。比 ICMP 可靠：大量企业网/云主机封 ICMP。

    直接连 53 端口（DNS）不合适——很多公共 DNS 不开放 TCP 53 给任意来源。
    这里优先 443（Cloudflare/Google 都开），失败再试 80。
    """
    import socket

    for port in (443, 80):
        samples: list[float] = []
        for _ in range(attempts):
            try:
                start = time.perf_counter()
                with socket.create_connection((host, port), timeout=timeout):
                    samples.append((time.perf_counter() - start) * 1000.0)
            except OSError:
                continue
        if samples:
            return min(samples)
    return None


def detect_region(*, probe: bool = True) -> tuple[str, dict[str, Any]]:
    """识别当前区域，返回 (region_key, 诊断证据)。

    判定顺序（先强后弱）：
      1. 延迟打分：分别测"中国锚点"与"全球锚点"的 RTT，差距显著则采信；
      2. 时区：Asia/Shanghai 等 → CN；
      3. 系统语言：zh → CN，ja/ko/th → APAC，其余 → GLOBAL。

    第 1 步只用 ICP 可达性不同的公共地址，不请求任何定位 API。
    """
    evidence: dict[str, Any] = {"probe_enabled": probe}

    # ---- 1. 延迟打分 ----
    if probe:
        cn_anchor = _rtt_ms("223.5.5.5")
        g_anchor = min(
            (v for v in (_rtt_ms(a) for a in _GLOBAL_ANCHORS) if v is not None),
            default=None,
        )
        evidence["cn_anchor_ms"] = round(cn_anchor, 1) if cn_anchor else None
        evidence["global_anchor_ms"] = round(g_anchor, 1) if g_anchor else None
        if cn_anchor is not None and g_anchor is not None:
            # 中国锚点明显更快 → CN；全球锚点明显更快 → GLOBAL。
            # 阈值 60ms：低于这个差距属于路由抖动，不足以判定地域。
            if cn_anchor + 60 < g_anchor:
                evidence["reason"] = "latency:cn_faster"
                evidence["region"] = REGION_CN
                return REGION_CN, evidence
            if g_anchor + 60 < cn_anchor:
                # 再看是 APAC 还是欧美：日韩锚点明显更快则为 APAC
                apac = min(
                    (v for v in (_rtt_ms("168.126.63.1"), _rtt_ms("203.80.96.10"))
                     if v is not None),
                    default=None,
                )
                evidence["apac_anchor_ms"] = round(apac, 1) if apac else None
                if apac is not None and apac + 40 < g_anchor:
                    evidence["reason"] = "latency:apac_faster"
                    evidence["region"] = REGION_APAC
                    return REGION_APAC, evidence
                evidence["reason"] = "latency:global_faster"
                evidence["region"] = REGION_GLOBAL
                return REGION_GLOBAL, evidence

    # ---- 2. 时区 ----
    tz = _system_timezone()
    evidence["timezone"] = tz
    if tz:
        for hint, region in _WIN_TZ_HINTS.items():
            if hint.lower() == tz.lower():
                evidence["reason"] = f"timezone:{hint}"
                evidence["region"] = region
                return region, evidence
        for hint, region in _TZ_HINTS.items():
            if hint.lower() in tz.lower():
                evidence["reason"] = f"timezone:{hint}"
                evidence["region"] = region
                return region, evidence

    # ---- 3. 语言 ----
    region = _locale_region()
    evidence["reason"] = "locale"
    evidence["region"] = region
    return region, evidence


def get_profile(region: str) -> RegionProfile:
    """取区域画像。未知区域回退到全球画像（最保守，不会把慢网误报成故障）。"""
    return PROFILES.get(region) or PROFILES[REGION_GLOBAL]


# --------------------------------------------------------------------------- #
# 网络环境画像（不同类型的接入网，检测策略必须不同）
# --------------------------------------------------------------------------- #
@dataclass
class NetworkEnvironment:
    """当前网络环境的关键事实，供检测项调整策略。"""

    icmp_available: bool = True
    captive_portal: bool = False
    portal_probe: str = ""
    ipv6_only: bool = False
    behind_proxy: bool = False
    vpn_active: bool = False
    notes: list[str] = field(default_factory=list)


def _has_ipv6_global(adapters: list[Any]) -> bool:
    for a in adapters:
        for ip in getattr(a, "ipv6", []) or []:
            try:
                addr = ipaddress.ip_address(str(ip).split("%")[0])
            except ValueError:
                continue
            if addr.version == 6 and not (addr.is_private or addr.is_loopback or addr.is_link_local):
                return True
    return False


_CAPTIVE_PROBES = (
    # 返回 204 表示"无劫持、无需登录"。任何 200/302 都说明有中间人在改写。
    "http://connectivitycheck.gstatic.com/generate_204",
    "http://www.gstatic.com/generate_204",
    "http://detectportal.firefox.com/success.txt",
)


def detect_captive_portal(*, timeout: float = 4.0) -> tuple[bool, str]:
    """检测是否需要网页登录（酒店/机场/校园网常见）。

    判定依据：HTTP 请求被重定向或返回内容被改写。全程只读、只发 GET，
    不上传任何数据。全部探测失败（无外网）时返回 (False, "")，不误报。
    """
    import urllib.error
    import urllib.request

    for url in _CAPTIVE_PROBES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "LanPulse/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                code = resp.getcode()
                body = resp.read(64)
                if code == 204:
                    return False, ""
                # 200 但内容不是预期的 success.txt → 被门户改写
                if "detectportal.firefox.com" in url and b"success" in body:
                    return False, ""
                return True, url
        except urllib.error.HTTPError as exc:
            # 3xx/511 等明确表示有拦截层
            if exc.code in (301, 302, 303, 307, 308, 511):
                return True, url
            continue
        except (urllib.error.URLError, OSError, TimeoutError):
            continue
    return False, ""


def detect_network_environment(
    adapters: list[Any],
    *,
    proxy_enabled: bool = False,
    probe: bool = True,
) -> NetworkEnvironment:
    """汇总当前网络环境的各项事实。

    probe=False 时只做纯本地推断（不发起任何网络请求），用于快速路径。
    """
    env = NetworkEnvironment()
    env.behind_proxy = proxy_enabled

    up = [a for a in adapters if getattr(a, "up", False)]
    env.vpn_active = any(
        getattr(a, "is_virtual", False) and getattr(a, "up", False) and getattr(a, "gateway", "")
        for a in up
    )
    has_v4 = any(getattr(a, "ipv4", None) for a in up)
    has_v6 = _has_ipv6_global(adapters)
    env.ipv6_only = bool(has_v6 and not has_v4)

    if env.vpn_active:
        env.notes.append("env.vpn_active")
    if env.behind_proxy:
        env.notes.append("env.proxy")
    if env.ipv6_only:
        env.notes.append("env.ipv6_only")

    if probe:
        portal, url = detect_captive_portal()
        env.captive_portal = portal
        env.portal_probe = url
        if portal:
            env.notes.append("env.captive_portal")
    return env


__all__ = [
    "REGION_AUTO", "REGION_CN", "REGION_GLOBAL", "REGION_APAC", "ALL_REGIONS",
    "DnsPlan", "RegionProfile", "PROFILES", "DNS_VENDOR_KEYS",
    "NetworkEnvironment", "detect_region", "get_profile", "region_display_key",
    "detect_captive_portal", "detect_network_environment",
]
