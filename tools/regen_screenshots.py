r"""截图脱敏：用合成数据重新生成 README 用图。

问题：
    docs/images/ 下的截图原本是用**本机真实体检结果**渲染的，包含
    - 计算机名
    - 内网 IPv4 与默认网关
    - 网卡型号与虚拟网卡布局
    这些属于个人信息，不应随开源仓库发布。

做法：
    构造一份**合成的** DiagnosticReport（主机名、IP、网关全部使用文档保留值），
    用真实 UI 组件渲染成图。这样截图能反映真实界面，但不含任何本机数据。
    合成数据使用 RFC 5737 文档专用地址段（192.0.2.0/24）与 EXAMPLE 主机名。

用法（需要图形环境）：
    python tools/regen_screenshots.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

try:
    from _console import setup_console

    setup_console()
except ImportError:
    pass

from core.i18n import t  # noqa: E402
from core.models import CheckResult, DiagnosticReport, Metric, Severity  # noqa: E402

#: 脱敏用的占位值。全部来自文档/示例保留段，不对应任何真实设备。
SYNTH_HOST = "EXAMPLE-PC"
SYNTH_IP = "192.0.2.42"          # RFC 5737 TEST-NET-1
SYNTH_PREFIX = 24
SYNTH_GW = "192.0.2.1"
SYNTH_DNS = ["223.5.5.5", "223.6.6.6", "119.29.29.29"]


def build_report() -> DiagnosticReport:
    """构造一份合成报告：结构与真实体检一致，数值为脱敏占位值。"""
    rep = DiagnosticReport(
        host=SYNTH_HOST,
        os_name="Windows 11",
        elevated=False,
    )
    rep.finished_at = time.time()

    rep.results = [
        CheckResult(
            check_id="adapter", title="check.adapter.title",
            category="check.adapter.category", severity=Severity.OK,
            summary_key="check.adapter.summary_ok",
            summary="Adapter link is healthy and connected",
            detail="• Ethernet | Up | 192.0.2.42\n• Wi-Fi | Disconnected | no IP",
            metrics=[
                Metric("metric.link_speed", "1 Gbps", "Ethernet"),
                Metric("metric.adapter_count", "2", "1 up / 1 virtual"),
                Metric("metric.primary_adapter", "Ethernet", "Generic Gigabit Ethernet"),
                Metric("metric.ipv4", f"{SYNTH_IP}/{SYNTH_PREFIX}"),
                Metric("metric.gateway", SYNTH_GW),
            ],
        ),
        CheckResult(
            check_id="ip", title="check.ip.title",
            category="check.ip.category", severity=Severity.OK,
            summary_key="check.ip.summary_ok",
            summary_args={"ip": SYNTH_IP, "prefix": SYNTH_PREFIX, "mode": "静态"},
            summary=f"IPv4 配置正常：{SYNTH_IP}/{SYNTH_PREFIX}（静态），网关同网段",
            metrics=[
                Metric("metric.ipv4", f"{SYNTH_IP}/{SYNTH_PREFIX}", ok=True),
                Metric("metric.acquire_mode", "静态配置"),
                Metric("metric.gateway", SYNTH_GW, ok=True),
            ],
        ),
        CheckResult(
            check_id="gateway", title="check.gateway.title",
            category="check.gateway.category", severity=Severity.OK,
            summary_key="check.gateway.summary_ok",
            summary_args={"gw": SYNTH_GW},
            summary=f"默认网关 {SYNTH_GW} 配置正常",
            metrics=[
                Metric("metric.gateway", SYNTH_GW, ok=True),
                Metric("metric.route_count", "1"),
                Metric("metric.gateway_latency", "2ms", ok=True),
            ],
        ),
        CheckResult(
            check_id="dns_server", title="check.dns_server.title",
            category="check.dns_server.category", severity=Severity.OK,
            summary_key="check.dns_server.summary_ok",
            summary_args={
                "mode": "value.manual_specified",
                "head_parts": [
                    {"key": "check.dns_server.owner_pair_full",
                     "args": {"ip": "223.5.5.5", "owner": "dns.vendor.aliyun"}},
                    {"key": "check.dns_server.owner_pair_full",
                     "args": {"ip": "223.6.6.6", "owner": "dns.vendor.aliyun"}},
                    {"key": "check.dns_server.owner_pair_full",
                     "args": {"ip": "119.29.29.29", "owner": "dns.vendor.tencent"}},
                ],
            },
            summary="DNS 配置正常（手动指定）：223.5.5.5（阿里公共 DNS）；223.6.6.6（阿里公共 DNS）",
            evidence={"servers": SYNTH_DNS, "interface": "Ethernet"},
            metrics=[
                Metric("metric.dns_count", "3", ok=True),
                Metric("metric.dns_owner", "223.5.5.5", "阿里公共 DNS", ok=True),
            ],
        ),
        CheckResult(
            check_id="dns_resolve", title="check.dns_resolve.title",
            category="check.dns_resolve.category", severity=Severity.OK,
            summary_key="check.dns_resolve.summary_ok",
            summary_args={"n": 4, "ms": "8", "grade": "优秀"},
            summary="域名解析正常：4 个域名平均耗时 8ms（优秀）",
            metrics=[
                Metric("metric.avg_resolve_ms", "8ms", "优秀", ok=True),
                Metric("metric.probe_domains", "4", ok=True),
            ],
        ),
        CheckResult(
            check_id="hosts", title="check.hosts.title",
            category="check.hosts.category", severity=Severity.OK,
            summary_key="check.hosts.summary_ok",
            summary_args={"n": 0},
            summary="HOSTS 正常：0 条自定义映射，未发现屏蔽或劫持记录",
            metrics=[
                Metric("metric.mapping_lines", "0", ok=True),
                Metric("metric.blocked_records", "0", ok=True),
            ],
        ),
        CheckResult(
            check_id="proxy", title="check.proxy.title",
            category="check.proxy.category", severity=Severity.OK,
            summary_key="check.proxy.summary_ok",
            summary="未使用系统代理，网络直连（正常）",
            metrics=[Metric("metric.proxy_enable", "否", ok=True)],
        ),
        CheckResult(
            check_id="tcp", title="check.tcp.title",
            category="check.tcp.category", severity=Severity.OK,
            summary_key="check.tcp.summary_ok",
            summary_args={"auto": "normal"},
            summary="协议栈参数正常（接收窗口自动调节 normal，窗口缩放启发式 disabled）",
            metrics=[
                Metric("metric.autotuning", "normal", ok=True),
                Metric("metric.rss", "enabled", ok=True),
            ],
        ),
        CheckResult(
            check_id="mtu", title="check.mtu.title",
            category="check.mtu.category", severity=Severity.OK,
            summary_key="check.mtu.summary_ok",
            summary_args={"cfg": 1500, "pmtu": 1492, "gap": -8, "tol": 20},
            summary="MTU 正常：配置 1500，实测路径 1492（差 -8 字节，在 20 字节容差内）",
            metrics=[
                Metric("metric.configured_mtu", "1500"),
                Metric("metric.measured_mtu", "1492", "路径 MTU", ok=True),
            ],
        ),
        CheckResult(
            check_id="firewall", title="check.firewall.title",
            category="check.firewall.category", severity=Severity.WARN,
            summary_key="check.firewall.summary_all_off",
            summary_args={"profiles_parts": ["profile.domain", "profile.private", "profile.public"]},
            summary="三个网络配置文件的防火墙全部关闭：域网络、专用网络、公用网络",
            advice=["建议开启防火墙，避免局域网内其它设备访问本机服务"],
            action_ids=["firewall.ensure_enabled"],
            metrics=[
                Metric("profile.domain", "关闭", ok=False),
                Metric("profile.domain", "关闭", ok=False),
                Metric("profile.domain", "关闭", ok=False),
            ],
        ),
        CheckResult(
            check_id="connectivity", title="check.connectivity.title",
            category="check.connectivity.category", severity=Severity.OK,
            summary_key="check.connectivity.summary_ok",
            summary_args={"ping": "7ms（优秀）", "handshake": "最慢 43ms"},
            summary="外网连通正常：ping 7ms（优秀），HTTPS 握手最慢 43ms",
            metrics=[
                Metric(t("metric.ping_target", target="223.5.5.5"), "7ms", ok=True),
                Metric("metric.loss_rate", "0%", ok=True),
            ],
        ),
    ]
    for r in rep.results:
        r.duration_ms = 80
    return rep


SHOTS = [
    (0, "scenario"),
    (1, "dashboard"),
    (2, "dns"),
    (3, "hosts"),
    (4, "repair"),
    (5, "backup"),
    (6, "diagnose"),
    (7, "report"),
    # 这里是页面名，不是文件名。曾经写成 "settings-zh"，导致英文模式
    # 拼出 screenshot-settings-zh-en.png 这种不存在的图，而 README_EN.md
    # 引用的 screenshot-settings-en.png 永远不会更新。
    (8, "settings"),
]


def main() -> int:
    # 支持 --lang zh|en：中英两套截图，供 README.md / README_EN.md 分别引用
    lang = "zh"
    if "--lang" in sys.argv:
        idx = sys.argv.index("--lang")
        if idx + 1 < len(sys.argv):
            lang = sys.argv[idx + 1]
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)

    from app.ui.main_window import MainWindow
    from app.ui.state import AppState
    from core.i18n import set_language, t
    from core.settings import load_settings

    set_language(lang)
    state = AppState(settings=load_settings())
    win = MainWindow(state, elevated=False, settings=state.settings)
    win.show()

    rep = build_report()
    state.set_report(rep)
    out_dir = ROOT / "docs" / "images"
    out_dir.mkdir(parents=True, exist_ok=True)

    idx = {"i": 0}

    def shoot_next() -> None:
        i = idx["i"]
        if i >= len(SHOTS):
            print(f"全部截图已重新生成（{lang}）")
            app.quit()
            return
        page_idx, name = SHOTS[i]
        win.switch_page(page_idx)
        app.processEvents()
        time.sleep(0.4)
        app.processEvents()
        # 命名规则：英文一律加 -en；中文默认不加后缀，但 settings 页例外
        # （README.md 引用的是 screenshot-settings-zh.png）。
        if lang == "zh":
            suffix = "-zh" if name == "settings" else ""
        else:
            suffix = f"-{lang}"
        path = out_dir / f"screenshot-{name}{suffix}.png"
        win.grab().save(str(path))
        print(f"  saved {path.name}")
        idx["i"] = i + 1
        QTimer.singleShot(450, shoot_next)

    QTimer.singleShot(700, shoot_next)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
