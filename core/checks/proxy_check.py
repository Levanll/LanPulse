"""检测单元：系统代理设置。

「昨天好好的，今天浏览器完全打不开网页，但微信能发消息」——十有八九是代理软件
异常退出后 WinINET 代理没清干净：浏览器仍把流量发给 127.0.0.1:7890，而那里已经没人监听。

这里读注册表（只读）、探测代理端口是否有人监听、并对比 WinHTTP 的设置是否一致。
全程不修改任何设置，修复动作交给 proxy.reset。
"""
from __future__ import annotations

import socket
import sys
from dataclasses import dataclass

from ..context import DiagnosticContext
from ..i18n import t
from ..models import CheckResult, Metric, Severity

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

# 本地代理探测超时：本机回环上端口要么立即拒绝，要么立即接受，1 秒足够。
LOCAL_PROBE_TIMEOUT = 1.0
# 自动配置脚本（PAC）可达性探测：跨网段时要给足时间，3 秒。
PAC_PROBE_TIMEOUT = 3.0

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


@dataclass
class ProxySettings:
    enable: int = 0
    server: str = ""
    override: str = ""
    auto_config_url: str = ""


class ProxyCheck:
    check_id = "proxy"
    title = "check.proxy.title"
    category = "check.proxy.category"

    def run(self, ctx: DiagnosticContext) -> CheckResult:
        metrics: list[Metric] = []
        problems: list[str] = []
        advice: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        settings = _read_registry()
        if settings is None:
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=Severity.SKIP,
                summary=t("check.proxy.summary_skip"),
                summary_key="check.proxy.summary_skip",
                detail=t("check.proxy.detail_skip"),
                metrics=[Metric("metric.registry_path", REG_PATH, ok=False)],
                evidence={"registry": REG_PATH, "readable": False},
            )

        winhttp = _winhttp_proxy(ctx)
        endpoints = _parse_server(settings.server)

        metrics.append(Metric(
            "metric.proxy_enable",
            t("status.enabled") if settings.enable else t("status.disabled"),
            "ProxyEnable=1" if settings.enable else "ProxyEnable=0",
            ok=not settings.enable))
        if settings.server:
            metrics.append(Metric("metric.proxy_server", settings.server,
                                  t("check.proxy.note.endpoints", n=len(endpoints))))
        if settings.override:
            metrics.append(Metric("metric.proxy_override", _shorten(settings.override, 60)))
        if settings.auto_config_url:
            metrics.append(Metric("metric.auto_config_url",
                                  _shorten(settings.auto_config_url, 60)))
        metrics.append(Metric("metric.winhttp_proxy", winhttp or t("status.direct_unset")))

        evidence: dict = {
            "proxy_enable": settings.enable,
            "proxy_server": settings.server,
            "proxy_override": settings.override,
            "auto_config_url": settings.auto_config_url,
            "winhttp": winhttp,
            "endpoints": [{"host": h, "port": p} for h, p in endpoints],
        }

        # ---- 代理已关闭 ----
        if not settings.enable:
            if settings.auto_config_url:
                reachable, detail = _check_pac(settings.auto_config_url)
                metrics.append(Metric("metric.pac_reachable",
                                      t("status.yes") if reachable else t("status.no"),
                                      detail, ok=reachable))
                evidence["pac_reachable"] = reachable
                if not reachable:
                    severity = Severity.WARN
                    problems.append(t("check.proxy.problem.pac_fail",
                                      url=_shorten(settings.auto_config_url, 40)))
                    advice.append(t("check.proxy.advice.pac"))
                    actions.append("proxy.restore_auto")
            if severity is Severity.OK:
                return CheckResult(
                    check_id=self.check_id,
                    title=self.title,
                    category=self.category,
                    severity=Severity.OK,
                    summary=(t("check.proxy.summary_direct") if not settings.auto_config_url
                             else t("check.proxy.summary_auto_only")),
                    summary_key=("check.proxy.summary_direct"
                                 if not settings.auto_config_url
                                 else "check.proxy.summary_auto_only"),
                    detail=_detail_lines(settings, endpoints, winhttp),
                    metrics=metrics,
                    evidence=evidence,
                )
            return CheckResult(
                check_id=self.check_id,
                title=self.title,
                category=self.category,
                severity=severity,
                summary=t("sep.summary").join(problems),
                detail=_detail_lines(settings, endpoints, winhttp),
                metrics=metrics,
                advice=advice,
                action_ids=_unique(actions),
                evidence=evidence,
            )

        # ---- 代理已启用 ----
        local_dead: list[tuple[str, int]] = []
        local_alive: list[tuple[str, int]] = []
        remote: list[tuple[str, int]] = []
        for host, port in endpoints:
            if host in _LOOPBACK_HOSTS or host.startswith("127."):
                if _port_listening(host, port):
                    local_alive.append((host, port))
                    metrics.append(Metric(
                        t("metric.local_proxy", host=host, port=port),
                        t("status.listening"), t("check.proxy.note.proxy_running"), ok=True))
                else:
                    local_dead.append((host, port))
                    metrics.append(Metric(
                        t("metric.local_proxy", host=host, port=port),
                        t("status.no_listener"), t("check.proxy.note.proxy_dead"), ok=False))
            else:
                remote.append((host, port))
                metrics.append(Metric(
                    t("metric.remote_proxy", host=host, port=port),
                    t("value.remote"), t("check.proxy.note.remote")))

        evidence["local_alive"] = local_alive
        evidence["local_dead"] = local_dead
        evidence["remote"] = remote

        if local_dead:
            severity = Severity.CRITICAL
            dead_text = t("sep.list").join(f"{h}:{p}" for h, p in local_dead)
            problems.append(t("check.proxy.problem.dead", addrs=dead_text))
            advice.append(t("check.proxy.advice.dead"))
            actions.append("proxy.reset")
        elif not endpoints and not settings.auto_config_url:
            # ProxyEnable=1 但 ProxyServer 为空（且没有 PAC）：浏览器处于「代理已开、地址为空」
            # 的状态，任何请求都发不出去，和残留代理是同一类故障、同样的处理方式。
            # 有 PAC 时 WinINET 以 PAC 优先，空的手工代理不影响上网，不据此报错。
            severity = Severity.CRITICAL
            problems.append(t("check.proxy.problem.empty"))
            advice.append(t("check.proxy.advice.empty"))
            actions.append("proxy.reset")
        elif local_alive:
            severity = _worse(severity, Severity.INFO)
            problems.append(t("check.proxy.problem.local_alive",
                              addrs=t("sep.list").join(f"{h}:{p}" for h, p in local_alive)))
        elif remote:
            severity = _worse(severity, Severity.INFO)
            problems.append(t("check.proxy.problem.remote",
                              addrs=t("sep.list").join(f"{h}:{p}" for h, p in remote)))

        # ---- PAC 优先级更高时也要查 ----
        if settings.auto_config_url:
            reachable, detail = _check_pac(settings.auto_config_url)
            metrics.append(Metric("metric.pac_reachable",
                                  t("status.yes") if reachable else t("status.no"),
                                  detail, ok=reachable))
            evidence["pac_reachable"] = reachable
            if not reachable:
                severity = _worse(severity, Severity.WARN)
                problems.append(t("check.proxy.problem.pac_lost"))
                actions.append("proxy.restore_auto")

        # ---- WinHTTP 与 WinINET 不一致 ----
        if winhttp and _normalize_winhttp(winhttp) != _normalize_wininet(settings.server):
            severity = _worse(severity, Severity.INFO)
            metrics.append(Metric("metric.consistency", t("value.inconsistent"),
                                  t("check.proxy.note.consistency"), ok=False))
            advice.append(t("check.proxy.advice.consistency"))
        else:
            metrics.append(Metric("metric.consistency",
                                  t("value.consistent") if winhttp else t("status.unset"),
                                  ok=True))

        return CheckResult(
            check_id=self.check_id,
            title=self.title,
            category=self.category,
            severity=severity,
            # 问题态文案由多条具体事实拼接而成，不含固定模板，
            # 因此仅在正常态挂 key（切换语言时正常结论会跟随，问题详情保持原文）。
            summary_key=("check.proxy.summary_ok" if not problems else ""),
            summary=(t("sep.summary").join(problems) if problems
                     else t("check.proxy.summary_ok")),
            detail=_detail_lines(settings, endpoints, winhttp),
            metrics=metrics,
            advice=advice,
            action_ids=_unique(actions),
            evidence=evidence,
        )


# --------------------------------------------------------------------------- #
# 读取与探测
# --------------------------------------------------------------------------- #
def _read_registry() -> ProxySettings | None:
    """读 WinINET 代理设置。键不存在按「未启用代理」处理；仅导入失败时返回 None。"""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as key:
            return ProxySettings(
                enable=_reg_int(key, "ProxyEnable"),
                server=_reg_str(key, "ProxyServer"),
                override=_reg_str(key, "ProxyOverride"),
                auto_config_url=_reg_str(key, "AutoConfigURL"),
            )
    except OSError as exc:
        # 键不存在（全新账户）与权限不足都会走这里；前者等价于「没配代理」。
        if getattr(exc, "winerror", None) == 2:  # ERROR_FILE_NOT_FOUND
            return ProxySettings()
        return None


def _reg_int(key, name: str) -> int:
    import winreg

    try:
        return int(winreg.QueryValueEx(key, name)[0])
    except OSError:
        # 值不存在是常态（从未设置过代理）
        return 0


def _reg_str(key, name: str) -> str:
    import winreg

    try:
        return str(winreg.QueryValueEx(key, name)[0] or "")
    except OSError:
        return ""


def _parse_server(server: str) -> list[tuple[str, int]]:
    """解析 ProxyServer。支持 `host:port`、`http=host:port;https=host:port` 与无端口形式。"""
    if not server:
        return []
    out: list[tuple[str, int]] = []
    for chunk in server.replace(",", ";").split(";"):
        item = chunk.strip()
        if not item:
            continue
        if "=" in item:
            item = item.split("=", 1)[1].strip()
        host, _, port_text = item.rpartition(":")
        if not host:
            host, port_text = item, "80"
        try:
            port = int(port_text)
        except ValueError:
            host, port = item, 80
        if host:
            out.append((host, port))
    return out


def _port_listening(host: str, port: int) -> bool:
    """本机端口是否有程序在监听。连接成功即说明有服务；拒绝/超时都视为「没有」。"""
    try:
        with socket.create_connection((host, port), timeout=LOCAL_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def _check_pac(url: str) -> tuple[bool, str]:
    """检查 PAC 地址是否可用：file:// 看文件存在，http(s) 看能否建立连接。"""
    low = url.lower()
    if low.startswith("file://"):
        path = url[7:].lstrip("/").replace("/", "\\")
        import os

        exists = os.path.isfile(path)
        return exists, path if exists else t("err.file_missing", path=path)
    if low.startswith(("http://", "https://")):
        rest = url.split("://", 1)[1]
        host_port = rest.split("/", 1)[0]
        host, _, port_text = host_port.rpartition(":")
        if not host:
            host, port = host_port, 443 if low.startswith("https") else 80
        else:
            try:
                port = int(port_text)
            except ValueError:
                host, port = host_port, 80
        try:
            with socket.create_connection((host, port), timeout=PAC_PROBE_TIMEOUT):
                return True, f"{host}:{port} {t('status.connectable')}"
        except OSError as exc:
            return False, t("err.connect_failed", host=host, port=port,
                            err=type(exc).__name__)
    return False, t("err.unsupported_protocol", url=url[:40])


def _winhttp_proxy(ctx: DiagnosticContext) -> str:
    rc, out = ctx.cmd(("netsh", "winhttp", "show", "proxy"), timeout=15)
    if rc != 0 or not out:
        return ""
    return parse_winhttp_proxy(out)


def parse_winhttp_proxy(text: str) -> str:
    """从 `netsh winhttp show proxy` 输出里取出代理串；直连返回空串。"""
    for line in text.splitlines():
        low = line.lower()
        if "proxy server" in low or "代理服务器" in line:
            value = line.split(":", 1)[1].strip() if ":" in line else ""
            if not value or "direct" in value.lower() or "直接" in value:
                return ""
            return value
        if "direct access" in low or "直接访问" in line:
            return ""
    return ""


def _normalize_winhttp(value: str) -> str:
    return value.strip().lower().replace(" ", "")


def _normalize_wininet(value: str) -> str:
    if not value:
        return ""
    parts = []
    for chunk in value.replace(",", ";").split(";"):
        item = chunk.strip()
        if "=" in item:
            item = item.split("=", 1)[1]
        parts.append(item.strip().lower())
    return ";".join(p for p in parts if p)


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _detail_lines(settings: ProxySettings, endpoints: list[tuple[str, int]],
                  winhttp: str) -> str:
    lines = [
        t("check.proxy.detail.enable",
          value=t("status.enabled") if settings.enable else t("status.disabled")),
        t("check.proxy.detail.server", value=settings.server or t("status.empty_paren")),
        t("check.proxy.detail.override",
          value=settings.override or t("status.empty_all_proxy")),
        t("check.proxy.detail.pac",
          value=settings.auto_config_url or t("status.empty_paren")),
        t("check.proxy.detail.winhttp", value=winhttp or t("status.direct_access")),
    ]
    if endpoints:
        lines.append(t("check.proxy.detail.endpoints",
                       list=t("sep.list").join(f"{h}:{p}" for h, p in endpoints)))
    return "\n".join(lines)


def _worse(current: Severity, candidate: Severity) -> Severity:
    return candidate if candidate.rank > current.rank else current


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for item in items:
        if item not in seen:
            seen.append(item)
    return seen


__all__ = ["ProxyCheck", "ProxySettings", "parse_winhttp_proxy"]
