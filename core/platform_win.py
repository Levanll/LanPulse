"""Windows 原生能力适配层。

设计原则：
1. 只调用 Windows 自带能力（IP Helper API / WMI-CIM / netsh / ipconfig / 注册表），
   不依赖任何第三方系统组件，保证在 Windows 10/11 及 Server 2016+ 上可用。
2. 所有系统输出统一解码策略：先 UTF-8 严格解码，失败回退系统 ANSI 代码页（中文系统为 GBK）。
   这是中文 Windows 上混用 code page 的实际解法，不吞异常、不静默替换成乱码。
3. 所有子进程调用都带超时，超时视为该检测单元失败，由上层标记为 SKIP 而非崩溃。
"""
from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

CREATE_NO_WINDOW = 0x08000000
IS_WINDOWS = sys.platform == "win32"


# --------------------------------------------------------------------------- #
# 进程与编码
# --------------------------------------------------------------------------- #
def decode_console(data: bytes) -> str:
    """解码控制台程序输出。UTF-8 优先，回退 OEM/ANSI 代码页。"""
    if not data:
        return ""
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    # 中文 Windows 上 netsh / ipconfig 实际输出为 GBK(936)
    for enc in ("gbk", "cp936", "mbcs"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def run_cmd(
    argv: Sequence[str],
    *,
    timeout: float = 20.0,
    cwd: str | None = None,
) -> tuple[int, str]:
    """执行命令，返回 (returncode, 解码后的合并输出)。不抛异常，用返回码表达失败。"""
    try:
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            timeout=timeout,
            cwd=cwd,
            creationflags=CREATE_NO_WINDOW if IS_WINDOWS else 0,
        )
    except subprocess.TimeoutExpired:
        return -1, f"[超时] 命令执行超过 {timeout:.0f} 秒: {' '.join(argv)}"
    except (OSError, ValueError) as exc:
        return -2, f"[无法执行] {' '.join(argv)}: {exc}"
    out = decode_console(proc.stdout) + decode_console(proc.stderr)
    return proc.returncode, out.strip()


_PS_PREFIX = (
    "$ErrorActionPreference='SilentlyContinue';"
    "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
    "$OutputEncoding=[System.Text.Encoding]::UTF8;"
)


def run_ps(script: str, *, timeout: float = 30.0) -> tuple[int, str]:
    """执行 PowerShell 脚本。自动附加 UTF-8 输出与静默错误策略。"""
    exe = _powershell_exe()
    if not exe:
        return -3, "[环境不支持] 未找到 PowerShell"
    return run_cmd(
        [exe, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", _PS_PREFIX + script],
        timeout=timeout,
    )


def run_ps_json(script: str, *, timeout: float = 30.0) -> Any:
    """执行 PowerShell 并把结果解析为 Python 对象。

    PowerShell 对单元素结果不输出数组，此处用 @() 包裹结果保证结构稳定；
    ConvertTo-Json 的深度固定为 6，避免默认深度 2 截断嵌套对象。
    """
    wrapped = f"$r = @({script}); if ($r.Count -eq 0) {{ '[]' }} else {{ $r | ConvertTo-Json -Depth 6 -Compress }}"
    rc, out = run_ps(wrapped, timeout=timeout)
    if rc != 0:
        raise RuntimeError(f"PowerShell 执行失败(rc={rc}): {out[:400]}")
    text = out.strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"PowerShell 输出无法解析为 JSON: {exc}; 原文={text[:300]}") from exc
    return data


_ps_exe_cache: str | None = None


def _powershell_exe() -> str | None:
    global _ps_exe_cache
    if _ps_exe_cache is not None:
        return _ps_exe_cache
    for name in ("powershell.exe", "pwsh.exe"):
        for base in (
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0"),
        ):
            cand = os.path.join(base, name)
            if os.path.isfile(cand):
                _ps_exe_cache = cand
                return cand
        found = _which(name)
        if found:
            _ps_exe_cache = found
            return found
    _ps_exe_cache = ""
    return None


def _which(name: str) -> str | None:
    for ext in ("", ".exe", ".cmd", ".bat"):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            if not d:
                continue
            cand = os.path.join(d, name + ext)
            if os.path.isfile(cand):
                return cand
    return None


# --------------------------------------------------------------------------- #
# 提权状态
# --------------------------------------------------------------------------- #
def is_elevated() -> bool:
    """当前进程是否以管理员身份运行。失败时视为未提权（保守判断）。"""
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def is_admin_account() -> bool:
    """当前登录账户是否属于 Administrators 组（决定能否通过 UAC 提权）。"""
    rc, out = run_cmd(["whoami", "/groups"], timeout=10)
    if rc != 0:
        return False
    return "S-1-5-32-544" in out


# --------------------------------------------------------------------------- #
# 系统信息
# --------------------------------------------------------------------------- #
def computer_name() -> str:
    return os.environ.get("COMPUTERNAME", "UNKNOWN-PC")


def os_display_name() -> str:
    try:
        import platform

        return f"{platform.system()} {platform.release()} {platform.version()}"
    except Exception:  # pragma: no cover - 平台信息不可用时仅影响展示
        return "Windows"


def windows_build() -> int:
    return int(os.environ.get("OS_BUILD") or _build_from_registry())


def _build_from_registry() -> int:
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        ) as key:
            return int(winreg.QueryValueEx(key, "CurrentBuildNumber")[0])
    except (OSError, ValueError, ImportError):
        return 0


def now() -> float:
    return time.time()


# --------------------------------------------------------------------------- #
# 网卡快照（一次采集，多处复用）
# --------------------------------------------------------------------------- #
@dataclass
class AdapterInfo:
    """一块网络适配器的静态+动态状态。"""

    name: str
    description: str = ""
    status: str = ""
    link_speed: str = ""
    mac: str = ""
    if_index: int = 0
    interface_guid: str = ""
    media_type: str = ""
    ipv4: list[str] = field(default_factory=list)
    ipv6: list[str] = field(default_factory=list)
    prefix_len: int = 0
    gateway: str = ""
    dns_v4: list[str] = field(default_factory=list)
    dns_v6: list[str] = field(default_factory=list)
    dhcp: bool = False
    #: IP 层 MTU（NlMtu）。这是 netsh 读写的那一个，也是决定"能不能过大包"的那一个。
    #: **所有修复动作、检测判定、备份与回滚都必须用它**，不能用 link_mtu。
    mtu: int = 0
    #: 链路层 MTU（NDIS MtuSize）。由驱动决定，通常 ≥ ip MTU，改不动也不该改。
    #: 仅用于诊断展示：两者不等说明上层做了封装（VPN/PPPoE/隧道）。
    link_mtu: int = 0
    is_virtual: bool = False

    @property
    def up(self) -> bool:
        return self.status.lower() == "up"

    @property
    def primary_ipv4(self) -> str:
        return self.ipv4[0] if self.ipv4 else ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "link_speed": self.link_speed,
            "mac": self.mac,
            "if_index": self.if_index,
            "interface_guid": self.interface_guid,
            "ipv4": self.ipv4,
            "ipv6": self.ipv6,
            "prefix_len": self.prefix_len,
            "gateway": self.gateway,
            "dns_v4": self.dns_v4,
            "dns_v6": self.dns_v6,
            "dhcp": self.dhcp,
            "mtu": self.mtu,
            "link_mtu": self.link_mtu,
            "is_virtual": self.is_virtual,
        }


# 视为虚拟/隧道适配器的接口描述关键字。这些适配器不应参与 DNS 优化决策，
# 也不应被自动修改，避免破坏 VPN / 虚拟机的既定配置。
_VIRTUAL_HINTS = (
    "vmware", "virtualbox", "hyper-v", "vethernet", "tap-", "tun", "wintun",
    "loopback", "pseudo", "vpn", "wireguard", "zerotier", "docker", "wsl",
    "qmtap", "verykuai", "npcap", "bluetooth",
)


_ADAPTER_PS = r"""
$adapters = Get-NetAdapter -ErrorAction SilentlyContinue |
    Select-Object Name, InterfaceDescription, Status, LinkSpeed, MacAddress, ifIndex, InterfaceGuid, MtuSize, MediaType
$addrs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Select-Object InterfaceIndex, IPAddress, PrefixLength, PrefixOrigin, SuffixOrigin
$addrs6 = Get-NetIPAddress -AddressFamily IPv6 -ErrorAction SilentlyContinue |
    Select-Object InterfaceIndex, IPAddress, PrefixOrigin, AddressState
$gws = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
    Select-Object InterfaceIndex, NextHop, RouteMetric, InterfaceMetric
$dns = Get-DnsClientServerAddress -ErrorAction SilentlyContinue |
    Select-Object InterfaceIndex, AddressFamily, ServerAddresses
# NlMtu 是 IP 层 MTU，正是 netsh interface ipv4 set subinterface mtu= 读写的那个。
# Get-NetAdapter 的 MtuSize 是 NDIS 链路层值，两者在有封装时并不相等
# （本机实测以太网 MtuSize=1500 / NlMtu=1492）。修复动作必须以 NlMtu 为准，
# 否则会出现"写入 1492 却读回 1500，verify 永久失败，回滚再把 1492 改成 1500"。
$nlmtu = Get-NetIPInterface -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Select-Object InterfaceIndex, NlMtu
foreach ($a in $adapters) {
    $a | Add-Member -NotePropertyName Ips -NotePropertyValue @($addrs | Where-Object { $_.InterfaceIndex -eq $a.ifIndex } ) -Force
    $a | Add-Member -NotePropertyName Ips6 -NotePropertyValue @($addrs6 | Where-Object { $_.InterfaceIndex -eq $a.ifIndex } ) -Force
    $nl = $nlmtu | Where-Object { $_.InterfaceIndex -eq $a.ifIndex } | Select-Object -First 1
    $a | Add-Member -NotePropertyName NlMtu -NotePropertyValue $(if ($nl) { $nl.NlMtu } else { 0 }) -Force
    $a | Add-Member -NotePropertyName Gateway -NotePropertyValue (@($gws | Where-Object { $_.InterfaceIndex -eq $a.ifIndex }) | Sort-Object InterfaceMetric | Select-Object -First 1) -Force
    $a | Add-Member -NotePropertyName Dns -NotePropertyValue @($dns | Where-Object { $_.InterfaceIndex -eq $a.ifIndex }) -Force
}
$adapters
"""


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def collect_adapters() -> list[AdapterInfo]:
    """通过 CIM 一次性采集全部适配器信息（含 IP / 网关 / DNS）。"""
    raw = run_ps_json(_ADAPTER_PS, timeout=40)
    items = _as_list(raw)
    out: list[AdapterInfo] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        desc = (it.get("InterfaceDescription") or "").strip()
        name = (it.get("Name") or "").strip()
        blob = f"{name} {desc}".lower()
        ips = _as_list(it.get("Ips"))
        ipv4 = [str(i.get("IPAddress")) for i in ips if isinstance(i, dict) and i.get("IPAddress")]
        prefix = int(ips[0].get("PrefixLength") or 0) if ips and isinstance(ips[0], dict) else 0
        # IPv6 地址只取"首选"状态，排除 tentative/deprecated 的临时地址
        ipv6 = [
            str(i.get("IPAddress"))
            for i in _as_list(it.get("Ips6"))
            if isinstance(i, dict)
            and i.get("IPAddress")
            and str(i.get("AddressState") or "Preferred").lower() != "tentative"
        ]
        gw_obj = it.get("Gateway")
        gateway = ""
        if isinstance(gw_obj, dict) and gw_obj.get("NextHop") not in (None, "0.0.0.0", ""):
            gateway = str(gw_obj.get("NextHop"))
        dns_v4: list[str] = []
        dns_v6: list[str] = []
        for d in _as_list(it.get("Dns")):
            if not isinstance(d, dict):
                continue
            fam = d.get("AddressFamily")
            servers = [str(s) for s in _as_list(d.get("ServerAddresses")) if s]
            if str(fam) in ("2", "IPv4", "InterNetwork"):
                dns_v4 = servers
            elif str(fam) in ("23", "IPv6", "InterNetworkV6"):
                dns_v6 = servers
        # NlMtu 优先；取不到时退回 MtuSize 并记 0，由调用方决定是否可信。
        # 不能把 MtuSize 当作 IP MTU 用——那正是本模块曾经的缺陷。
        nl_mtu = it.get("NlMtu")
        link_mtu = it.get("MtuSize")
        out.append(
            AdapterInfo(
                name=name,
                description=desc,
                status=(it.get("Status") or "").strip(),
                link_speed=(it.get("LinkSpeed") or "").strip(),
                mac=(it.get("MacAddress") or "").strip(),
                if_index=int(it.get("ifIndex") or 0),
                interface_guid=(it.get("InterfaceGuid") or "").strip(),
                media_type=str(it.get("MediaType") or ""),
                ipv4=ipv4,
                ipv6=ipv6,
                prefix_len=prefix,
                gateway=gateway,
                dns_v4=dns_v4,
                dns_v6=dns_v6,
                dhcp=any(
                    str(i.get("PrefixOrigin")).lower() == "dhcp"
                    for i in ips
                    if isinstance(i, dict)
                ),
                mtu=int(nl_mtu) if isinstance(nl_mtu, (int, str))
                and str(nl_mtu).isdigit() else 0,
                link_mtu=int(link_mtu) if isinstance(link_mtu, (int, str))
                and str(link_mtu).isdigit() else 0,
                is_virtual=any(h in blob for h in _VIRTUAL_HINTS),
            )
        )
    # 已连接的物理网卡优先，其次按 ifIndex
    out.sort(key=lambda a: (not a.up, a.is_virtual, a.if_index))
    return out


def primary_adapter(adapters: list[AdapterInfo] | None = None) -> AdapterInfo | None:
    """挑选“当前正在承载上网流量”的网卡：已连接 + 有默认网关 + 非虚拟优先。"""
    adapters = adapters if adapters is not None else collect_adapters()
    candidates = [a for a in adapters if a.up and a.gateway]
    if not candidates:
        candidates = [a for a in adapters if a.up and a.ipv4]
    if not candidates:
        return None
    physical = [a for a in candidates if not a.is_virtual]
    return (physical or candidates)[0]


# --------------------------------------------------------------------------- #
# 文件与注册表辅助
# --------------------------------------------------------------------------- #
HOSTS_PATH = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                          "System32", "drivers", "etc", "hosts")


def read_text_file(path: str, *, encoding: str = "utf-8") -> str:
    with open(path, "r", encoding=encoding, errors="surrogateescape", newline="") as fh:
        return fh.read()


def atomic_write(path: str, text: str, *, encoding: str = "utf-8") -> None:
    """原子写入：先写同目录临时文件再替换，避免掉电/崩溃造成半截文件。

    关键系统文件（如 hosts）被其它进程占用时 ReplaceFile 失败，此处回退为直接覆盖，
    仍保证内容完整；失败异常向上抛，不吞。
    """
    directory = os.path.dirname(path) or "."
    tmp = os.path.join(directory, f".{os.path.basename(path)}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding=encoding, errors="surrogateescape", newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    try:
        os.replace(tmp, path)
    except OSError:
        with open(path, "w", encoding=encoding, errors="surrogateescape", newline="") as fh:
            fh.write(text)
        try:
            os.unlink(tmp)
        except OSError:
            pass


def flush_dns_cache() -> tuple[int, str]:
    return run_cmd(["ipconfig", "/flushdns"], timeout=15)


def app_data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "LanPulse")
    os.makedirs(path, exist_ok=True)
    return path


IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def is_valid_ipv4(text: str) -> bool:
    parts = text.split(".")
    if len(parts) != 4:
        return False
    try:
        return all(0 <= int(p) <= 255 and p.isdigit() for p in parts)
    except ValueError:
        return False


__all__ = [
    "CREATE_NO_WINDOW",
    "IS_WINDOWS",
    "HOSTS_PATH",
    "AdapterInfo",
    "app_data_dir",
    "atomic_write",
    "collect_adapters",
    "computer_name",
    "decode_console",
    "flush_dns_cache",
    "is_admin_account",
    "is_elevated",
    "is_valid_ipv4",
    "now",
    "os_display_name",
    "primary_adapter",
    "read_text_file",
    "run_cmd",
    "run_ps",
    "run_ps_json",
    "windows_build",
]
