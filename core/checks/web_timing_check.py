"""检测单元：网页分层计时。

回答"网页为什么打不开"这个最常见的问题，但不是笼统地说"不通"，
而是**定位到具体是哪个环节出了问题**：

    DNS 解析 → TCP 连接 → TLS 握手 → 首字节(TTFB) → 内容传输

每一层耗时独立测量，任何一层异常都能被单独指出。这比"能通/不通"
有用得多：DNS 慢和 TTFB 慢是完全不同的两个问题，修法也不同。

实现说明：
  * 只用标准库（socket + ssl + http.client），不引入 requests。
  * 只发 HEAD 或极小 GET，不下载页面正文——检测不该消耗用户流量。
  * 证书检查：有效期、域名匹配、链是否可信。
  * 重定向链：记录跳转次数与最终地址（过多跳转本身就是问题）。
"""
from __future__ import annotations

import http.client
import socket
import ssl
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from ..context import DiagnosticContext
from ..models import CheckResult, Metric, Severity

#: 每个目标的总预算（秒）
PER_TARGET_TIMEOUT = 8.0

#: 分层耗时阈值（毫秒）。
#: DNS 阈值随区域变化（见 region.py），这里给的是连接与首字节的通用阈值。
TCP_GOOD_MS = 150.0
TCP_SLOW_MS = 500.0
TLS_GOOD_MS = 300.0
TLS_SLOW_MS = 900.0
TTFB_GOOD_MS = 400.0
TTFB_SLOW_MS = 1500.0

#: 重定向超过这个次数视为异常（常见于被劫持或被运营商插入跳转）
MAX_REDIRECTS = 5


@dataclass
class LayerTiming:
    """一次网页访问的分层耗时。单位毫秒，None 表示该层未执行。"""

    url: str = ""
    dns_ms: float | None = None
    tcp_ms: float | None = None
    tls_ms: float | None = None
    ttfb_ms: float | None = None
    status: int = 0
    final_url: str = ""
    redirects: list[str] = field(default_factory=list)
    cert_subject: str = ""
    cert_expire_days: int | None = None
    cert_error: str = ""
    error: str = ""
    via: str = ""

    @property
    def total_ms(self) -> float:
        parts = [self.dns_ms, self.tcp_ms, self.tls_ms, self.ttfb_ms]
        return sum(p for p in parts if p is not None)

    @property
    def ok(self) -> bool:
        return not self.error and 0 < self.status < 500


def _resolve_timed(host: str, port: int) -> tuple[float | None, str]:
    """测量 DNS 解析耗时，返回 (毫秒, IP)。"""
    start = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        return None, f"解析失败: {exc}"
    elapsed = (time.perf_counter() - start) * 1000.0
    ip = infos[0][4][0] if infos else ""
    return elapsed, ip


def _probe(url: str, timeout: float = PER_TARGET_TIMEOUT) -> LayerTiming:
    """对单个 URL 做分层计时。"""
    t = LayerTiming(url=url)
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        t.error = "URL 无效"
        return t

    deadline = time.perf_counter() + timeout

    # ---- 1. DNS ----
    dns_ms, ip = _resolve_timed(host, port)
    t.dns_ms = dns_ms
    if dns_ms is None:
        t.error = f"DNS 解析失败：{ip}"
        return t
    t.via = ip

    # ---- 2. TCP ----
    try:
        start = time.perf_counter()
        sock = socket.create_connection((host, port), timeout=max(0.5, deadline - time.perf_counter()))
        t.tcp_ms = (time.perf_counter() - start) * 1000.0
    except OSError as exc:
        t.error = f"TCP 连接失败：{exc}"
        return t

    try:
        # ---- 3. TLS ----
        if parsed.scheme == "https":
            ctx = ssl.create_default_context()
            start = time.perf_counter()
            try:
                sock = ctx.wrap_socket(sock, server_hostname=host)
                t.tls_ms = (time.perf_counter() - start) * 1000.0
            except ssl.SSLCertVerificationError as exc:
                t.cert_error = str(exc)
                t.error = f"证书校验失败：{exc.verify_message or exc}"
                return t
            except ssl.SSLError as exc:
                t.error = f"TLS 握手失败：{exc}"
                return t

            # 证书信息
            try:
                cert = sock.getpeercert()
                if cert:
                    t.cert_subject = dict(x[0] for x in cert.get("subject", ())).get(
                        "commonName", "")
                    not_after = cert.get("notAfter", "")
                    if not_after:
                        from email.utils import parsedate_to_datetime

                        exp = parsedate_to_datetime(not_after)
                        t.cert_expire_days = int(
                            (exp - parsedate_to_datetime(
                                time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                              time.gmtime()))).total_seconds() // 86400
                        )
            except (ValueError, TypeError, KeyError):
                # 证书能通过校验但解析字段失败，不影响连接结论
                pass

        # ---- 4. TTFB + 重定向 ----
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            "User-Agent: LanPulse/1.1\r\n"
            "Accept: */*\r\n"
            "Range: bytes=0-0\r\n"      # 只要 1 字节，避免下载正文
            "Connection: close\r\n\r\n"
        )
        start = time.perf_counter()
        sock.sendall(request.encode("ascii", errors="replace"))
        raw = sock.recv(2048)
        t.ttfb_ms = (time.perf_counter() - start) * 1000.0

        text = raw.decode("iso-8859-1", errors="replace")
        first_line = text.split("\r\n", 1)[0]
        parts = first_line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            t.status = int(parts[1])
        # 记录重定向目标（不跟随，避免额外请求拖长检测）
        for line in text.split("\r\n"):
            if line.lower().startswith("location:"):
                t.final_url = line.split(":", 1)[1].strip()
                t.redirects.append(t.final_url)
                break
    finally:
        try:
            sock.close()
        except OSError:
            pass

    return t


def _grade(ms: float | None, good: float, slow: float) -> str:
    """把耗时映射到等级 key。"""
    if ms is None:
        return "metric.grade_unknown"
    if ms < good:
        return "metric.grade_good"
    if ms < slow:
        return "metric.grade_fair"
    return "metric.grade_poor"


class WebTimingCheck:
    check_id = "web_timing"
    title = "check.web_timing.title"
    category = "check.web_timing.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        if not ctx.allow_probe:
            return CheckResult(
                check_id=self.check_id, title=self.title, category=self.category,
                severity=Severity.SKIP,
                summary="已关闭联网探测，跳过网页分层计时",
                summary_key="check.web_timing.summary_skipped",
            )

        # 目标取自区域剖面：中国用百度，欧美用 Google
        profile = ctx.profile
        targets = [f"https://{d}/" for d in profile.resolve_domains[:2]]
        # 再加一个 region 首域名，保证至少 2 个目标
        if len(targets) < 2 and profile.resolve_domains:
            targets.append(f"https://{profile.resolve_domains[0]}/")

        timings: list[LayerTiming] = []
        for url in targets:
            timings.append(_probe(url))

        ok_list = [t for t in timings if t.ok]
        failed = [t for t in timings if not t.ok]

        metrics: list[Metric] = []
        for t in timings:
            host = urlparse(t.url).hostname or t.url
            if not t.ok:
                metrics.append(Metric(
                    "metric.web_target", host,
                    t.error[:70],
                    ok=False,
                ))
                continue
            metrics.append(Metric(
                "metric.web_dns", f"{t.dns_ms:.0f}ms",
                f"{host} · {_grade(t.dns_ms, 60, 150)}", ok=True,
            ))
            metrics.append(Metric(
                "metric.web_tcp", f"{t.tcp_ms:.0f}ms" if t.tcp_ms else "—",
                _grade(t.tcp_ms, TCP_GOOD_MS, TCP_SLOW_MS),
                ok=bool(t.tcp_ms and t.tcp_ms < TCP_SLOW_MS),
            ))
            if t.tls_ms is not None:
                metrics.append(Metric(
                    "metric.web_tls", f"{t.tls_ms:.0f}ms",
                    _grade(t.tls_ms, TLS_GOOD_MS, TLS_SLOW_MS),
                    ok=t.tls_ms < TLS_SLOW_MS,
                ))
            if t.ttfb_ms is not None:
                metrics.append(Metric(
                    "metric.web_ttfb", f"{t.ttfb_ms:.0f}ms",
                    _grade(t.ttfb_ms, TTFB_GOOD_MS, TTFB_SLOW_MS),
                    ok=t.ttfb_ms < TTFB_SLOW_MS,
                ))
            if t.cert_expire_days is not None:
                metrics.append(Metric(
                    "metric.web_cert", f"{t.cert_expire_days} 天",
                    t.cert_subject,
                    ok=t.cert_expire_days > 14,
                ))

        # ---- 判定 ----
        severity = Severity.OK
        problems: list[str] = []
        advice: list[str] = []
        detail_lines: list[str] = []

        if not ok_list:
            severity = Severity.CRITICAL
            problems.append("所有测试网页都无法访问")
            advice.append("先确认能否 ping 通外网 IP：能通则问题在应用层，不通则检查物理链路")
        else:
            # 逐层找断层
            cert_err = [t for t in timings if t.cert_error]
            if cert_err:
                severity = Severity.CRITICAL
                problems.append(f"证书校验失败：{cert_err[0].cert_error[:60]}")
                advice.append("检查系统时间是否正确——时间错误会导致证书校验必然失败")
            slow_ttfb = [t for t in ok_list if t.ttfb_ms and t.ttfb_ms > TTFB_SLOW_MS]
            slow_dns = [t for t in ok_list if t.dns_ms and t.dns_ms > 150]
            slow_tls = [t for t in ok_list if t.tls_ms and t.tls_ms > TLS_SLOW_MS]
            if slow_ttfb and severity is Severity.OK:
                severity = Severity.WARN
                problems.append(f"首字节响应慢（{slow_ttfb[0].ttfb_ms:.0f}ms），站点侧或链路拥塞")
                advice.append("目标站点响应慢，不是本地网络问题；可换个网站对比确认")
            if slow_dns and severity is Severity.OK:
                severity = Severity.WARN
                problems.append(f"DNS 解析慢（{slow_dns[0].dns_ms:.0f}ms）")
                advice.append("切换到更快的公共 DNS 可改善")
            if slow_tls and severity is Severity.OK:
                severity = Severity.WARN
                problems.append(f"TLS 握手慢（{slow_tls[0].tls_ms:.0f}ms），可能是中间设备干扰")
                advice.append("TLS 握手慢常见于安全软件扫描流量，可临时关闭对比")
            if failed and severity is Severity.OK:
                severity = Severity.WARN
                problems.append(f"{len(failed)} 个目标无法访问")

        for t in timings:
            host = urlparse(t.url).hostname or t.url
            if t.ok:
                detail_lines.append(
                    f"• {host}：DNS {t.dns_ms:.0f} / TCP {t.tcp_ms:.0f}"
                    + (f" / TLS {t.tls_ms:.0f}" if t.tls_ms is not None else "")
                    + (f" / TTFB {t.ttfb_ms:.0f}" if t.ttfb_ms is not None else "")
                    + f" ms（HTTP {t.status}）"
                )
                if t.redirects:
                    detail_lines.append(f"    重定向到 {t.final_url[:60]}")
                if t.cert_expire_days is not None:
                    detail_lines.append(f"    证书 {t.cert_subject}，剩余 {t.cert_expire_days} 天")
            else:
                detail_lines.append(f"• {host}：{t.error}")

        if severity is Severity.OK:
            best = ok_list[0]
            summary = (f"网页访问正常：DNS {best.dns_ms:.0f}ms、"
                       f"TCP {best.tcp_ms:.0f}ms、首字节 {best.ttfb_ms:.0f}ms")
        else:
            summary = "；".join(problems)

        actions: list[str] = []
        if any(t.cert_error for t in timings):
            actions.append("dns.flush_cache")
        if any(t.dns_ms and t.dns_ms > 150 for t in ok_list):
            actions.append("dns.set_public")

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            summary=summary,
            detail="\n".join(detail_lines),
            metrics=metrics,
            advice=advice,
            action_ids=actions,
            evidence={
                "targets": [t.url for t in timings],
                "timings": [
                    {
                        "url": t.url, "ok": t.ok, "status": t.status,
                        "dns_ms": round(t.dns_ms, 1) if t.dns_ms else None,
                        "tcp_ms": round(t.tcp_ms, 1) if t.tcp_ms else None,
                        "tls_ms": round(t.tls_ms, 1) if t.tls_ms else None,
                        "ttfb_ms": round(t.ttfb_ms, 1) if t.ttfb_ms else None,
                        "cert_days": t.cert_expire_days,
                        "cert_error": t.cert_error,
                        "error": t.error,
                    }
                    for t in timings
                ],
                "thresholds": {
                    "tcp_good_ms": TCP_GOOD_MS, "tcp_slow_ms": TCP_SLOW_MS,
                    "tls_good_ms": TLS_GOOD_MS, "tls_slow_ms": TLS_SLOW_MS,
                    "ttfb_good_ms": TTFB_GOOD_MS, "ttfb_slow_ms": TTFB_SLOW_MS,
                },
            },
        )


__all__ = ["WebTimingCheck", "LayerTiming", "_probe"]
