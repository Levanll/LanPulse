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
REGION_HK = "hk"
REGION_MO = "mo"
REGION_TW = "tw"
REGION_JP = "jp"
REGION_KR = "kr"
REGION_SG = "sg"
REGION_IN = "in"
REGION_AU = "au"
REGION_NA = "na"
REGION_EU = "eu"
REGION_OTHER = "other"

#: 顺序即设置页下拉顺序：按中文用户的使用概率排，中国大陆在最前。
#: 港澳台连排，便于用户在同一视觉区块里找到。
ALL_REGIONS = (
    REGION_CN, REGION_HK, REGION_MO, REGION_TW, REGION_JP, REGION_KR, REGION_SG,
    REGION_IN, REGION_AU, REGION_NA, REGION_EU, REGION_OTHER,
)

#: v1.1.0 只有 cn / global / apac 三套粗粒度剖面，用户的设置里可能还存着
#: 旧值。这里把它们映射到新粒度，避免升级后设置页显示空白、检测退回默认。
#: global 原本泛指"欧美"，无法区分北美与欧洲，只能落到 other（最保守的回退
#: 剖面不会把正常网络误报成故障）；apac 同理落到 other。
LEGACY_REGION_ALIASES = {
    "global": REGION_OTHER,
    "apac": REGION_OTHER,
}


def normalize_region(region: str) -> str:
    """把任意区域标识归一为新粒度的合法值。未知值回退 other。"""
    key = (region or "").strip().lower()
    if key == REGION_AUTO:
        return REGION_AUTO
    key = LEGACY_REGION_ALIASES.get(key, key)
    return key if key in ALL_REGIONS else REGION_OTHER


def region_display_key(region: str) -> str:
    """区域展示名的 i18n key（具体文案在 app/i18n 目录）。"""
    return f"region.{normalize_region(region)}"


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
    # ---- 香港 ----
    "205.252.144.228": "dns.vendor.hk",
    "202.181.224.2": "dns.vendor.hk",
    # ---- 澳门（CTM / MTel）----
    # 地址取自 public-dns.info 的澳门列表，只保留标注 100% 可靠率的 CTM/MTel 服务器。
    # 澳门只有 CTM 与 MTel 两家固网运营商，不存在像大陆那样的多家公共 DNS。
    "202.175.82.192": "dns.vendor.mo",
    "182.93.23.130": "dns.vendor.mo",
    "205.198.55.225": "dns.vendor.mo",   # MTel
    # ---- 台湾 ----
    "168.95.1.1": "dns.vendor.tw",
    "168.95.192.1": "dns.vendor.tw",
    # ---- 日本 ----
    "203.80.96.10": "dns.vendor.jp",
    "202.12.27.33": "dns.vendor.jp",
    "203.112.2.4": "dns.vendor.jp",
    # ---- 韩国 ----
    "168.126.63.1": "dns.vendor.korea",
    "168.126.63.2": "dns.vendor.korea",
    "164.124.101.2": "dns.vendor.korea",
    # ---- 新加坡 ----
    "165.21.83.88": "dns.vendor.sg",
    "165.21.100.88": "dns.vendor.sg",
    # ---- 印度 ----
    "49.44.44.44": "dns.vendor.in",
    "202.88.232.1": "dns.vendor.in",
    # ---- 澳大利亚 ----
    "139.130.4.5": "dns.vendor.au",
    "203.50.2.71": "dns.vendor.au",
    # ---- 国际 anycast（各区域通用）----
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
    # ---- 欧洲 ----
    "84.200.69.80": "dns.vendor.eu",
    "84.200.70.40": "dns.vendor.eu",
    "185.228.168.9": "dns.vendor.eu",
    "185.228.169.9": "dns.vendor.eu",
    "146.112.61.104": "dns.vendor.eu",
    # ---- 北美 ----
    "64.6.64.6": "dns.vendor.na",
    "64.6.65.6": "dns.vendor.na",
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
#
# 顺序即优先级：1.1.1.1 在国内多数网络可达，而 8.8.8.8 / 9.9.9.9 常被阻断。
# 探测到第一个可用值就停（见 _first_rtt_ms），所以把最可能可达的放最前，
# 否则每个不可达锚点都要付满超时才轮到下一个。
_GLOBAL_ANCHORS = ("1.1.1.1", "8.8.8.8", "9.9.9.9")

#: 单个锚点的探测预算。这是"识别区域"这一全局准备步骤的成本上限，
#: 不属于任何一个检测项。三处串行探测（cn / global / apac）共享它。
_ANCHOR_TIMEOUT = 1.2


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
    # 香港：城市网络，本地解析极快，但多数流量出海，跨境 RTT 与新加坡同档。
    REGION_HK: RegionProfile(
        key=REGION_HK,
        name_key="region.hk",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.yahoo.com.hk", "www.opensource.hk"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("9.9.9.9", "probe.quad9")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("hk_local", ("205.252.144.228", "202.181.224.2"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=50,
        resolve_normal_ms=140,
        resolve_slow_ms=400,
        rtt_excellent_ms=45,
        rtt_normal_ms=110,
        rtt_slow_ms=300,
    ),
    # 澳门：城市网络，规模比香港更小，本地 DNS 只有 CTM 与 MTel 两家。
    # 到香港/珠海都在 10ms 级，到国际 anycast 节点通常经香港出口，
    # 因此阈值在香港的基础上给一点点余量（澳门本地出口带宽更紧张）。
    REGION_MO: RegionProfile(
        key=REGION_MO,
        name_key="region.mo",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.macaupost.gov.mo", "www.gov.mo"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("9.9.9.9", "probe.quad9")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("mo_local", ("202.175.82.192", "182.93.23.130"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=55,
        resolve_normal_ms=150,
        resolve_slow_ms=420,
        rtt_excellent_ms=50,
        rtt_normal_ms=120,
        rtt_slow_ms=320,
    ),
    # 台湾：本地 DNS 干净且快，国际 anycast 通常也在 30ms 内。
    REGION_TW: RegionProfile(
        key=REGION_TW,
        name_key="region.tw",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.yahoo.com.tw", "www.pchome.com.tw"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("168.95.1.1", "probe.tw")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("tw_local", ("168.95.1.1", "168.95.192.1"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=50,
        resolve_normal_ms=140,
        resolve_slow_ms=400,
        rtt_excellent_ms=45,
        rtt_normal_ms=110,
        rtt_slow_ms=300,
    ),
    # 日本：国内 DNS 与 CDN 都很完善，跨境到欧美约 150-200ms。
    REGION_JP: RegionProfile(
        key=REGION_JP,
        name_key="region.jp",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.yahoo.co.jp", "www.rakuten.co.jp"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("202.12.27.33", "probe.jp")),
        tcp_targets=(("www.google.com", 443), ("www.yahoo.co.jp", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("jp_local", ("202.12.27.33", "203.112.2.4"), "accent"),
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=50,
        resolve_normal_ms=140,
        resolve_slow_ms=400,
        rtt_excellent_ms=45,
        rtt_normal_ms=110,
        rtt_slow_ms=300,
    ),
    # 韩国：本地 DNS 质量高，国际线路略逊于日本。
    REGION_KR: RegionProfile(
        key=REGION_KR,
        name_key="region.kr",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.naver.com", "www.daum.net"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("168.126.63.1", "probe.korea")),
        tcp_targets=(("www.google.com", 443), ("www.naver.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("kr_local", ("168.126.63.1", "168.126.63.2"), "accent"),
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=50,
        resolve_normal_ms=140,
        resolve_slow_ms=400,
        rtt_excellent_ms=45,
        rtt_normal_ms=110,
        rtt_slow_ms=300,
    ),
    # 新加坡：东南亚枢纽，到亚太主要城市都近，跨境到欧美偏高。
    REGION_SG: RegionProfile(
        key=REGION_SG,
        name_key="region.sg",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.straitstimes.com", "www.shopee.sg"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("165.21.83.88", "probe.sg")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("sg_local", ("165.21.83.88", "165.21.100.88"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=60,
        resolve_normal_ms=160,
        resolve_slow_ms=450,
        rtt_excellent_ms=50,
        rtt_normal_ms=130,
        rtt_slow_ms=320,
    ),
    # 印度：国际线路质量波动大，跨境 RTT 普遍高于东亚，阈值需放宽。
    REGION_IN: RegionProfile(
        key=REGION_IN,
        name_key="region.in",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.flipkart.com", "www.rediff.com"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("49.44.44.44", "probe.in")),
        tcp_targets=(("www.google.com", 443), ("www.flipkart.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("in_local", ("49.44.44.44", "202.88.232.1"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=80,
        resolve_normal_ms=220,
        resolve_slow_ms=600,
        rtt_excellent_ms=70,
        rtt_normal_ms=180,
        rtt_slow_ms=420,
    ),
    # 澳大利亚：地广人稀，到欧美都要跨洋，基线延迟本就更高。
    REGION_AU: RegionProfile(
        key=REGION_AU,
        name_key="region.au",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.abc.net.au", "www.gumtree.com.au"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("139.130.4.5", "probe.au")),
        tcp_targets=(("www.google.com", 443), ("www.abc.net.au", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("au_local", ("139.130.4.5", "203.50.2.71"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=80,
        resolve_normal_ms=200,
        resolve_slow_ms=550,
        rtt_excellent_ms=70,
        rtt_normal_ms=170,
        rtt_slow_ms=400,
    ),
    # 北美：anycast 就近，公共 DNS 质量高，跨境到亚洲约 150-250ms。
    REGION_NA: RegionProfile(
        key=REGION_NA,
        name_key="region.na",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.wikipedia.org", "www.github.com"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("8.8.8.8", "probe.google")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("opendns", ("208.67.222.222", "208.67.220.220"), "info"),
            _plan("na_local", ("64.6.64.6", "64.6.65.6"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=60,
        resolve_normal_ms=160,
        resolve_slow_ms=450,
        rtt_excellent_ms=50,
        rtt_normal_ms=130,
        rtt_slow_ms=350,
    ),
    # 欧洲：各国运营商 DNS 差异大且隐私约束严，优先推荐欧盟境内的公共解析。
    REGION_EU: RegionProfile(
        key=REGION_EU,
        name_key="region.eu",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.wikipedia.org", "www.heise.de"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("9.9.9.9", "probe.quad9")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("eu_local", ("84.200.69.80", "84.200.70.40"), "accent"),
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "info"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        # GDPR 环境下公共 DNS 的隐私立场比延迟更重要，标签上要能看出来
        resolve_excellent_ms=60,
        resolve_normal_ms=170,
        resolve_slow_ms=450,
        rtt_excellent_ms=50,
        rtt_normal_ms=130,
        rtt_slow_ms=350,
    ),
    # 其他：无法归入上述任何一类时的保守回退。只提供全球 anycast 方案，
    # 阈值取各区域里最宽松的一档，避免把正常网络误报成故障（见 get_profile）。
    REGION_OTHER: RegionProfile(
        key=REGION_OTHER,
        name_key="region.other",
        resolve_domains=("www.google.com", "www.cloudflare.com",
                         "www.wikipedia.org", "www.github.com"),
        ping_targets=(("1.1.1.1", "probe.cloudflare"), ("9.9.9.9", "probe.quad9")),
        tcp_targets=(("www.google.com", 443), ("www.cloudflare.com", 443)),
        mtu_target="1.1.1.1",
        dns_plans=(
            _plan("global_public", ("1.1.1.1", "8.8.8.8"), "accent"),
            _plan("quad9", ("9.9.9.9", "149.112.112.112"), "info"),
            _plan("opendns", ("208.67.222.222", "208.67.220.220"), "info"),
            _plan("dhcp", (), "dim"),
        ),
        resolve_excellent_ms=90,
        resolve_normal_ms=230,
        resolve_slow_ms=600,
        rtt_excellent_ms=75,
        rtt_normal_ms=190,
        rtt_slow_ms=450,
    ),
}


# --------------------------------------------------------------------------- #
# 自动识别
# --------------------------------------------------------------------------- #
# Windows 时区键名 → 区域。用 TimeZoneKeyName（如 "China Standard Time"），
# 而不是 StandardName（后者是本地化资源字符串，中文系统上会返回
# "@tzres.dll,-572" 这种不可读的东西，无法用于匹配）。
_WIN_TZ_HINTS = {
    # ---- 大中华区 ----
    "China Standard Time": REGION_CN,
    "Taipei Standard Time": REGION_TW,
    # 香港与澳门都没有独立的 Windows 时区键，三者共用 China Standard Time。
    # 仅凭时区无法区分，交由语言与延迟打分补充判断（见 detect_region）：
    # zh-HK / zh-MO 两个地区码能把港澳分开，其余中文按大陆处理。
    # ---- 日韩 ----
    "Tokyo Standard Time": REGION_JP,
    "Korea Standard Time": REGION_KR,
    # ---- 东南亚 / 南亚 ----
    "Singapore Standard Time": REGION_SG,
    "SE Asia Standard Time": REGION_SG,          # 曼谷 / 雅加达 / 河内
    "Myanmar Standard Time": REGION_SG,
    "India Standard Time": REGION_IN,
    "Sri Lanka Standard Time": REGION_IN,
    # ---- 大洋洲 ----
    "AUS Eastern Standard Time": REGION_AU,
    "AUS Central Standard Time": REGION_AU,
    "W. Australia Standard Time": REGION_AU,
    "Tasmania Standard Time": REGION_AU,
    "New Zealand Standard Time": REGION_AU,      # 邻近且网络路径相近
    # ---- 北美 ----
    "Pacific Standard Time": REGION_NA,
    "Mountain Standard Time": REGION_NA,
    "Central Standard Time": REGION_NA,
    "Eastern Standard Time": REGION_NA,
    "Atlantic Standard Time": REGION_NA,
    "Alaskan Standard Time": REGION_NA,
    "Hawaiian Standard Time": REGION_NA,
    # ---- 欧洲 ----
    "GMT Standard Time": REGION_EU,
    "W. Europe Standard Time": REGION_EU,
    "Central Europe Standard Time": REGION_EU,
    "Central European Standard Time": REGION_EU,
    "Romance Standard Time": REGION_EU,
    "E. Europe Standard Time": REGION_EU,
    "FLE Standard Time": REGION_EU,
    "Russian Standard Time": REGION_EU,
    "Turkey Standard Time": REGION_EU,
    "GTB Standard Time": REGION_EU,
}

# IANA 时区名 → 区域。跨平台与手动设置 TZ 时使用。
_TZ_HINTS = {
    # ---- 大中华区 ----
    "Asia/Shanghai": REGION_CN, "Asia/Chongqing": REGION_CN, "Asia/Harbin": REGION_CN,
    "Asia/Urumqi": REGION_CN, "PRC": REGION_CN,
    "Asia/Hong_Kong": REGION_HK, "Hongkong": REGION_HK,
    # 澳门用 IANA 的 Asia/Macau（与 Asia/Macao 等价，两者都收录）
    "Asia/Macau": REGION_MO, "Asia/Macao": REGION_MO, "Macao": REGION_MO,
    "Asia/Taipei": REGION_TW, "ROC": REGION_TW,
    # ---- 日韩 ----
    "Asia/Tokyo": REGION_JP, "Japan": REGION_JP,
    "Asia/Seoul": REGION_KR, "ROK": REGION_KR,
    # ---- 东南亚 / 南亚 ----
    "Asia/Singapore": REGION_SG, "Asia/Kuala_Lumpur": REGION_SG,
    "Asia/Bangkok": REGION_SG, "Asia/Jakarta": REGION_SG,
    "Asia/Manila": REGION_SG, "Asia/Ho_Chi_Minh": REGION_SG,
    "Asia/Kolkata": REGION_IN, "Asia/Calcutta": REGION_IN,
    # ---- 大洋洲 ----
    "Australia/Sydney": REGION_AU, "Australia/Melbourne": REGION_AU,
    "Australia/Brisbane": REGION_AU, "Australia/Perth": REGION_AU,
    "Australia/Adelaide": REGION_AU, "Pacific/Auckland": REGION_AU,
    # ---- 北美 ----
    "America/New_York": REGION_NA, "America/Chicago": REGION_NA,
    "America/Denver": REGION_NA, "America/Los_Angeles": REGION_NA,
    "America/Toronto": REGION_NA, "America/Vancouver": REGION_NA,
    "America/Phoenix": REGION_NA, "America/Anchorage": REGION_NA,
    "Pacific/Honolulu": REGION_NA,
    # ---- 欧洲 ----
    "Europe/London": REGION_EU, "Europe/Dublin": REGION_EU,
    "Europe/Paris": REGION_EU, "Europe/Berlin": REGION_EU,
    "Europe/Madrid": REGION_EU, "Europe/Rome": REGION_EU,
    "Europe/Amsterdam": REGION_EU, "Europe/Brussels": REGION_EU,
    "Europe/Vienna": REGION_EU, "Europe/Warsaw": REGION_EU,
    "Europe/Prague": REGION_EU, "Europe/Stockholm": REGION_EU,
    "Europe/Oslo": REGION_EU, "Europe/Helsinki": REGION_EU,
    "Europe/Zurich": REGION_EU, "Europe/Lisbon": REGION_EU,
    "Europe/Athens": REGION_EU, "Europe/Moscow": REGION_EU,
    "Europe/Istanbul": REGION_EU,
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
    """从系统语言推断区域。

    语言只作为最后的兜底（时区与延迟打分都拿不到结论时才用），因此这里
    优先给"语言与区域基本一一对应"的那些：中文按地区细分（zh-CN / zh-TW /
    zh-HK），日韩各自独立，其余语言归到最接近的大区。无法判断时回退
    other —— 它是阈值最宽松的剖面，不会把正常网络误报成故障。
    """
    try:
        lang = _locale.getdefaultlocale()[0] or ""
    except (ValueError, TypeError):
        lang = ""
    if not lang:
        lang = os.environ.get("LANG", "")
    lang = lang.lower().replace("_", "-")

    if lang.startswith("zh"):
        # zh-tw / zh-hk / zh-mo 分别指向台港澳，其余中文（zh-cn / zh-sg 等）按大陆处理。
        # 这是港澳唯一的可靠区分手段：三地共用 Windows 的 China Standard Time。
        if "tw" in lang:
            return REGION_TW
        if "hk" in lang:
            return REGION_HK
        if "mo" in lang:
            return REGION_MO
        return REGION_CN
    if lang.startswith("ja"):
        return REGION_JP
    if lang.startswith("ko"):
        return REGION_KR
    if lang.startswith(("th", "vi", "id", "ms", "fil")):
        return REGION_SG
    if lang.startswith(("hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa")):
        return REGION_IN
    if lang.startswith("en-"):
        # 英语国家横跨三大区，只能按地区码细分
        if any(tag in lang for tag in ("au", "nz")):
            return REGION_AU
        if any(tag in lang for tag in ("gb", "ie")):
            return REGION_EU
        if any(tag in lang for tag in ("sg", "my", "ph")):
            return REGION_SG
        if any(tag in lang for tag in ("in", "pk", "lk", "bd")):
            return REGION_IN
        return REGION_NA          # en-us / en-ca 及未标注地区
    # 欧洲各语种
    if lang.startswith(("de", "fr", "es", "it", "nl", "pt", "pl", "cs", "sv",
                        "no", "da", "fi", "el", "hu", "ro", "bg", "hr", "sk",
                        "sl", "et", "lv", "lt", "ru", "uk", "tr", "sr")):
        return REGION_EU
    return REGION_OTHER


def _rtt_ms(host: str, *, timeout: float = _ANCHOR_TIMEOUT) -> float | None:
    """用 TCP 443/80 握手测 RTT。比 ICMP 可靠：大量企业网/云主机封 ICMP。

    直接连 53 端口（DNS）不合适——很多公共 DNS 不开放 TCP 53 给任意来源。
    这里优先 443（Cloudflare/Google 都开），失败再试 80，取第一个成功的。

    **不做重复尝试。** 实测依据：
    - 被阻断的锚点（国内访问 8.8.8.8 / 9.9.9.9 的常态）表现为 SYN 静默丢弃，
      重试每次都要付满 timeout，零信息增益；
    - 443 被单独封禁但主机可达的锚点（实测 1.1.1.1 如此），重试会让它变成
      "1.2s × 2 + 1.2s"，而 80 端口本来能立刻返回。

    单次采样带来的抖动由判定阈值吸收：cn/global 的 60ms 与 apac 的 40ms
    都是数百毫秒量级的迟滞带，不是逐毫秒比较。
    """
    import socket

    for port in (443, 80):
        try:
            start = time.perf_counter()
            with socket.create_connection((host, port), timeout=timeout):
                return (time.perf_counter() - start) * 1000.0
        except OSError:
            continue
    return None


def _first_rtt_ms(hosts: tuple[str, ...]) -> tuple[float | None, str]:
    """按顺序探测多个锚点，返回第一个可用值就停。

    为什么不能写 `min(_rtt_ms(a) for a in hosts)`：min 会**完整消费**生成器，
    等价于把所有锚点全测一遍。在 8.8.8.8 / 9.9.9.9 被阻断的网络上，
    哪怕 1.1.1.1 已经 30ms 返回，仍要再等两个锚点各超时一次（实测 +9.6s）。
    区域识别只需要一个"全球基准"，取到即可。

    返回 (rtt, 命中的主机)。全部失败时返回 (None, "")。
    """
    for host in hosts:
        rtt = _rtt_ms(host)
        if rtt is not None:
            return rtt, host
    return None, ""


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
        # 取第一个可用的全球基准而不是全部测完再 min()：见 _first_rtt_ms 的说明。
        g_anchor, g_host = _first_rtt_ms(_GLOBAL_ANCHORS)
        evidence["cn_anchor_ms"] = round(cn_anchor, 1) if cn_anchor else None
        evidence["global_anchor_ms"] = round(g_anchor, 1) if g_anchor else None
        if g_host:
            evidence["global_anchor_host"] = g_host
        if cn_anchor is not None and g_anchor is not None:
            # 中国锚点明显更快 → CN；全球锚点明显更快 → 其他区域。
            # 阈值 60ms：低于这个差距属于路由抖动，不足以判定地域。
            if cn_anchor + 60 < g_anchor:
                evidence["reason"] = "latency:cn_faster"
                evidence["region"] = REGION_CN
                return REGION_CN, evidence
            if g_anchor + 60 < cn_anchor:
                # 全球锚点更快，说明不在中国大陆。但要判到具体区域，
                # 单靠延迟不可行：东亚（日韩台新）彼此只差十几毫秒，
                # 且全球 anycast 在各地都就近接入，测出来的差距没有区分度。
                # 因此这里只排除 CN，剩下的区域交给时区判断——
                # 时区键能精确到国家，比延迟打分可靠得多。
                evidence["reason"] = "latency:not_cn"
                # 继续走时区分支；若时区也匹配不上，语言是最后兜底。

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
    """取区域画像。未知区域归一后仍无法匹配时回退 other。

    other 是阈值最宽松的一档，保证任何无法识别的网络都不会被误报成故障。
    旧版本的 "global" / "apac" 会被 normalize_region 映射过来。
    """
    key = normalize_region(region)
    if key == REGION_AUTO:
        # auto 不应该走到这里（调用方应先 detect_region），兜底给 other
        return PROFILES[REGION_OTHER]
    return PROFILES.get(key) or PROFILES[REGION_OTHER]


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
    "REGION_AUTO", "REGION_CN", "REGION_HK", "REGION_MO", "REGION_TW", "REGION_JP",
    "REGION_KR", "REGION_SG", "REGION_IN", "REGION_AU", "REGION_NA",
    "REGION_EU", "REGION_OTHER", "ALL_REGIONS", "LEGACY_REGION_ALIASES",
    "normalize_region", "DnsPlan", "RegionProfile", "PROFILES", "DNS_VENDOR_KEYS",
    "NetworkEnvironment", "detect_region", "get_profile", "region_display_key",
    "detect_captive_portal", "detect_network_environment",
]
