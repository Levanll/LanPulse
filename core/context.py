"""单次诊断的共享上下文。

一次完整体检会运行 10+ 个检测单元，若每个单元都独立调用 PowerShell 采集网卡信息，
仅这一项就会产生数十秒的重复开销。DiagnosticContext 负责：
  * 惰性采集并缓存一次性快照（网卡 / hosts 原文 / 系统信息）；
  * 缓存命令输出，供多个检测单元复用；
  * 向检测单元提供“是否以管理员运行”等环境事实。

约定：上下文只做缓存与只读访问，绝不在此层修改系统。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from . import platform_win as pw
from . import region as region_mod
from .models import CheckResult


@dataclass
class DiagnosticContext:
    """一次体检的只读环境快照。"""

    elevated: bool = field(default_factory=pw.is_elevated)
    hostname: str = field(default_factory=pw.computer_name)
    os_name: str = field(default_factory=pw.os_display_name)
    build: int = field(default_factory=pw.windows_build)
    #: 用户固定的区域（settings.region）。auto 表示自动识别。
    region_override: str = region_mod.REGION_AUTO
    #: 是否允许发起联网探测。关闭后所有需要外网的检测项跳过，只看本地配置。
    allow_probe: bool = True
    #: 超时倍数。网络很慢的地区（卫星、跨境）可用 2.0~4.0。
    timeout_scale: float = 1.0

    _adapters: list[pw.AdapterInfo] | None = None
    _hosts_text: str | None = None
    _cache: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ---- 惰性采集 ----
    @property
    def adapters(self) -> list[pw.AdapterInfo]:
        with self._lock:
            if self._adapters is None:
                self._adapters = pw.collect_adapters()
            return self._adapters

    def refresh_adapters(self) -> list[pw.AdapterInfo]:
        """强制重新采集网卡状态，丢弃缓存。

        为什么修复链路必须在备份前调用它：这个缓存是为"一次体检内不重复采集"
        设计的，而体检可能已经过去几分钟、甚至用户中途手动改过配置。
        备份的语义是"记录**被修改的那一刻**的真实状态"，拿体检时的旧快照去
        备份，回滚就会回到一个用户早已不处于的过去。

        真实事故（2026-11-10 闭环实测暴露）：mtu.optimize 的 backup() 读到
        缓存里的 1492，而实际已是 1400（被前一步构造改动），回滚便"恢复"到
        1492 —— 既不是用户原值，也不是被修的值，属于凭空写了一笔。
        """
        with self._lock:
            self._adapters = pw.collect_adapters()
            return self._adapters

    @property
    def primary(self) -> pw.AdapterInfo | None:
        return pw.primary_adapter(self.adapters)

    @property
    def hosts_text(self) -> str:
        with self._lock:
            if self._hosts_text is None:
                self._hosts_text = pw.read_text_file(pw.HOSTS_PATH)
            return self._hosts_text

    # ---- 通用缓存 ----
    def cached(self, key: str, producer: Callable[[], Any]) -> Any:
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        value = producer()
        with self._lock:
            self._cache[key] = value
        return value

    def cmd(self, argv: tuple[str, ...], *, timeout: float = 20.0) -> tuple[int, str]:
        """带缓存的命令执行，避免同一条 netsh 在多个检测单元里重复跑。

        timeout 会自动乘以 timeout_scale，这样慢速网络地区只需调设置，
        不必逐处改常量。
        """
        scaled = max(1.0, timeout * self.timeout_scale)
        key = f"cmd:{scaled:.1f}:" + " ".join(argv)
        return self.cached(key, lambda: pw.run_cmd(list(argv), timeout=scaled))

    def ps_json(self, key: str, script: str, *, timeout: float = 30.0) -> Any:
        scaled = max(1.0, timeout * self.timeout_scale)
        return self.cached("ps:" + key, lambda: pw.run_ps_json(script, timeout=scaled))

    # ---- 区域剖面 ----
    @property
    def region_key(self) -> str:
        """当前生效的区域标识。用户固定则用之，否则自动识别并缓存结果。"""
        if self.region_override and self.region_override != region_mod.REGION_AUTO:
            return self.region_override

        def _detect() -> str:
            key, evidence = region_mod.detect_region(probe=self.allow_probe)
            self._cache["region_evidence"] = evidence
            return key

        return self.cached("region:auto", _detect)

    @property
    def region_evidence(self) -> dict[str, Any]:
        # 先触发一次识别，保证 evidence 已填充
        _ = self.region_key
        return dict(self._cache.get("region_evidence") or {})

    @property
    def profile(self) -> region_mod.RegionProfile:
        """当前区域的探测集与阈值。所有地域相关的探测目标都从这里取。"""
        return region_mod.get_profile(self.region_key)

    def env(self) -> region_mod.NetworkEnvironment:
        """网络环境画像（是否门户认证、VPN、仅 IPv6 等）。"""
        proxy_on = bool(self._cache.get("proxy_enabled", False))
        return self.cached(
            "network_env",
            lambda: region_mod.detect_network_environment(
                self.adapters, proxy_enabled=proxy_on, probe=self.allow_probe
            ),
        )


__all__ = ["DiagnosticContext"]
