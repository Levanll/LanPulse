"""系统集成：提权、单实例、环境自检、临时文件清理、打开目录。

这里的每个函数都直接触碰操作系统边界（UAC、内核命名对象、文件权限），
因此统一遵守两条规则：
  * 所有 Win32 调用都显式声明 argtypes/restype。ctypes 默认把指针当 c_int，
    64 位下句柄会被截断，导致 CloseHandle 关不掉真正的句柄（句柄泄漏）。
  * 失败必须给出可读原因并降级，不抛异常给 UI 线程；
    但也不用裸 `except: pass` 吞掉——拿不到原因的地方就记录到日志。
"""
from __future__ import annotations

import ctypes
import fnmatch
import logging
import os
import platform
import re
import sys
import tempfile
import time
from ctypes import wintypes
from dataclasses import dataclass

try:  # 作为包内模块导入
    from core import platform_win as pw
    from core.backup import BACKUP_ROOT_NAME
    from core.branding import WINDOW_TITLE
except ImportError:  # 以 PYTHONPATH=<项目根> 导入 app.sysutil
    from core import platform_win as pw  # type: ignore[no-redef]
    from core.backup import BACKUP_ROOT_NAME  # type: ignore[no-redef]
    from core.branding import WINDOW_TITLE  # type: ignore[no-redef]

log = logging.getLogger("lanpulse.sysutil")

#: 窗口标题的唯一来源是 core.branding，这里只是转发。
#: 曾经硬编码为 "LanPulse - 网络体检与优化"（旧标语），改名后没有跟随，
#: 导致单实例检测按错误的标题找窗口。

# UAC 被用户拒绝时 ShellExecuteW 的返回码是 ERROR_CANCELLED(1223) 对应的
# SE_ERR_ 值区间（<= 32）。这个值不需要单独判断，只要 <= 32 就视为未提权成功。
_SE_ERR_MIN = 32

_ERROR_ALREADY_EXISTS = 183

IS_WINDOWS = sys.platform == "win32"


# --------------------------------------------------------------------------- #
# Win32 绑定（惰性加载：非 Windows 上导入本模块不能直接炸掉）
# --------------------------------------------------------------------------- #
def _dll(name: str) -> "ctypes.WinDLL":
    """带 use_last_error 的 WinDLL。

    必须用 use_last_error=True + ctypes.get_last_error()，而不是在调用后
    再调一次 windll.kernel32.GetLastError()：两次 ctypes 调用之间它自己的
    参数转换可能覆盖线程 last-error，读到的就不是 CreateMutexW 的返回值了。
    """
    return ctypes.WinDLL(name, use_last_error=True)  # type: ignore[attr-defined]


def _kernel32() -> "ctypes.WinDLL":
    k32 = _dll("kernel32")
    k32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    k32.CreateMutexW.restype = wintypes.HANDLE
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    k32.CloseHandle.restype = wintypes.BOOL
    return k32


# --------------------------------------------------------------------------- #
# A. 管理员提权
# --------------------------------------------------------------------------- #
def is_admin() -> bool:
    """当前进程是否已提权。转调 platform_win，保证全项目只有一处判定逻辑。"""
    return pw.is_elevated()


def _launch_target(args: list[str] | None) -> tuple[str, str, str]:
    """构造 (可执行文件, 参数字符串, 工作目录)。

    打包(exe)与源码两种运行方式的差别全在这里：
      * 已打包：sys.executable 就是 LanPulse.exe，参数只有业务参数；
      * 未打包：sys.executable 是 python.exe，必须把入口脚本 main.py 作为
        第一个参数补上，否则提权后的新进程会启动一个空的 Python 解释器
        —— 用户看到 UAC 确认了却什么都没发生。
    """
    frozen = bool(getattr(sys, "frozen", False))
    extra = list(args) if args is not None else sys.argv[1:]
    script = os.path.abspath(sys.argv[0]) if sys.argv and sys.argv[0] else ""

    if frozen:
        exe = sys.executable
        params = extra
        cwd = os.path.dirname(exe) or os.getcwd()
    else:
        exe = sys.executable
        # 没有入口脚本（例如 -c / 交互式）时无法安全重启，让调用方看到空参数字符串
        params = ([script] if script else []) + extra
        cwd = os.path.dirname(script) or os.getcwd()
    return exe, subprocess_list2cmdline(params), cwd


def subprocess_list2cmdline(args: list[str]) -> str:
    """Windows 命令行拼装。必须按标准规则加引号，否则含空格的路径会被拆开。"""
    import subprocess

    return subprocess.list2cmdline(args)


def relaunch_as_admin(args: list[str] | None = None) -> bool:
    """以管理员身份重启当前程序。

    返回 True 表示提权进程已被拉起，调用方必须立即退出本进程，否则会出现
    两个实例同时操作同一份 hosts / DNS 配置。
    返回 False 表示用户拒绝 UAC 或系统不允许提权 —— 这不是错误，
    调用方应提示“已取消，将以只读模式运行”，而不是弹异常。

    args 语义：**完整的业务参数列表**（不含 python.exe 与脚本路径，两者由本函数补）。
    传 None 表示原样沿用当前进程的命令行参数。
    """
    if not IS_WINDOWS:
        return False
    exe, params, cwd = _launch_target(args)
    try:
        shell32 = _dll("shell32")
        shell32.ShellExecuteW.argtypes = (
            wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
            wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int,
        )
        shell32.ShellExecuteW.restype = ctypes.c_void_p
        # restype 用 c_void_p 是因为 HINSTANCE 在 64 位下是 8 字节；
        # 小于等于 32 的返回值是 SE_ERR_* 错误码，不是句柄。
        result = int(shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1) or 0)
    except (AttributeError, OSError) as exc:
        log.error("提权重启失败，无法调用 ShellExecuteW: %s", exc)
        return False
    if result <= _SE_ERR_MIN:
        log.info("提权被取消或失败（ShellExecuteW 返回 %s），将以只读模式继续", result)
        return False
    log.info("已拉起提权进程: %s %s", exe, params)
    return True


# --------------------------------------------------------------------------- #
# B. 单实例
# --------------------------------------------------------------------------- #
class SingleInstance:
    """基于内核命名互斥体的单实例守卫。

    命名对象跨会话可见，所以即使程序被不同用户/不同终端启动也只会有一个实例；
    互斥体随进程结束自动释放，但进程活着期间必须显式 CloseHandle，
    否则句柄泄漏，且在长驻进程里会累积。
    """

    def __init__(self, key: str = "LanPulse_Global_Mutex") -> None:
        self.key = key
        self._handle: int | None = None
        self._is_owner = False

    def acquire(self) -> bool:
        """True = 本进程是唯一实例；False = 已有实例在运行。

        注意已存在时 CreateMutexW 也会返回一个有效句柄（指向对方的互斥体），
        必须关掉，否则我们反而成了它的持有者之一，对方退出后互斥体仍然活着。
        """
        if self._handle:
            return self._is_owner
        if not IS_WINDOWS:
            # 非 Windows 上没有命名互斥体语义，直接放行，避免开发机上一开就退出
            self._is_owner = True
            return True
        try:
            k32 = _kernel32()
            handle = k32.CreateMutexW(None, False, self.key)
            last_error = ctypes.get_last_error()
        except (AttributeError, OSError) as exc:
            log.error("创建单实例互斥体失败(%s): %s", self.key, exc)
            self._is_owner = True  # 守卫不可用时宁可让程序能开，不要锁死用户
            return True

        if not handle:
            log.error("CreateMutexW 返回空句柄，last_error=%s", last_error)
            self._is_owner = True
            return True

        if last_error == _ERROR_ALREADY_EXISTS:
            _kernel32().CloseHandle(handle)
            self._is_owner = False
            return False

        self._handle = handle
        self._is_owner = True
        return True

    def release(self) -> None:
        if not self._handle:
            return
        try:
            if not _kernel32().CloseHandle(self._handle):
                log.warning("关闭单实例互斥体失败，last_error=%s", ctypes.get_last_error())
        except (AttributeError, OSError) as exc:
            log.warning("关闭单实例互斥体异常: %s", exc)
        finally:
            self._handle = None
            self._is_owner = False

    def activate_existing(self) -> None:
        """把已运行实例的窗口唤到前台。

        窗口标题必须与 main.py 的 setWindowTitle 完全一致，否则 FindWindowW
        永远找不到；WINDOW_TITLE 常量导出给 main.py 复用，避免两处手写漂移。
        """
        if not IS_WINDOWS:
            return
        try:
            user32 = _dll("user32")
            user32.FindWindowW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR)
            user32.FindWindowW.restype = wintypes.HWND
            hwnd = user32.FindWindowW(None, WINDOW_TITLE)
            if not hwnd:
                log.info("未找到已运行实例的窗口（标题=%s），可能仍在启动中", WINDOW_TITLE)
                return
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE：最小化态也能还原
            user32.SetForegroundWindow(hwnd)
        except (AttributeError, OSError) as exc:
            log.warning("唤起已有窗口失败: %s", exc)

    # 支持 with 语句，避免调用方漏掉 release
    def __enter__(self) -> "SingleInstance":
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


# --------------------------------------------------------------------------- #
# C. 环境自检
# --------------------------------------------------------------------------- #
@dataclass
class EnvCheck:
    name: str
    ok: bool
    detail: str
    severity: str  # "ok" / "warn" / "critical"
    fix_hint: str = ""


_MIN_WIN10_BUILD = 10240  # 第一版 Windows 10 的 build 号


def _check_os() -> EnvCheck:
    if platform.system() != "Windows":
        return EnvCheck(
            name="操作系统",
            ok=False,
            detail=f"当前系统为 {platform.system()} {platform.release()}，"
                   f"LanPulse 的检测与修复能力基于 Windows 原生组件，其它平台不可用。",
            severity="critical",
            fix_hint="请在 Windows 10 及以上版本运行本程序。",
        )
    version = platform.version()
    match = re.search(r"\d+\.\d+\.(\d+)", version)
    build = int(match.group(1)) if match else 0
    # platform.release() 在中文 Windows 11 上会给出 "11"，单独展示信息量太低，
    # 补上 "Windows" 前缀；名称只影响可读性，判定仍以 build 号为准。
    release = f"Windows {platform.release()}" if platform.release() else "Windows（未知版本）"
    if not build:
        return EnvCheck(
            name="操作系统",
            ok=True,
            detail=f"{release}，版本号 {version} 无法解析出 build，"
                   f"按兼容处理（部分新版检测项可能不可用）。",
            severity="warn",
            fix_hint="",
        )
    if build < _MIN_WIN10_BUILD:
        return EnvCheck(
            name="操作系统",
            ok=False,
            detail=f"{release} build {build}，低于 Windows 10 最低要求 build {_MIN_WIN10_BUILD}。"
                   f"Get-NetAdapter 等检测依赖的接口在此版本上不完整。",
            severity="warn",
            fix_hint="建议升级到 Windows 10 及以上版本。",
        )
    return EnvCheck(
        name="操作系统",
        ok=True,
        detail=f"{release} build {build}，满足 Windows 10 (build ≥ {_MIN_WIN10_BUILD}) 要求。",
        severity="ok",
    )


def _check_admin() -> EnvCheck:
    if pw.is_elevated():
        return EnvCheck(name="管理员权限", ok=True, detail="已以管理员身份运行，可执行全部修复动作。",
                        severity="ok")
    return EnvCheck(
        name="管理员权限",
        ok=False,
        detail="当前为普通用户权限，检测功能全部可用，但改写 hosts / DNS / 防火墙等修复动作会被拒绝。",
        severity="warn",
        fix_hint="部分修复功能需要管理员权限，点击「以管理员身份重启」",
    )


def _check_powershell() -> EnvCheck:
    rc, out = pw.run_ps("$PSVersionTable.PSVersion.Major", timeout=20)
    text = out.strip()
    match = re.search(r"\d+", text)
    if rc != 0 or not match:
        reason = text[:160] if text else f"返回码 {rc}，无输出"
        return EnvCheck(
            name="PowerShell",
            ok=False,
            detail=f"PowerShell 不可用（{reason}）。网卡、DNS、TCP 参数等检测依赖它，"
                   f"缺失时大部分检测项会被跳过。",
            severity="critical",
            fix_hint="检查 C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe 是否存在，"
                     "或运行 sfc /scannow 修复系统组件。",
        )
    return EnvCheck(name="PowerShell", ok=True,
                    detail=f"PowerShell {match.group(0)} 可用。", severity="ok")


def _check_netsh() -> EnvCheck:
    # netsh 的帮助页在部分版本上返回 1，0 和 1 都代表"程序能跑起来"
    rc, out = pw.run_cmd(["netsh", "/?"], timeout=15)
    if rc in (0, 1):
        return EnvCheck(name="netsh", ok=True,
                        detail=f"netsh 可用（帮助页返回码 {rc}）。", severity="ok")
    reason = f"返回码 {rc}" if rc >= 0 else out[:120]
    return EnvCheck(
        name="netsh",
        ok=False,
        detail=f"netsh 不可用（{reason}）。协议栈重置、Winsock 修复等动作无法执行。",
        severity="critical",
        fix_hint="检查 netsh.exe 是否被安全软件拦截，或运行 sfc /scannow 修复系统文件。",
    )


def _check_hosts_readable() -> EnvCheck:
    path = pw.HOSTS_PATH
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline().rstrip("\r\n")
    except FileNotFoundError:
        return EnvCheck(
            name="HOSTS 可读",
            ok=False,
            detail=f"{path} 不存在。缺失时域名解析仍可用，但屏蔽类记录已丢失。",
            severity="warn",
            fix_hint="可用「HOSTS 恢复为系统默认模板」重建该文件。",
        )
    except PermissionError as exc:
        return EnvCheck(
            name="HOSTS 可读",
            ok=False,
            detail=f"读取 {path} 被拒绝：{exc}。安全软件可能正在锁定该文件。",
            severity="critical",
            fix_hint="检查安全软件的「系统文件保护」是否拦截了 hosts 读取。",
        )
    except OSError as exc:
        return EnvCheck(
            name="HOSTS 可读",
            ok=False,
            detail=f"读取 {path} 失败：{exc}",
            severity="critical",
            fix_hint="检查磁盘错误（chkdsk）或系统文件完整性（sfc /scannow）。",
        )
    return EnvCheck(
        name="HOSTS 可读",
        ok=True,
        detail=f"{path} 可读，首行 {len(first)} 字符"
               + (f"：{first[:40]}" if first else "（空行）。"),
        severity="ok",
    )


def _check_hosts_writable() -> EnvCheck:
    """只用权限位判断，绝不真的写 hosts —— 体检阶段不允许产生任何副作用。

    注意 os.access(W_OK) 在 Windows 上不做 ACL 检查（只看只读属性 / 卷是否只读），
    所以普通用户也可能拿到 True。结论仍按 os.access 给（这是本项的契约），
    但未提权时在 detail 里点明"实际写入还会被 ACL 拒绝"，避免用户误以为是假阳性。
    """
    path = pw.HOSTS_PATH
    writable = os.access(path, os.W_OK)
    elevated = pw.is_elevated()
    caveat = "" if elevated else "当前未提权，写 hosts 仍会被系统的 ACL 拒绝（详见「管理员权限」项）。"
    if writable:
        return EnvCheck(
            name="HOSTS 可写",
            ok=True,
            detail=f"{path} 未设置只读属性，具备写权限{('；' + caveat) if caveat else '。'}"
                   f"（仅检测权限，未修改文件）",
            severity="ok",
        )
    return EnvCheck(
        name="HOSTS 可写",
        ok=False,
        detail=f"{path} 当前无写权限，HOSTS 相关修复会被跳过。{caveat}"
               f"（仅检测权限，未修改文件）",
        severity="warn",
        fix_hint="右键 hosts 文件 → 属性 → 取消「只读」，并以管理员身份重启程序。",
    )


def _check_backup_disk() -> EnvCheck:
    """真写一个临时文件再删掉：目录权限、磁盘满、只读盘都能一次测出来。

    用 tempfile 生成唯一名，避免和并发进程撞名；删除失败不影响结论（本项只关心可写性），
    但要记进日志，防止 _probe_*.tmp 在用户机器上堆垃圾。
    """
    root = os.path.join(pw.app_data_dir(), BACKUP_ROOT_NAME)
    try:
        os.makedirs(root, exist_ok=True)
    except OSError as exc:
        return EnvCheck(
            name="备份目录",
            ok=False,
            detail=f"无法创建备份目录 {root}：{exc}。修复前的自动备份不可用，"
                   f"出于安全考虑将禁止执行任何修改。",
            severity="critical",
            fix_hint="检查磁盘剩余空间与 %LOCALAPPDATA% 的访问权限。",
        )
    try:
        fd, probe = tempfile.mkstemp(prefix="_probe_", suffix=".tmp", dir=root)
    except OSError as exc:
        return EnvCheck(
            name="备份目录",
            ok=False,
            detail=f"备份目录 {root} 不可写：{exc}。修复前的自动备份不可用。",
            severity="critical",
            fix_hint="检查磁盘剩余空间，或确认安全软件未阻止写入 %LOCALAPPDATA%\\LanPulse。",
        )
    cleanup_note = ""
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("netpulse write probe\n")
    except OSError as exc:
        cleanup_note = f"（探测文件写入失败：{exc}）"
    finally:
        try:
            os.unlink(probe)
        except OSError as exc:
            log.warning("探测文件未能删除: %s (%s)", probe, exc)
            cleanup_note = f"（探测文件 {os.path.basename(probe)} 未能删除：{exc}，下次启动会被清理）"
    if cleanup_note.startswith("（探测文件写入失败"):
        return EnvCheck(
            name="备份目录",
            ok=False,
            detail=f"备份目录 {root} 写入失败{cleanup_note}。修复前的自动备份不可用。",
            severity="critical",
            fix_hint="检查磁盘剩余空间与目录权限。",
        )
    return EnvCheck(
        name="备份目录",
        ok=True,
        detail=f"{root} 可写，已写入并删除一个探测文件{cleanup_note}。",
        severity="ok",
    )


_NTDLL_PATH = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                           "System32", "ntdll.dll")


def _check_system_time() -> EnvCheck:
    """启发式时间检查。

    依据：ntdll.dll 的 mtime 约等于当前系统文件版本（安装 / 最近一次更新）的时间。
    它只会比"现在"旧，不会更未来；因此只要本机时间与它相差超过一年，
    基本可以判定系统时间跑偏。时间错会导致 TLS 证书校验失败（所有 https 报错），
    这是"能上 QQ 打不开网页"的典型原因之一。误差容忍一年，避免老系统误报。
    """
    try:
        mtime = os.stat(_NTDLL_PATH).st_mtime
    except OSError as exc:
        return EnvCheck(
            name="系统时间",
            ok=True,
            detail=f"无法读取 {_NTDLL_PATH} 的时间戳（{exc}），跳过时间启发式检查。",
            severity="ok",
        )
    drift_days = abs(time.time() - mtime) / 86400.0
    if drift_days <= 365:
        return EnvCheck(
            name="系统时间",
            ok=True,
            detail=f"本机时间与系统文件 ntdll.dll 的时间戳相差 {drift_days:.0f} 天，"
                   f"在合理范围内（阈值 365 天）。",
            severity="ok",
        )
    return EnvCheck(
        name="系统时间",
        ok=False,
        detail=f"本机时间与 ntdll.dll 时间戳相差 {drift_days:.0f} 天（阈值 365 天）。"
               f"该项为启发式判断：ntdll.dll 的修改时间应接近系统安装或最近更新的时间，"
               f"差值过大通常意味着系统时间被改错。时间错误会导致证书校验失败、网页打不开。",
        severity="warn",
        fix_hint="在「设置 → 时间和语言」中开启自动同步时间，或手动校正日期与时间。",
    )


def run_env_checks() -> list[EnvCheck]:
    """按"最可能出问题、最容易修"的顺序跑完 8 项环境自检。

    每项都真实探测（执行命令 / 读文件 / 写探测文件），不做任何假设；
    单项内部已把异常转成 EnvCheck，因此本函数不会因为环境残缺而抛异常。
    """
    checks = (
        _check_os,
        _check_admin,
        _check_powershell,
        _check_netsh,
        _check_hosts_readable,
        _check_hosts_writable,
        _check_backup_disk,
        _check_system_time,
    )
    return [fn() for fn in checks]


# --------------------------------------------------------------------------- #
# D. 清理临时文件
# --------------------------------------------------------------------------- #
def cleanup_stale_temp(max_age_days: int = 7) -> int:
    """删除 app_data_dir 下超过指定天数的 *.tmp 文件，返回删除数量。

    安全边界（不要为"顺手清理"而放宽）：
      * 只扫 app_data_dir 一层，不递归 —— 备份会话目录里的东西一律不碰；
      * 只匹配 *.tmp —— 不按扩展名批量删其它文件；
      * 只删普通文件 —— 符号链接、目录即使名字像 tmp 也跳过。
    """
    root = os.path.abspath(pw.app_data_dir())
    cutoff = time.time() - max(0, max_age_days) * 86400.0
    removed = 0
    try:
        entries = list(os.scandir(root))
    except OSError as exc:
        log.warning("无法扫描临时目录 %s: %s", root, exc)
        return 0
    for entry in entries:
        if not fnmatch.fnmatch(entry.name, "*.tmp"):
            continue
        try:
            if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                continue
            if entry.stat(follow_symlinks=False).st_mtime > cutoff:
                continue
            os.unlink(entry.path)
            removed += 1
        except OSError as exc:
            # 单个文件被占用是常态（例如上一次进程还没退干净），不能中断整轮清理
            log.warning("清理临时文件失败 %s: %s", entry.path, exc)
    if removed:
        log.info("已清理 %d 个临时文件（目录 %s）", removed, root)
    return removed


# --------------------------------------------------------------------------- #
# E. 打开目录 / 文件
# --------------------------------------------------------------------------- #
def open_path(path: str) -> bool:
    """用系统默认程序打开文件或目录。返回是否成功，失败原因写日志。"""
    if not path:
        return False
    target = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(target):
        log.warning("要打开的路径不存在: %s", target)
        return False
    try:
        os.startfile(target)  # type: ignore[attr-defined]  # 仅 Windows 提供
    except (AttributeError, OSError) as exc:
        log.error("打开路径失败 %s: %s", target, exc)
        return False
    return True


def open_backup_dir(store_root: str) -> bool:
    """打开备份根目录。目录不存在时先建出来——用户点"打开"的期望是看到它，
    而不是收到一个"不存在"的报错。"""
    root = os.path.abspath(os.path.expanduser(store_root or ""))
    if not root:
        return False
    try:
        os.makedirs(root, exist_ok=True)
    except OSError as exc:
        log.error("创建备份目录失败 %s: %s", root, exc)
        return False
    return open_path(root)


__all__ = [
    "WINDOW_TITLE",
    "EnvCheck",
    "SingleInstance",
    "cleanup_stale_temp",
    "is_admin",
    "open_backup_dir",
    "open_path",
    "relaunch_as_admin",
    "run_env_checks",
]
