r"""为 v1.1.0 新功能补充 i18n 文案。

新增内容：
  * 3 个检测项（web_timing / dns_hijack / bufferbloat）的标题、分类、结论
  * 6 个场景（slow / disconnect / web / gaming / security / full）
  * 10 条根因规则（标题、影响、建议）
  * 上述涉及的新指标名

写法要求：键名与代码里的引用严格一致；中英占位符集合必须相同。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

ZH: dict[str, str] = {
    # ---------------- 检测项 ----------------
    "check.web_timing.title": "网页打开速度",
    "check.web_timing.category": "网页",
    "check.web_timing.summary_skipped": "已关闭联网探测",
    "check.dns_hijack.title": "DNS 解析是否被篡改",
    "check.dns_hijack.category": "安全",
    "check.dns_hijack.summary_skipped": "已关闭联网探测",
    "check.dns_hijack.summary_no_dns": "未配置手动 DNS",
    "check.bufferbloat.title": "下载时延卡顿",
    "check.bufferbloat.category": "体验",
    "check.bufferbloat.summary_skipped": "已关闭联网探测",
    "check.bufferbloat.summary_unmeasurable": "无法测量延迟",
    "check.bufferbloat.summary_no_load": "无法产生有效下载负载",

    # ---------------- 新指标 ----------------
    "metric.web_target": "测试站点",
    "metric.web_dns": "DNS 解析",
    "metric.web_tcp": "TCP 连接",
    "metric.web_tls": "TLS 握手",
    "metric.web_ttfb": "首字节响应",
    "metric.web_cert": "证书剩余",
    "metric.hijack_query": "解析对比",
    "metric.bufferbloat_idle": "空闲延迟",
    "metric.bufferbloat_loaded": "下载时延迟",
    "metric.bufferbloat_delta": "延迟增量",
    "metric.bufferbloat_grade": "评级",

    # ---------------- 等级 ----------------
    "metric.grade_good": "优秀",
    "metric.grade_fair": "一般",
    "metric.grade_poor": "偏慢",
    "metric.grade_unknown": "未测",

    # ---------------- 场景 ----------------
    "scenario.slow.name": "上网很慢",
    "scenario.slow.desc": "网页加载慢、下载慢、视频缓冲久",
    "scenario.disconnect.name": "经常断网",
    "scenario.disconnect.desc": "偶尔掉线、需要重启路由器才能恢复",
    "scenario.web.name": "网页打不开",
    "scenario.web.desc": "某些或全部网站无法访问，但 QQ 等能上",
    "scenario.gaming.name": "游戏 / 视频卡顿",
    "scenario.gaming.desc": "网速够快，但游戏延迟高、视频会议卡",
    "scenario.security.name": "检查是否被劫持",
    "scenario.security.desc": "怀疑网站被篡改、跳转到广告页",
    "scenario.full.name": "完整体检",
    "scenario.full.desc": "运行全部 14 项检测（约 10-15 秒）",

    # ---------------- 根因规则 ----------------
    "rootcause.dhcp_failed.title": "路由器没有分配 IP 地址",
    "rootcause.dhcp_failed.impact": "拿到的是 169.254 开头的无效地址，无法上网",
    "rootcause.dhcp_failed.advice": "执行「重新获取 IP 地址」，仍失败请重启路由器",

    "rootcause.hosts_hijack.title": "HOSTS 文件存在可疑记录",
    "rootcause.hosts_hijack.impact": "特定网站会被指向错误地址，可能被屏蔽或劫持",
    "rootcause.hosts_hijack.advice": "清理异常记录，并对电脑做一次杀毒扫描",

    "rootcause.dns_hijack.title": "DNS 解析结果被篡改",
    "rootcause.dns_hijack.impact": "同一域名解析到错误的 IP，导致网站打不开或跳到假站",
    "rootcause.dns_hijack.advice": "切换到可信公共 DNS，并检查 HOSTS 文件",

    "rootcause.proxy_residual.title": "代理软件退出后残留了系统代理",
    "rootcause.proxy_residual.impact": "所有网页请求都被发往一个已关闭的端口，表现为完全无法上网",
    "rootcause.proxy_residual.advice": "关闭残留的系统代理设置",

    "rootcause.gateway_poor.title": "到路由器的这一段链路质量差",
    "rootcause.gateway_poor.impact": "丢包或延迟高，整条网络都不稳定",
    "rootcause.gateway_poor.advice": "无线环境先换 5GHz 或靠近路由器；有线检查网线与网口",

    "rootcause.dns_slow.title": "DNS 解析速度慢",
    "rootcause.dns_slow.impact": "每次打开新网站都要先等解析，表现为“点开就卡一下”",
    "rootcause.dns_slow.advice": "清空 DNS 缓存，或切换到更快的公共 DNS",

    "rootcause.web_break.title": "网页访问在某一层中断",
    "rootcause.web_break.impact": "分层计时已定位到具体环节，不必逐项排查",
    "rootcause.web_break.advice": "按下方分层数据对应处理",

    "rootcause.mtu_mismatch.title": "MTU 不匹配（大包被丢弃）",
    "rootcause.mtu_mismatch.impact": "小包能通、大包被丢，表现为“能开首页但视频和下载卡死”",
    "rootcause.mtu_mismatch.advice": "按实测值修正 MTU",

    "rootcause.bufferbloat.title": "下载时延迟明显升高",
    "rootcause.bufferbloat.impact": "带宽没跑满但延迟飙升，游戏与视频会议最容易感知",
    "rootcause.bufferbloat.advice": "在路由器启用 SQM / QoS，或限制后台大流量任务",

    "rootcause.firewall_off.title": "Windows 防火墙处于关闭状态",
    "rootcause.firewall_off.impact": "这是安全风险，不会导致当前无法上网",
    "rootcause.firewall_off.advice": "建议重新启用防火墙",
}

EN: dict[str, str] = {
    "check.web_timing.title": "Web page load speed",
    "check.web_timing.category": "Web",
    "check.web_timing.summary_skipped": "Network probing disabled",
    "check.dns_hijack.title": "DNS tampering check",
    "check.dns_hijack.category": "Security",
    "check.dns_hijack.summary_skipped": "Network probing disabled",
    "check.dns_hijack.summary_no_dns": "No manual DNS configured",
    "check.bufferbloat.title": "Lag under download load",
    "check.bufferbloat.category": "Experience",
    "check.bufferbloat.summary_skipped": "Network probing disabled",
    "check.bufferbloat.summary_unmeasurable": "Latency unmeasurable",
    "check.bufferbloat.summary_no_load": "Could not create download load",

    "metric.web_target": "Test site",
    "metric.web_dns": "DNS lookup",
    "metric.web_tcp": "TCP connect",
    "metric.web_tls": "TLS handshake",
    "metric.web_ttfb": "First byte",
    "metric.web_cert": "Cert validity",
    "metric.hijack_query": "Resolution compare",
    "metric.bufferbloat_idle": "Idle latency",
    "metric.bufferbloat_loaded": "Loaded latency",
    "metric.bufferbloat_delta": "Latency increase",
    "metric.bufferbloat_grade": "Grade",

    "metric.grade_good": "Good",
    "metric.grade_fair": "Fair",
    "metric.grade_poor": "Slow",
    "metric.grade_unknown": "N/A",

    "scenario.slow.name": "Slow internet",
    "scenario.slow.desc": "Pages load slowly, downloads crawl, videos buffer",
    "scenario.disconnect.name": "Frequent disconnects",
    "scenario.disconnect.desc": "Drops out now and then; a router restart fixes it",
    "scenario.web.name": "Websites won't open",
    "scenario.web.desc": "Some or all sites fail, but chat apps still work",
    "scenario.gaming.name": "Gaming / video lag",
    "scenario.gaming.desc": "Bandwidth is fine but games lag and calls stutter",
    "scenario.security.name": "Check for tampering",
    "scenario.security.desc": "Sites look altered or redirect to ad pages",
    "scenario.full.name": "Full checkup",
    "scenario.full.desc": "Run all 14 checks (about 10-15 seconds)",

    "rootcause.dhcp_failed.title": "The router did not assign an IP address",
    "rootcause.dhcp_failed.impact": "The address is a 169.254 placeholder, so there is no internet",
    "rootcause.dhcp_failed.advice": "Run \"Renew IP address\"; if it still fails, restart the router",

    "rootcause.hosts_hijack.title": "Suspicious entries in the HOSTS file",
    "rootcause.hosts_hijack.impact": "Specific sites resolve to the wrong address and may be blocked or hijacked",
    "rootcause.hosts_hijack.advice": "Clean the entries and run a full antivirus scan",

    "rootcause.dns_hijack.title": "DNS responses are being tampered with",
    "rootcause.dns_hijack.impact": "A domain resolves to the wrong IP, so sites fail or lead to fake pages",
    "rootcause.dns_hijack.advice": "Switch to a trusted public DNS and review the HOSTS file",

    "rootcause.proxy_residual.title": "A dead system proxy was left behind",
    "rootcause.proxy_residual.impact": "Every web request goes to a closed port, which looks like a total outage",
    "rootcause.proxy_residual.advice": "Clear the leftover system proxy setting",

    "rootcause.gateway_poor.title": "The link to the router is poor",
    "rootcause.gateway_poor.impact": "Packet loss or high latency makes the whole connection unstable",
    "rootcause.gateway_poor.advice": "On Wi-Fi try 5 GHz or move closer; on Ethernet check the cable and port",

    "rootcause.dns_slow.title": "DNS lookups are slow",
    "rootcause.dns_slow.impact": "Every new site waits on resolution first, which feels like a stall",
    "rootcause.dns_slow.advice": "Flush the DNS cache or switch to a faster public DNS",

    "rootcause.web_break.title": "Web access breaks at a specific layer",
    "rootcause.web_break.impact": "Layered timing has already pinpointed the stage, so no guesswork is needed",
    "rootcause.web_break.advice": "Act on the layered figures below",

    "rootcause.mtu_mismatch.title": "MTU mismatch (large packets are dropped)",
    "rootcause.mtu_mismatch.impact": "Small packets pass while large ones vanish: home pages open but video and downloads stall",
    "rootcause.mtu_mismatch.advice": "Set MTU to the measured value",

    "rootcause.bufferbloat.title": "Latency rises sharply under download load",
    "rootcause.bufferbloat.impact": "Bandwidth is fine but latency spikes, which gaming and video calls feel first",
    "rootcause.bufferbloat.advice": "Enable SQM / QoS on the router, or limit large background transfers",

    "rootcause.firewall_off.title": "Windows Firewall is turned off",
    "rootcause.firewall_off.impact": "This is a security risk and does not cause the current connectivity problem",
    "rootcause.firewall_off.advice": "Turn the firewall back on",
}


def _inject(path: pathlib.Path, table: dict[str, str]) -> int:
    src = path.read_text(encoding="utf-8")
    added = {k: v for k, v in table.items() if f'"{k}"' not in src}
    if not added:
        return 0
    block = "\n".join(
        "    " + repr(k) + ": " + repr(v) + "," for k, v in added.items()
    )
    idx = src.rfind("}")
    src = (
        src[:idx]
        + "\n    # ---- v1.1.0 新增：场景化诊断 / 根因分析 / 网页分层 / 劫持检测 / 缓冲膨胀 ----\n"
        + block
        + "\n"
        + src[idx:]
    )
    path.write_text(src, encoding="utf-8")
    return len(added)


def main() -> int:
    n_zh = _inject(ROOT / "app" / "i18n_zh.py", ZH)
    n_en = _inject(ROOT / "app" / "i18n_en.py", EN)
    print(f"zh 新增 {n_zh} 条，en 新增 {n_en} 条")
    if n_zh != n_en:
        print("警告：两语言新增数量不一致，请检查")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
