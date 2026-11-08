"""把双语 About 应用到 GitHub 仓库，并同步双语 topics 与 homepage。

GitHub 的 description 不跟随界面语言，只有单字段。这里的做法：
中文 + 换行 + 英文放进同一字段，靠换行让两段都能读。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _console import setup_console  # noqa: E402
from repo_about import build  # noqa: E402

setup_console()

API = "https://api.github.com/repos/Levanll/LanPulse"
TOKEN_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".gh_token"
)

#: 话题标签：GitHub 的 topics 只支持 ASCII 小写与连字符，无法放中文，
#: 因此这里保证英文可检索性；中文覆盖靠 description 与 README。
TOPICS = [
    "windows", "network", "diagnostics", "dns", "hosts", "mtu",
    "troubleshooting", "network-monitoring", "pyside6", "python",
    "system-tools", "bilingual", "offline", "privacy", "rollback",
]


def main() -> int:
    if not os.path.isfile(TOKEN_FILE):
        print("[X] .gh_token 不存在")
        return 2
    token = open(TOKEN_FILE, encoding="ascii", errors="replace").read().strip()

    desc = build()
    payload = json.dumps(
        {"description": desc, "topics": TOPICS}, ensure_ascii=False
    ).encode("utf-8")

    req = urllib.request.Request(
        API,
        data=payload,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": "LanPulse-About",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(f"[X] HTTP {exc.code}: {body[:400]}")
        return 3
    except (urllib.error.URLError, OSError) as exc:
        print(f"[X] 请求失败: {exc}")
        return 4

    print("[OK] 仓库 About 已更新")
    print(f"  描述 ({len(data.get('description', ''))}/350 字符):")
    for line in (data.get("description") or "").splitlines():
        print(f"    {line}")
    print(f"  topics ({len(data.get('topics') or [])}): "
          f"{', '.join(sorted(data.get('topics') or []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
