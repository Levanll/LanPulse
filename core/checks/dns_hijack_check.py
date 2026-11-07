"""检测单元：DNS 劫持 / 污染检测。

思路：同一个域名，分别向**当前系统 DNS**与**两个公共 DNS**查询。
如果系统 DNS 返回的 IP 与公共 DNS 都不一致，说明解析结果被改写。

这能发现两类问题：
  * 运营商 DNS 劫持（返回广告页 IP）
  * DNS 污染（返回错误地址导致网站打不开）

实现：自构造 DNS 报文，用 UDP 直连指定 DNS 服务器查询。
不走系统解析器——那样无法指定"问谁"，也就无法对比。
零第三方依赖，只用 socket + struct。
"""
from __future__ import annotations

import random
import socket
import struct
import time

from ..context import DiagnosticContext
from ..models import CheckResult, Metric, Severity

#: 查询超时（秒）
QUERY_TIMEOUT = 2.5

#: 用哪些域名做对比。选大站：它们有稳定的多 IP，且被劫持时特征明显。
PROBE_DOMAINS = ("www.baidu.com", "www.qq.com")

#: 作为"基准"的公共 DNS。取两个不同阵营，避免单一服务商本身出错。
REFERENCE_DNS = ("223.5.5.5", "119.29.29.29")


def _build_query(domain: str, txid: int) -> bytes:
    """构造 A 记录查询报文。"""
    header = struct.pack(">HHHHHH", txid, 0x0100, 1, 0, 0, 0)  # RD=1
    qname = b""
    for label in domain.split("."):
        raw = label.encode("ascii")
        qname += bytes([len(raw)]) + raw
    qname += b"\x00"
    question = qname + struct.pack(">HH", 1, 1)  # QTYPE=A, QCLASS=IN
    return header + question


def _parse_answers(payload: bytes) -> list[str]:
    """从响应里提取 A 记录 IP。解析失败返回空列表（不抛异常）。"""
    if len(payload) < 12:
        return []
    try:
        _txid, _flags, qdcount, ancount, _nscount, _arcount = struct.unpack(
            ">HHHHHH", payload[:12]
        )
    except struct.error:
        return []
    if ancount == 0:
        return []

    offset = 12
    # 跳过问题段
    for _ in range(qdcount):
        while offset < len(payload):
            length = payload[offset]
            if length == 0:
                offset += 1
                break
            if length & 0xC0 == 0xC0:      # 压缩指针
                offset += 2
                break
            offset += 1 + length
        offset += 4                          # QTYPE + QCLASS

    ips: list[str] = []
    for _ in range(ancount):
        if offset >= len(payload):
            break
        # 跳过 name（可能是压缩指针）
        if payload[offset] & 0xC0 == 0xC0:
            offset += 2
        else:
            while offset < len(payload) and payload[offset] != 0:
                offset += 1 + payload[offset]
            offset += 1
        if offset + 10 > len(payload):
            break
        try:
            rtype, _rclass, _ttl, rdlength = struct.unpack(">HHIH", payload[offset:offset + 10])
        except struct.error:
            break
        offset += 10
        if rtype == 1 and rdlength == 4 and offset + 4 <= len(payload):
            ips.append(".".join(str(b) for b in payload[offset:offset + 4]))
        offset += rdlength
    return ips


def query_dns(server: str, domain: str, timeout: float = QUERY_TIMEOUT) -> tuple[list[str], float | None]:
    """向指定 DNS 服务器查询 A 记录，返回 (IP 列表, 耗时毫秒)。"""
    txid = random.randint(0, 0xFFFF)
    packet = _build_query(domain, txid)
    start = time.perf_counter()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(packet, (server, 53))
        while True:
            try:
                data, _addr = sock.recvfrom(2048)
            except socket.timeout:
                return [], None
            if len(data) >= 2 and struct.unpack(">H", data[:2])[0] == txid:
                elapsed = (time.perf_counter() - start) * 1000.0
                return _parse_answers(data), elapsed
    except OSError:
        return [], None
    finally:
        sock.close()


class DnsHijackCheck:
    check_id = "dns_hijack"
    title = "check.dns_hijack.title"
    category = "check.dns_hijack.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        if not ctx.allow_probe:
            return CheckResult(
                check_id=self.check_id, title=self.title, category=self.category,
                severity=Severity.SKIP,
                summary="已关闭联网探测，跳过 DNS 劫持检测",
                summary_key="check.dns_hijack.summary_skipped",
            )

        # 当前系统 DNS 作为"被检对象"
        primary = ctx.primary
        system_dns = [d for d in (primary.dns_v4 if primary else []) if d]
        # 回环地址不参与对比（本机有 DNS 转发器时无法区分）
        system_dns = [d for d in system_dns if not d.startswith("127.")]

        if not system_dns:
            return CheckResult(
                check_id=self.check_id, title=self.title, category=self.category,
                severity=Severity.SKIP,
                summary="未配置手动 DNS 服务器，无法对比劫持情况",
                summary_key="check.dns_hijack.summary_no_dns",
                detail="自动获取 DNS 时由路由器决定解析器，本机看不到实际地址。\n"
                       "如需检测，可在「DNS 优化」页手动指定公共 DNS 后再体检。",
            )

        target = system_dns[0]
        metrics: list[Metric] = []
        mismatches: list[str] = []
        detail_lines: list[str] = []
        compared = 0

        for domain in PROBE_DOMAINS:
            mine, my_ms = query_dns(target, domain)
            refs: dict[str, list[str]] = {}
            for ref in REFERENCE_DNS:
                ips, _ms = query_dns(ref, domain)
                if ips:
                    refs[ref] = ips

            if not mine:
                detail_lines.append(f"• {domain}：当前 DNS {target} 无响应")
                metrics.append(Metric(
                    "metric.hijack_query", domain, f"{target} 无响应", ok=False))
                continue

            if not refs:
                detail_lines.append(f"• {domain}：公共 DNS 均无响应，无法对比")
                continue

            compared += 1
            # 判定：当前 DNS 返回的 IP 完全不在任何公共 DNS 的结果里 → 疑似改写
            ref_all: set[str] = set()
            for ips in refs.values():
                ref_all.update(ips)
            overlap = set(mine) & ref_all

            detail_lines.append(
                f"• {domain}：当前 {target} → {', '.join(mine[:2])}"
                f"（{my_ms:.0f}ms）；基准 → {', '.join(sorted(ref_all)[:2])}"
            )
            metrics.append(Metric(
                "metric.hijack_query", domain,
                f"{len(mine)} 个 A 记录，与基准重合 {len(overlap)} 个",
                ok=bool(overlap),
            ))

            if not overlap:
                mismatches.append(
                    f"{domain}：当前 DNS 返回 {', '.join(mine[:2])}，"
                    f"公共 DNS 返回 {', '.join(sorted(ref_all)[:2])}"
                )

        if compared == 0:
            severity = Severity.SKIP
            summary = "无法完成对比（DNS 查询均超时）"
            problems: list[str] = []
            advice: list[str] = []
        elif mismatches:
            severity = Severity.CRITICAL
            problems = [f"{len(mismatches)} 个域名解析结果与公共 DNS 不一致，疑似被劫持或污染"]
            advice = [
                "切换到可信的公共 DNS（如阿里 223.5.5.5）后重新体检确认",
                "若切换后仍不一致，检查 HOSTS 文件与安全软件",
            ]
            detail_lines.extend(f"  ⚠ {m}" for m in mismatches)
            summary = problems[0]
        else:
            severity = Severity.OK
            problems = []
            advice = []
            summary = f"DNS 解析结果与公共 DNS 一致（对比 {compared} 个域名），未发现劫持"

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            summary=summary,
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=["dns.set_public"] if mismatches else [],
            evidence={
                "system_dns": target,
                "reference_dns": list(REFERENCE_DNS),
                "domains": list(PROBE_DOMAINS),
                "mismatches": mismatches,
                "compared": compared,
            },
        )


__all__ = ["DnsHijackCheck", "query_dns", "_build_query", "_parse_answers"]
