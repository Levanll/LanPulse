"""手工创建 GitHub Release 并上传 release/ 下的资产。

对应 HANDOFF 发版流程第 3、4 步。`release.yml` 已是手动触发，所以这一步
不再由 CI 代劳——要用本机构建出来的产物直接上传。

版本号从命令行传入，body 取 `docs/release-notes/<tag>.merged.md`。

用法：
    python tools/create_release.py v1.3.1
    python tools/create_release.py v1.3.1 --dry-run

为什么用 Python 而不是 PowerShell：本机是 PowerShell 5.1，转 JSON 时
中文会变成问号；这里统一走 json.dumps(ensure_ascii=False).encode("utf-8")。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
try:
    from _console import setup_console
    setup_console()
except Exception:  # noqa: BLE001 - 控制台编码修不了也不该影响发版
    pass

REPO = "Levanll/LanPulse"


def load_token() -> str:
    p = ROOT / ".gh_token"
    if not p.exists():
        sys.exit("FAIL 缺少 .gh_token（见 HANDOFF「发布 token」一节）")
    return p.read_text(encoding="utf-8").strip()


def api(token: str, path: str, method: str = "GET", payload=None):
    url = f"https://api.github.com/repos/{REPO}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "LanPulse-release",
    }
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, (json.loads(raw.decode("utf-8")) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def upload(token: str, upload_url: str, path: Path):
    url = upload_url.replace("{?name,label}", f"?name={path.name}")
    req = urllib.request.Request(
        url,
        data=path.read_bytes(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
            "User-Agent": "LanPulse-release",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


def collect_assets(version: str) -> list[Path]:
    """按版本号从 release/ 取三个资产。缺任何一个都直接失败，不传半套。"""
    rel = ROOT / "release"
    return [
        rel / f"LanPulse-{version}-Setup.exe",
        rel / f"LanPulse-{version}-win64-portable.zip",
        rel / "SHA256SUMS.txt",
    ]


def main() -> int:
    ap = argparse.ArgumentParser(description="创建 GitHub Release 并上传资产")
    ap.add_argument("tag", help="tag 名，如 v1.3.1")
    ap.add_argument("--dry-run", action="store_true", help="只校验不发送")
    args = ap.parse_args()

    tag = args.tag if args.tag.startswith("v") else f"v{args.tag}"
    version = tag.lstrip("v")

    body_file = ROOT / "docs" / "release-notes" / f"{tag}.merged.md"
    if not body_file.exists():
        sys.exit(f"FAIL 缺少描述文件: {body_file}")
    body = body_file.read_text(encoding="utf-8")

    # 中英对照结构校验：缺任一段就不发，避免推出半成品描述
    problems = []
    if "## 本次更新" not in body:
        problems.append("缺少中文段 ## 本次更新")
    if "## What's new" not in body:
        problems.append("缺少英文段 ## What's new")
    if "\n---\n" not in body:
        problems.append("缺少 --- 分隔线")
    if "???" in body:
        problems.append("含 ??? —— 中文编码出错")
    if problems:
        sys.exit("FAIL 描述结构不合格:\n  " + "\n  ".join(problems))

    assets = collect_assets(version)
    missing = [a.name for a in assets if not a.exists()]
    if missing:
        sys.exit(f"FAIL 缺少资产: {missing}")

    print(f"tag:  {tag}")
    print(f"body: {body_file.name}  {len(body)} 字符，中英段落齐全")
    for a in assets:
        print(f"  {a.name}  {a.stat().st_size:,} B")

    if args.dry_run:
        print("\n--dry-run：未发送任何请求")
        return 0

    token = load_token()

    st, existing = api(token, f"/releases/tags/{tag}")
    if st == 200 and isinstance(existing, dict):
        print(f"\n已存在 {tag}，先删除 id={existing['id']}")
        api(token, f"/releases/{existing['id']}", method="DELETE")

    print("\n创建 Release …")
    st, rel = api(token, "/releases", method="POST", payload={
        "tag_name": tag, "name": tag, "body": body,
        "draft": False, "prerelease": False,
    })
    if st not in (200, 201):
        sys.exit(f"FAIL 创建失败 {st}: {rel}")
    print(f"  已创建 id={rel['id']}  body={len(rel['body'])} 字符")
    if "???" in rel["body"]:
        sys.exit("FAIL 服务端 body 含 ??? —— 中文编码出错")

    for a in assets:
        print(f"上传 {a.name} …")
        st, res = upload(token, rel["upload_url"], a)
        if st not in (200, 201):
            sys.exit(f"FAIL 上传失败 {st}: {res}")
        print(f"  OK {res['name']}  {res['size']:,} B")

    print(f"\n完成: {rel['html_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
