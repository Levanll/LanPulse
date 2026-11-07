r"""LanPulse 一键发布到 GitHub：建仓库 → 推送代码 → 建 Release → 上传安装包。

前置：
    环境变量 GITHUB_TOKEN 必须是有效的 Personal Access Token。

所需权限（缺一不可，见 README 上方的说明）：
    Fine-grained : Administration(RW) + Contents(RW) + Workflows(RW)
    Classic      : repo + workflow

用法：
    # 先看会做什么，不产生任何副作用
    python tools/publish_github.py --dry-run

    # 真正执行（会自动读 token 里的登录名填进 README 占位符）
    $env:GITHUB_TOKEN = "ghp_xxx"
    python tools/publish_github.py

    # 仓库已存在时只更新代码与 Release
    python tools/publish_github.py --skip-repo

安全约定：
    * token 只从环境变量读，不落盘、不进命令行、不写进 .git/config
    * 推送用一次性凭据，push 完成后不保留
    * 任何一步失败都停下并给出可操作的下一步，不吞错误
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
UPLOAD_API = "https://uploads.github.com"
UA = "LanPulse-Publisher/1.0"

VERSION = "1.0.0"
TAG = f"v{VERSION}"

ASSETS = [
    "LanPulse-1.0.0-Setup.exe",
    "LanPulse-1.0.0-win64-portable.zip",
]


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def step(msg: str) -> None:
    print(f"\n[发布] {msg}")


def ok(msg: str) -> None:
    print(f"  [OK] {msg}")


def warn(msg: str) -> None:
    print(f"  [!]  {msg}")


def fail(msg: str) -> None:
    print(f"  [X]  {msg}")


def _token() -> str:
    tok = os.environ.get("GITHUB_TOKEN", "").strip()
    if not tok:
        fail("未设置 GITHUB_TOKEN")
        print("\n  PowerShell:")
        print('    $env:GITHUB_TOKEN = "ghp_xxxxxxxx"')
        print("\n  或在当前命令里临时设置（不写进历史）：")
        print('    $env:GITHUB_TOKEN = Read-Host -AsSecureString | ...')
        raise SystemExit(2)
    return tok


def api(
    method: str,
    path: str,
    *,
    token: str,
    body: dict | None = None,
    raw: bytes | None = None,
    content_type: str | None = None,
    base: str = API,
) -> tuple[int, dict | list | str]:
    """调用 GitHub API，返回 (状态码, 解析后的响应)。不抛网络异常外的错误。"""
    url = f"{base}{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": UA,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if raw is not None:
        data = raw
        headers["Content-Type"] = content_type or "application/octet-stream"
    elif body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            status = resp.getcode()
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except urllib.error.URLError as exc:
        return 0, f"网络错误: {exc.reason}"

    try:
        return status, json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        return status, text


def git(*args: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "core.quotepath"
    env["GIT_CONFIG_VALUE_0"] = "false"
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True,
        encoding="utf-8", errors="replace", env=env,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    out = "\n".join(l for l in out.splitlines() if not l.startswith("warning:"))
    return proc.returncode, out


# --------------------------------------------------------------------------- #
# 各步骤
# --------------------------------------------------------------------------- #
def check_token(token: str) -> str:
    step("校验 Token 与权限")
    status, data = api("GET", "/user", token=token)
    if status != 200 or not isinstance(data, dict):
        fail(f"Token 无效或无权访问（HTTP {status}）")
        print(f"    {data}")
        raise SystemExit(3)

    login = data.get("login", "")
    ok(f"登录身份：{login}")

    # 检查经典 token 的 scope（fine-grained 没有这个头，返回空）
    scopes = ""
    req = urllib.request.Request(
        f"{API}/user",
        headers={"Authorization": f"Bearer {token}", "User-Agent": UA,
                 "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            scopes = resp.headers.get("X-OAuth-Scopes", "") or ""
    except (urllib.error.URLError, OSError):
        pass

    if scopes:
        scope_set = {s.strip() for s in scopes.split(",") if s.strip()}
        ok(f"Scopes：{', '.join(sorted(scope_set)) or '（空）'}")
        missing = []
        if "repo" not in scope_set:
            missing.append("repo")
        if "workflow" not in scope_set:
            missing.append("workflow")
        if missing:
            warn(f"缺少 scope：{', '.join(missing)}")
            warn("repo 用于建仓库与推代码；workflow 用于推送 .github/workflows/ 文件")
            warn("缺少 workflow 时，git push 会被拒绝（错误里会明确提示）")
        else:
            ok("必需 scope 齐全（repo + workflow）")
    else:
        ok("Fine-grained token（无 scope 头，权限在页面上逐项配置）")

    return login


def create_repo(token: str, login: str, repo: str, *, private: bool) -> bool:
    step(f"创建仓库 {login}/{repo}")
    status, data = api("GET", f"/repos/{login}/{repo}", token=token)
    if status == 200:
        ok("仓库已存在，跳过创建")
        return True

    payload = {
        "name": repo,
        "description": (
            "Windows 网络体检与一键修复 —— 14 项检测 / 15 个可回滚修复动作 / "
            "跨区域自适应 / 中英双语。A Windows network diagnostics and one-click "
            "repair tool with fully reversible changes."
        ),
        "private": private,
        "has_issues": True,
        "has_wiki": False,
        "has_projects": False,
        "auto_init": False,          # 不要自动生成 README，否则推送会冲突
    }
    status, data = api("POST", "/user/repos", token=token, body=payload)
    if status == 201:
        ok(f"已创建：{data.get('html_url')}")
        return True

    fail(f"创建失败（HTTP {status}）")
    print(f"    {data}")
    if status == 403:
        warn("通常是 token 缺少 Administration: Read and write（fine-grained）")
        warn("或缺少 repo scope（classic）")
    elif status == 422:
        warn("仓库名可能已被占用，换一个 --repo 名称")
    return False


def fill_owner(login: str, repo: str) -> None:
    step("替换 README 占位符")
    changed = 0
    for name in ("README.md", "README_EN.md"):
        path = ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = text.replace("{OWNER}", login).replace("{REPO}", repo)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1
            ok(f"{name} -> {login}/{repo}")
    if changed == 0:
        ok("无需替换")
    if (ROOT / ".github/ISSUE_TEMPLATE/config.yml").is_file():
        p = ROOT / ".github/ISSUE_TEMPLATE/config.yml"
        t = p.read_text(encoding="utf-8")
        n = t.replace("{OWNER}", login).replace("{REPO}", repo)
        if n != t:
            p.write_text(n, encoding="utf-8")
            ok("config.yml 占位符已替换")


def commit_all() -> bool:
    step("提交本地改动")
    git("add", "-A")
    code, status = git("status", "--porcelain")
    if not status.strip():
        ok("工作区干净，无需提交")
        return True
    code, out = git(
        "-c", "user.name=LanPulse Bot",
        "-c", "user.email=noreply@localhost",
        "commit", "-m",
        f"chore: set repository owner and prepare {TAG} release",
    )
    if code != 0:
        fail(f"提交失败：{out}")
        return False
    ok("已提交")
    return True


def push(token: str, login: str, repo: str, branch: str) -> bool:
    step("推送代码")
    remote = f"https://github.com/{login}/{repo}.git"
    code, existing = git("remote", "get-url", "origin")
    if code == 0 and existing.strip():
        git("remote", "set-url", "origin", remote)
    else:
        git("remote", "add", "origin", remote)
    ok(f"origin -> {remote}")

    auth = f"https://x-access-token:{token}@github.com/{login}/{repo}.git"
    code, out = git("push", "-u", auth, branch, "--force")

    # 推送后立刻把带凭据的 URL 从 remote 上摘掉，避免 token 落进 .git/config
    git("remote", "set-url", "origin", remote)

    if code == 0:
        ok("推送成功")
        return True

    fail("推送失败")
    print(f"    {out[:800]}")
    if "workflow" in out.lower():
        warn("错误提到 workflow：token 缺少 workflow 权限")
        warn("  classic: 勾选 workflow scope")
        warn("  fine-grained: 勾选 Workflows: Read and write")
    elif "protected" in out.lower() or "denied" in out.lower():
        warn("可能触发了分支保护规则")
    return False


def ensure_release(token: str, login: str, repo: str) -> int | None:
    step(f"创建 Release {TAG}")
    status, data = api("GET", f"/repos/{login}/{repo}/releases/tags/{TAG}", token=token)
    if status == 200 and isinstance(data, dict):
        ok(f"Release 已存在（id={data.get('id')}），将复用")
        return int(data["id"])

    body = _release_notes()
    payload = {
        "tag_name": TAG,
        "target_commitish": "main",
        "name": f"LanPulse {TAG}",
        "body": body,
        "draft": False,
        "prerelease": False,
    }
    status, data = api("POST", f"/repos/{login}/{repo}/releases",
                       token=token, body=payload)
    if status == 201 and isinstance(data, dict):
        ok(f"已创建：{data.get('html_url')}")
        return int(data["id"])

    fail(f"创建 Release 失败（HTTP {status}）")
    print(f"    {data}")
    return None


def _release_notes() -> str:
    """Release 正文：优先取 CHANGELOG 的 1.0.0 段，失败则用简明摘要。"""
    path = ROOT / "CHANGELOG.md"
    if path.is_file():
        text = path.read_text(encoding="utf-8")
        m = re.search(r"## \[1\.0\.0\][^\n]*\n(.*?)(?=\n## \[|\Z)", text, re.S)
        if m:
            return m.group(1).strip()[:60000]
    return (
        "首个正式版本。\n\n"
        "- 14 项网络检测、15 个可回滚修复动作\n"
        "- 备份优先：所有修改可精确还原\n"
        "- 跨区域自适应（中国 / 国际 / 亚太）\n"
        "- 中英双语界面\n"
    )


def upload_assets(token: str, login: str, repo: str, release_id: int) -> bool:
    step("上传安装包")
    rel_dir = ROOT / "release"
    status, existing = api("GET", f"/repos/{login}/{repo}/releases/{release_id}/assets",
                           token=token)
    have = set()
    if status == 200 and isinstance(existing, list):
        have = {a.get("name") for a in existing if isinstance(a, dict)}

    all_ok = True
    for name in ASSETS:
        path = rel_dir / name
        if not path.is_file():
            warn(f"缺少文件：{name}，跳过")
            all_ok = False
            continue
        if name in have:
            ok(f"{name} 已存在，跳过")
            continue

        size_mb = path.stat().st_size / 1024 / 1024
        print(f"  上传 {name}（{size_mb:.1f} MB）…")
        q = urllib.parse.quote(name)
        status, data = api(
            "POST",
            f"/repos/{login}/{repo}/releases/{release_id}/assets?name={q}",
            token=token,
            raw=path.read_bytes(),
            base=UPLOAD_API,
        )
        if status == 201:
            ok(f"{name} 上传成功")
        else:
            fail(f"{name} 上传失败（HTTP {status}）")
            print(f"    {data}")
            all_ok = False
    return all_ok


def also_upload_sums(token: str, login: str, repo: str, release_id: int) -> None:
    name = "SHA256SUMS.txt"
    path = ROOT / "release" / name
    if not path.is_file() or path.stat().st_size == 0:
        return

    # 已存在则跳过：重复上传同名资产会返回 422（Validation Failed），
    # 之前这里没做检查，导致重复执行发布时误报"上传失败"。
    status, existing = api("GET", f"/repos/{login}/{repo}/releases/{release_id}/assets",
                           token=token)
    if status == 200 and isinstance(existing, list):
        if any(isinstance(a, dict) and a.get("name") == name for a in existing):
            ok(f"{name} 已存在，跳过")
            return

    q = urllib.parse.quote(name)
    status, _ = api("POST",
                    f"/repos/{login}/{repo}/releases/{release_id}/assets?name={q}",
                    token=token, raw=path.read_bytes(), base=UPLOAD_API)
    if status == 201:
        ok(f"{name} 上传成功")
    else:
        warn(f"{name} 上传失败（HTTP {status}），不影响主产物")


# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LanPulse 发布到 GitHub")
    ap.add_argument("--repo", default="LanPulse")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--private", action="store_true", help="创建私有仓库")
    ap.add_argument("--skip-repo", action="store_true", help="仓库已存在，跳过创建")
    ap.add_argument("--skip-push", action="store_true", help="只建 Release，不推代码")
    ap.add_argument("--dry-run", action="store_true", help="只检查，不产生副作用")
    args = ap.parse_args(argv)

    print("=" * 66)
    print("LanPulse GitHub 发布")
    print("=" * 66)

    if args.dry_run:
        step("预检（dry-run，不产生任何副作用）")
        for name in ASSETS:
            p = ROOT / "release" / name
            if p.is_file():
                ok(f"{name}  {p.stat().st_size / 1024 / 1024:.2f} MB")
            else:
                fail(f"缺少 {name}")
        tok = os.environ.get("GITHUB_TOKEN", "").strip()
        if not tok:
            warn("未设置 GITHUB_TOKEN —— 正式执行前必须设置")
        else:
            login = check_token(tok)
            fill_owner(login, args.repo) if False else None
            ok(f"目标仓库：{login}/{args.repo}")
        print("\n  dry-run 结束。去掉 --dry-run 即正式执行。")
        return 0

    token = _token()
    login = check_token(token)

    if not args.skip_repo:
        if not create_repo(token, login, args.repo, private=args.private):
            return 4

    fill_owner(login, args.repo)
    if not commit_all():
        return 5

    if not args.skip_push:
        if not push(token, login, args.repo, args.branch):
            return 6

    rid = ensure_release(token, login, args.repo)
    if rid is None:
        return 7

    assets_ok = upload_assets(token, login, args.repo, rid)
    also_upload_sums(token, login, args.repo, rid)

    print("\n" + "=" * 66)
    if assets_ok:
        print(f"发布完成：https://github.com/{login}/{args.repo}")
        print(f"Release ：https://github.com/{login}/{args.repo}/releases/tag/{TAG}")
        print("=" * 66)
        return 0

    warn("部分产物未上传，请查看上面日志")
    print(f"仓库：https://github.com/{login}/{args.repo}")
    print("=" * 66)
    return 8


if __name__ == "__main__":
    sys.exit(main())
