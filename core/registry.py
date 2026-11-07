"""检测单元注册表。

每个检测单元是一个实现了 Check 协议的对象：
    check_id: 全局唯一且稳定的字符串（报告、修复建议、UI 均以此关联）
    title / category: 展示用
    run(ctx) -> CheckResult

新增检测维度只需写一个模块 + 在 CHECKS 里登记，UI 与报告自动出现，
无需改动任何其它代码——这是“可扩展检测单元”约束的落地方式。
"""
from __future__ import annotations

import time
import traceback
from typing import Protocol, Sequence

from .context import DiagnosticContext
from .i18n import t
from .models import CheckResult, Severity


class Check(Protocol):
    check_id: str
    title: str
    category: str

    def run(self, ctx: DiagnosticContext) -> CheckResult: ...


def run_check(check: Check, ctx: DiagnosticContext) -> CheckResult:
    """执行单个检测单元，统一计时与异常隔离。

    单个检测单元的崩溃不得中断整轮体检：捕获后转为 severity=SKIP 的结果，
    并把异常原文放进 error 字段，报告里可见，不静默。
    """
    started = time.time()
    try:
        result = check.run(ctx)
    except Exception as exc:  # noqa: BLE001 - 检测单元必须彼此隔离
        result = CheckResult(
            check_id=check.check_id,
            title=check.title,
            category=check.category,
            severity=Severity.SKIP,
            summary=t("check.registry.summary_failed"),
            detail=t("check.registry.detail_failed", err=exc),
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc(limit=3)}",
        )
    result.duration_ms = int((time.time() - started) * 1000)
    return result


def load_checks() -> list[Check]:
    """按展示顺序返回全部检测单元。"""
    from .checks import (
        adapter_check,
        ip_check,
        gateway_check,
        dns_server_check,
        dns_resolve_check,
        hosts_check,
        proxy_check,
        tcp_check,
        mtu_check,
        firewall_check,
        connectivity_check,
        web_timing_check,
        dns_hijack_check,
        bufferbloat_check,
    )

    return [
        adapter_check.AdapterCheck(),
        ip_check.IpConfigCheck(),
        gateway_check.GatewayCheck(),
        dns_server_check.DnsServerCheck(),
        dns_resolve_check.DnsResolveCheck(),
        hosts_check.HostsCheck(),
        proxy_check.ProxyCheck(),
        tcp_check.TcpParamCheck(),
        mtu_check.MtuCheck(),
        firewall_check.FirewallCheck(),
        connectivity_check.ConnectivityCheck(),
        # v1.1.0 新增：把"为什么打不开网页/为什么游戏卡"这类
        # 用户真正关心的问题做成独立检测项
        web_timing_check.WebTimingCheck(),
        dns_hijack_check.DnsHijackCheck(),
        bufferbloat_check.BufferbloatCheck(),
    ]


#: 复刻"23 个模块"那种清单式能力的思路，但保持每项独立可测。
#: 这里登记各检测项的预估耗时等级，供 UI 在选择场景时提示用户。
CHECK_COST = {
    "adapter": "slow",          # 需要 PowerShell 采集
    "ip": "fast",
    "gateway": "slow",          # ping + route
    "dns_server": "fast",
    "dns_resolve": "slow",      # 真实 DNS 查询
    "hosts": "fast",
    "proxy": "fast",
    "tcp": "fast",
    "mtu": "slow",              # DF ping 二分
    "firewall": "fast",
    "connectivity": "slow",     # ping + TCP 握手
    "web_timing": "slow",       # 分层计时
    "dns_hijack": "slow",       # 多路 DNS 对比
    "bufferbloat": "very_slow",  # 需要真实下载负载
}


def run_all(ctx: DiagnosticContext, checks: Sequence[Check] | None = None,
            progress: object = None) -> list[CheckResult]:
    """顺序执行全部检测单元。

    顺序执行而非并发：PowerShell / netsh 并发调用在部分机器上会互相拖慢，
    而单轮体检（含 DNS 探测与连通性测试）的目标耗时为 5-8 秒，用户可接受。
    progress 支持一个可调用对象 (done, total, check) -> None，用于驱动 UI 进度。
    """
    checks = list(checks if checks is not None else load_checks())
    results: list[CheckResult] = []
    total = len(checks)
    for idx, check in enumerate(checks):
        if progress is not None and callable(progress):
            progress(idx, total, check)  # type: ignore[operator]
        results.append(run_check(check, ctx))
    if progress is not None and callable(progress):
        progress(total, total, checks[-1] if checks else None)  # type: ignore[operator]
    return results


__all__ = ["Check", "run_check", "load_checks", "run_all"]
