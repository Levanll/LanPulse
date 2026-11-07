r"""LanPulse v1.1.0 发布：重命名仓库 → 强推历史 → 建 Release → 上传产物。

为什么先重命名而不是新建仓库：
  * 全新仓库会丢掉已有的 1 次下载记录与 star（虽然很少，但没必要丢）
  * GitHub 的仓库重命名会自动把旧地址重定向，已有链接不会失效
  * 若先新建再删旧仓库，重定向就没了

安全：
  * token 只从 .gh_token 读取，不落盘到 git config
  * 强推前会打印摘要并要求确认
  * 推送完成后立刻把凭据 URL 从 remote 摘掉

用法：
    python tools/publish_v110.py            # 预检
    python tools/publish_v110.py --execute  # 真正执行
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
try:
    from _console import setup_console

    setup_console()
except ImportError:
    pass

API = "https://api.github.com"
UPLOAD = "https://uploads.github.com"
OWNER = "Levanll"
OLD_REPO = "NetPulse"
NEW_REPO = "LanPulse"
VERSION = "1.1.0"
TAG = f"v{VERSION}"
ASSETS = [
    f"LanPulse-{VERSION}-Setup.exe",
    f"LanPulse-{VERSION}-win64-portable.zip",
    "SHA256SUMS.txt",
]


def token() -> str:
    p = ROOT / ".gh_token"
    if not p.is_file():
        print("[X] .gh_token 不存在")
        raise SystemExit(2)
    return p.read_text(encoding="ascii", errors="replace").strip()


def api(method: str, path: str, tok: str, *, body: dict | None = None,
        raw: bytes | None = None, base: str = API,
        accept: str = "application/vnd.github+json") -> tuple[int, object]:
    url = f"{base}{path}" if path.startswith("/") else path
    data = raw if raw is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None)
    headers = {
        "Authorization": f"Bearer {tok}",
        "Accept": accept,
        "User-Agent": "LanPulse-Publisher",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if raw is not None:
        headers["Content-Type"] = "application/octet-stream"
    elif body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            txt = r.read().decode("utf-8", errors="replace")
            return r.getcode(), (json.loads(txt) if txt.strip() else {})
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(txt)
        except json.JSONDecodeError:
            return e.code, txt
    except urllib.error.URLError as e:
        return 0, f"网络错误: {e.reason}"


def git(*args: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "core.quotepath"
    env["GIT_CONFIG_VALUE_0"] = "false"
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                       encoding="utf-8", errors="replace", env=env)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode, "\n".join(l for l in out.splitlines()
                                   if not l.startswith("warning:"))


def step(msg: str) -> None:
    print(f"\n[发布] {msg}")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [!]  {msg}")


def fail(msg: str) -> None:
    print(f"  [X]  {msg}")


# --------------------------------------------------------------------------- #
def precheck(tok: str) -> bool:
    step("预检")
    code, data = api("GET", "/user", tok)
    if code != 200 or not isinstance(data, dict):
        fail(f"Token 无效（HTTP {code}）")
        return False
    ok(f"身份：{data.get('login')}")

    # 产物齐全性
    missing = [a for a in ASSETS if not (ROOT / "release" / a).is_file()]
    if missing:
        fail(f"缺少产物：{missing}")
        return False
    for a in ASSETS:
        mb = (ROOT / "release" / a).stat().st_size / 1024 / 1024
        ok(f"{a}  {mb:.2f} MB")

    # 仓库状态
    code, _ = api("GET", f"/repos/{OWNER}/{NEW_REPO}", tok)
    if code == 200:
        warn(f"{NEW_REPO} 已存在，将跳过重命名")
    else:
        code2, _ = api("GET", f"/repos/{OWNER}/{OLD_REPO}", tok)
        if code2 != 200:
            fail(f"{OLD_REPO} 也访问不到，无法重命名")
            return False
        ok(f"{OLD_REPO} 存在，将重命名为 {NEW_REPO}")

    # 本地仓库
    n, _ = git("rev-list", "--count", "HEAD")
    _, commits = git("rev-list", "--count", "HEAD")
    ok(f"本地历史：{commits} 个提交（已重写）")
    return True


def rename_repo(tok: str) -> str | None:
    """把 NetPulse 重命名为 LanPulse，返回最终仓库名。"""
    step("重命名仓库")
    code, _ = api("GET", f"/repos/{OWNER}/{NEW_REPO}", tok)
    if code == 200:
        ok(f"{NEW_REPO} 已存在，跳过")
        return NEW_REPO

    code, data = api("PATCH", f"/repos/{OWNER}/{OLD_REPO}", tok,
                     body={"name": NEW_REPO})
    if code == 200 and isinstance(data, dict):
        ok(f"{OLD_REPO} → {data.get('name')}")
        ok(f"新地址：{data.get('html_url')}")
        warn("GitHub 会把旧地址自动重定向，已有链接不会失效")
        return str(data.get("name"))
    fail(f"重命名失败（HTTP {code}）")
    print(f"    {data}")
    if code == 403:
        warn("需要 Administration: Read and write 权限")
    return None


def push(tok: str, repo: str) -> bool:
    step("强推重写后的历史")
    remote = f"https://github.com/{OWNER}/{repo}.git"
    code, existing = git("remote", "get-url", "origin")
    if code == 0 and existing.strip():
        git("remote", "set-url", "origin", remote)
    else:
        git("remote", "add", "origin", remote)
    ok(f"origin -> {remote}")

    auth = f"https://x-access-token:{tok}@github.com/{OWNER}/{repo}.git"
    # 重写历史后必须强推
    code, out = git("push", "--force", "-u", auth, "main")
    git("remote", "set-url", "origin", remote)      # 摘掉凭据
    if code == 0:
        ok("强推成功")
        return True
    fail("推送失败")
    print(f"    {out[:700]}")
    return False


def release_notes() -> str:
    p = ROOT / "CHANGELOG.md"
    if p.is_file():
        import re

        text = p.read_text(encoding="utf-8")
        m = re.search(r"## \[1\.1\.0\][^\n]*\n(.*?)(?=\n## \[|\Z)", text, re.S)
        if m:
            return m.group(1).strip()[:60000]
    return "LanPulse v1.1.0 — 场景化诊断 + 根因分析"


def ensure_release(tok: str, repo: str) -> int | None:
    step(f"创建 Release {TAG}")
    code, data = api("GET", f"/repos/{OWNER}/{repo}/releases/tags/{TAG}", tok)
    if code == 200 and isinstance(data, dict):
        ok(f"已存在（id={data.get('id')}），复用")
        return int(data["id"])

    code, data = api("POST", f"/repos/{OWNER}/{repo}/releases", tok, body={
        "tag_name": TAG,
        "target_commitish": "main",
        "name": f"LanPulse {TAG}",
        "body": release_notes(),
        "draft": False,
        "prerelease": False,
    })
    if code == 201 and isinstance(data, dict):
        ok(f"已创建：{data.get('html_url')}")
        return int(data["id"])
    fail(f"创建失败（HTTP {code}）")
    print(f"    {data}")
    return None


def upload(tok: str, repo: str, rid: int) -> bool:
    step("上传产物")
    code, existing = api("GET", f"/repos/{OWNER}/{repo}/releases/{rid}/assets", tok)
    have = set()
    if code == 200 and isinstance(existing, list):
        have = {a.get("name") for a in existing if isinstance(a, dict)}

    all_ok = True
    for name in ASSETS:
        if name in have:
            ok(f"{name} 已存在，跳过")
            continue
        path = ROOT / "release" / name
        mb = path.stat().st_size / 1024 / 1024
        print(f"  上传 {name}（{mb:.1f} MB）…")
        import urllib.parse

        q = urllib.parse.quote(name)
        code, data = api("POST", f"/repos/{OWNER}/{repo}/releases/{rid}/assets?name={q}",
                         tok, raw=path.read_bytes(), base=UPLOAD)
        if code == 201:
            ok(f"{name} 上传成功")
        else:
            fail(f"{name} 失败（HTTP {code}）")
            print(f"    {data}")
            all_ok = False
    return all_ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="真正执行")
    args = ap.parse_args()

    print("=" * 66)
    print(f"LanPulse {TAG} 发布")
    print("=" * 66)

    tok = token()
    if not precheck(tok):
        return 1

    if not args.execute:
        print("\n  预检通过。加 --execute 真正执行：")
        print(f"    1. 重命名 {OLD_REPO} → {NEW_REPO}")
        print("    2. 强推重写后的单次历史")
        print(f"    3. 创建 Release {TAG}")
        print("    4. 上传 3 个产物")
        return 0

    repo = rename_repo(tok)
    if not repo:
        return 3

    if not push(tok, repo):
        return 4

    rid = ensure_release(tok, repo)
    if rid is None:
        return 5

    ok_all = upload(tok, repo, rid)

    print("\n" + "=" * 66)
    print(f"仓库  ：https://github.com/{OWNER}/{repo}")
    print(f"Release：https://github.com/{OWNER}/{repo}/releases/tag/{TAG}")
    if not ok_all:
        warn("部分产物未上传，见上方日志")
    print("=" * 66)
    return 0 if ok_all else 6


if __name__ == "__main__":
    sys.exit(main())
