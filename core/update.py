"""更新检测 —— 只读版本清单，不发送任何本机信息。

## 为什么是"拉一个静态文件"而不是调 GitHub API

两个方案都能拿到最新版本号，但静态清单更适合这个产品的处境：

1. **不触限流**：GitHub API 未认证是 60 次/小时/IP，一个共享出口的校园网
   或公司网络里，用户可能根本没配额；静态文件走 Pages CDN，没有这个限制。
2. **可解释**：对用户说的是"向官网请求一个版本号文件"，比
   "调用 GitHub REST API"更容易讲清楚，这与产品"诚实"的定位一致。
3. **格式由我们定义**：可以带双语更新说明，且不与 Release body 的
   中英对照格式耦合。

## 隐私边界（不可放宽）

这个模块发出的请求**只有一种形态**：`GET https://levanll.github.io/LanPulse/latest.json`。

- 不附带任何查询参数、设备 ID、安装 ID、用户名或统计信息
- 不带 `Referer`（urllib 默认不带）
- 请求头只有一个固定的 `User-Agent: LanPulse/<version>`——包含版本号是为了
  在服务端排查"旧版是否还在请求"，它已经把信息量压到最低；**不要**往里加
  主机名、用户名或 GUID

服务器侧（GitHub Pages）仍会记录访问 IP，这是任何 HTTPS 请求都无法避免的，
但它属于传输层事实，不是本程序收集的数据。

## 失败必须静默

这是个网络诊断工具。它自己联网查更新失败时弹错误框，是荒谬的体验。
任何异常（超时、DNS 失败、404、JSON 坏、字段缺失）一律返回 None，
由调用方当作"没有更新"处理。`check_for_update` 不抛异常。
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

#: 版本清单地址。与落地页同域，走 GitHub Pages CDN。
UPDATER_URL = "https://levanll.github.io/LanPulse/latest.json"

#: 硬超时。更新检测是后台锦上添花，绝不该让用户等。
DEFAULT_TIMEOUT = 5.0

#: 两次自动检查的最小间隔（秒）。24 小时。
#: 目的是避免用户频繁开关软件造成的重复请求，不是服务端限流需要。
CHECK_INTERVAL = 24 * 3600

_VERSION_RE = re.compile(r"^\d+(\.\d+)*$")


@dataclass(frozen=True)
class UpdateInfo:
    """一条可用的更新信息。"""

    version: str
    url: str
    notes_zh: str = ""
    notes_en: str = ""
    mandatory: bool = False

    def notes(self, lang: str) -> str:
        """按当前语言取更新说明；缺失时回退到另一种语言。"""
        if str(lang).startswith("en"):
            return self.notes_en or self.notes_zh
        return self.notes_zh or self.notes_en


def version_tuple(text: str) -> tuple[int, ...]:
    """把 "1.2.3" 转成 (1, 2, 3) 以便正确比较。

    **不能直接比字符串**：字符串比较下 "1.10.0" < "1.9.0"，会把新版本
    判成旧版本，用户永远收不到更新提醒。
    """
    raw = str(text or "").strip()
    raw = raw[1:] if raw[:1].lower() == "v" else raw
    if not _VERSION_RE.match(raw):
        raise ValueError(f"版本号格式非法: {text!r}")
    return tuple(int(part) for part in raw.split("."))


def is_newer(remote: str, current: str) -> bool:
    """remote 是否比 current 新。任一方格式非法都返回 False（宁可漏报不误报）。"""
    try:
        return version_tuple(remote) > version_tuple(current)
    except ValueError:
        return False


def parse_manifest(text: str) -> UpdateInfo | None:
    """解析版本清单。字段不合法返回 None，不抛异常。"""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    version = str(data.get("version") or "").strip()
    url = str(data.get("url") or "").strip()
    if not version or not url:
        return None
    if not url.startswith("https://"):
        # 只接受 https：更新提示会把用户带去下载页面，
        # 一个 http 链接等于允许中间人替换成任意页面。
        return None
    try:
        version_tuple(version)
    except ValueError:
        return None
    return UpdateInfo(
        version=version,
        url=url,
        notes_zh=str(data.get("notes_zh") or ""),
        notes_en=str(data.get("notes_en") or ""),
        mandatory=bool(data.get("mandatory", False)),
    )


def check_for_update(current_version: str, *, timeout: float = DEFAULT_TIMEOUT,
                     fetch=None) -> UpdateInfo | None:
    """查询是否有新版本。没有更新、或任何失败，都返回 None。

    `fetch` 仅供测试注入（接收 url 返回文本）；默认走 urllib。
    """
    try:
        text = (fetch or _http_get)(UPDATER_URL, timeout=timeout, current_version=current_version)
    except Exception:  # noqa: BLE001 - 更新检测失败不得影响主流程
        return None
    if not text:
        return None
    info = parse_manifest(text)
    if info is None:
        return None

    # 当前版本号自身非法时，不弹更新提示（无法判断新旧，宁可沉默）
    if not is_newer(info.version, current_version):
        return None
    return info


def _http_get(url: str, *, timeout: float, current_version: str) -> str:
    """唯一的出口。参数固定，不接受调用方拼查询串。"""
    req = urllib.request.Request(
        url,
        headers={
            # 固定 UA：只带版本号，用于服务端判断旧版本是否还在请求。
            # 不要加主机名/用户名/GUID。
            "User-Agent": f"LanPulse/{current_version}",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        if resp.getcode() != 200:
            return ""
        return resp.read(64 * 1024).decode("utf-8", errors="replace")


__all__ = [
    "CHECK_INTERVAL", "DEFAULT_TIMEOUT", "UPDATER_URL", "UpdateInfo",
    "check_for_update", "is_newer", "parse_manifest", "version_tuple",
]
