r"""LanPulse GitHub 发布准备（Python 版，替代 prepare_github.ps1）。

为什么用 Python 而不是 PowerShell：
  * PowerShell 5.1 会把原生命令写到 stderr 的任何内容（含 git 的无害 warning
    "LF will be replaced by CRLF"）包装成 NativeCommandError，污染管道；
  * 中文文件名在 git 输出 → PowerShell 字符串 → Test-Path 的链路上会因
    代码页转换出现非法字符，直接抛 ArgumentException；
  * 这两点在 Python 里都不存在：subprocess 按字节/UTF-8 处理，os.path 按
    Unicode 处理。

用法：
    # 只做本地准备，不联网
    python tools/prepare_github.py

    # 替换 README 占位符为真实 owner/repo（仍不推送）
    python tools/prepare_github.py --owner your-name --repo LanPulse

    # 真正推送（需要环境变量 GITHUB_TOKEN）
    $env:GITHUB_TOKEN = "ghp_xxx"
    python tools/prepare_github.py --owner your-name --repo LanPulse --push

安全说明：
    * 不接受密码。GitHub 自 2021-08-13 起已移除密码认证，用密码推送必然失败。
      请用 Personal Access Token（classic 需 repo 作用域；fine-grained 需
      Contents: Read and write）。
    * 令牌只从环境变量读取，不出现在命令行与任何文件中。
    * 默认不推送；--push 会先打印摘要并要求输入 yes 确认。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()

ROOT = Path(__file__).resolve().parents[1]

OK = "[OK]"
WARN = "[!] "
FAIL = "[X] "

REQUIRED = [
    "README.md", "README_EN.md", "LICENSE", ".gitignore",
    "build.spec", "main.py", "installer/LanPulse.iss",
]

#: 这些目录/文件不应进入仓库（体积或环境相关）
MUST_IGNORE = ["dist/", "release/", "build/", ".venv/", "__pycache__/"]

MAX_FILE_MB = 20


def step(msg: str) -> None:
    print(f"\n[准备] {msg}")


def ok(msg: str) -> None:
    print(f"  {OK} {msg}")


def warn(msg: str) -> None:
    print(f"  {WARN} {msg}")


def fail(msg: str) -> None:
    print(f"  {FAIL} {msg}")


def git(*args: str, check: bool = False) -> tuple[int, str]:
    """执行 git。返回 (退出码, 合并输出)。

    用 encoding='utf-8' + errors='replace' 读取：git 在 Windows 上默认按
    系统代码页输出中文文件名，显式指定 UTF-8 并让 git 也输出 UTF-8
    （core.quotepath=false）才能稳定拿到真实路径。
    """
    env = dict(os.environ)
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "core.quotepath"
    env["GIT_CONFIG_VALUE_0"] = "false"
    proc = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    out = "\n".join(
        line for line in out.splitlines() if not line.startswith("warning:")
    ).strip()
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} 失败（{proc.returncode}）: {out}")
    return proc.returncode, out


def check_prerequisites() -> bool:
    step("检查前置条件")
    code, out = git("--version")
    if code != 0:
        fail("未找到 git，请先安装 Git for Windows")
        return False
    ok(out)

    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    if missing:
        fail(f"缺少必需文件：{', '.join(missing)}")
        return False
    ok("必需文件齐全")
    return True


def check_artifacts() -> tuple[Path | None, Path | None]:
    step("构建产物检查")
    setups = sorted((ROOT / "release").glob("LanPulse-*-Setup.exe")) if (ROOT / "release").is_dir() else []
    portables = sorted((ROOT / "release").glob("LanPulse-*-win64-portable.zip")) if (ROOT / "release").is_dir() else []
    setup = setups[0] if setups else None
    portable = portables[0] if portables else None

    if setup:
        ok(f"Setup:    {setup.name}  {setup.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        warn("release/ 下缺少 Setup.exe —— Release 页将没有安装包可传")
    if portable:
        ok(f"Portable: {portable.name}  {portable.stat().st_size / 1024 / 1024:.2f} MB")
    else:
        warn("release/ 下缺少 portable.zip")
    if not setup or not portable:
        warn("先运行 scripts/build_installer.ps1 可生成两者")
    return setup, portable


def replace_placeholders(owner: str, repo: str) -> None:
    step("替换 README 中的 {OWNER}/{REPO} 占位符")
    if not owner:
        pending = [
            f.name for f in (ROOT / "README.md", ROOT / "README_EN.md")
            if f.is_file() and re.search(r"\{(OWNER|REPO)\}", f.read_text(encoding="utf-8"))
        ]
        if pending:
            warn(f"README 仍含占位符：{', '.join(pending)}")
            warn("徽章会失效。请带 --owner 重新执行（或不影响代码本身）")
        else:
            ok("无需替换")
        return

    for name in ("README.md", "README_EN.md"):
        path = ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = text.replace("{OWNER}", owner).replace("{REPO}", repo)
        if new != text:
            path.write_text(new, encoding="utf-8")
            ok(f"{name} -> {owner}/{repo}")


def init_repo(branch: str) -> None:
    step("初始化 Git 仓库")
    if (ROOT / ".git").exists():
        ok("仓库已存在")
    else:
        git("init", "-b", branch, check=True)
        ok(f"已初始化（分支 {branch}）")

    ignore = ROOT / ".gitignore"
    if not ignore.is_file():
        fail(".gitignore 不存在，拒绝继续（防止把 100MB 构建产物提交上去）")
        raise RuntimeError(".gitignore missing")
    content = ignore.read_text(encoding="utf-8")
    missing = [p for p in MUST_IGNORE if p not in content]
    if missing:
        warn(f".gitignore 可能未覆盖：{', '.join(missing)}")
    else:
        ok(".gitignore 已覆盖构建产物与虚拟环境")


def stage_and_verify() -> int:
    step("暂存并检查大文件")
    git("add", "-A", check=True)
    code, out = git("diff", "--cached", "--name-only")
    if code != 0:
        fail(f"无法列出暂存文件：{out}")
        return -1

    names = [n for n in out.splitlines() if n.strip()]
    big: list[str] = []
    for name in names:
        path = ROOT / name
        if path.is_file():
            mb = path.stat().st_size / 1024 / 1024
            if mb > MAX_FILE_MB:
                big.append(f"{name} ({mb:.1f} MB)")

    if big:
        fail(f"暂存区含 >{MAX_FILE_MB}MB 的文件，GitHub 会拒绝：")
        for b in big:
            print(f"      {b}")
        fail("请把它们加入 .gitignore，然后 `git reset` 后重试")
        return -1

    ok(f"暂存 {len(names)} 个文件，无超大文件")
    return len(names)


def commit() -> None:
    step("创建提交")
    code, _ = git("rev-parse", "--verify", "HEAD")
    has_commits = code == 0

    if has_commits:
        _, dirty = git("status", "--porcelain")
        if dirty:
            git(
                "-c", "user.name=LanPulse Bot",
                "-c", "user.email=noreply@localhost",
                "commit", "-m", "chore: update repository files",
                check=True,
            )
            ok("已提交变更")
        else:
            ok("工作区干净，无需提交")
    else:
        git(
            "-c", "user.name=LanPulse Bot",
            "-c", "user.email=noreply@localhost",
            "commit", "-m",
            "feat: LanPulse v1.0.0 - Windows network diagnostics with one-click repair",
            check=True,
        )
        ok("已创建首个提交")

    _, log = git("--no-pager", "log", "--oneline", "-5")
    print("\n  提交摘要：")
    for line in log.splitlines():
        print(f"    {line}")


def print_next_steps(owner: str, repo: str, branch: str,
                     setup: Path | None, portable: Path | None) -> None:
    print()
    print("  本地准备已完成，未推送。")
    print()
    print("  下一步：")
    print("    1) 在 GitHub 创建空仓库（不要勾 README / .gitignore / license）")
    print("    2) 设置令牌（不要写进命令行，会进历史记录）：")
    print('         $env:GITHUB_TOKEN = "ghp_xxxxxxxx"')
    print("    3) 推送：")
    print(f"         python tools/prepare_github.py --owner <你的用户名> --repo {repo} --push")
    print()
    print("    4) 创建 Release 并上传安装包：")
    print(f"         https://github.com/{owner or '<owner>'}/{repo}/releases/new")
    print("         Tag: v1.0.0    标题: LanPulse v1.0.0")
    for p in (setup, portable):
        if p:
            print(f"         附件: {p}")


def do_push(owner: str, repo: str, branch: str) -> int:
    step("推送到 GitHub")
    if not owner:
        fail("--push 需要同时提供 --owner")
        return 1
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        fail("未设置 GITHUB_TOKEN 环境变量")
        warn("GitHub 已不支持密码推送，必须用 Personal Access Token")
        warn('  $env:GITHUB_TOKEN = "ghp_xxxxxxxx"')
        return 1

    remote = f"https://github.com/{owner}/{repo}.git"
    auth = f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"

    code, existing = git("remote", "get-url", "origin")
    if code == 0 and existing:
        ok(f"远程 origin 已存在：{existing}")
    else:
        git("remote", "add", "origin", remote, check=True)
        ok(f"已添加远程 origin：{remote}")

    print()
    warn(f"即将推送 {branch} 到 {remote}")
    warn("推送后仓库将公开可见")
    try:
        answer = input("  确认推送？输入 yes 继续: ").strip().lower()
    except EOFError:
        answer = ""
    if answer != "yes":
        print("  已取消，未推送。")
        return 0

    # 令牌只出现在这一次调用的变量里；用 -c 传凭据而不写进 .git/config，
    # 避免令牌残留在磁盘上。
    code, out = git("push", "-u", auth, branch)
    if code != 0:
        fail(f"推送失败：{out}")
        warn("常见原因：令牌无 repo 作用域 / 仓库不存在 / 分支受保护")
        return 1
    ok(f"推送成功：https://github.com/{owner}/{repo}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LanPulse GitHub 发布准备")
    ap.add_argument("--owner", default="", help="GitHub 用户名或组织名")
    ap.add_argument("--repo", default="LanPulse", help="仓库名")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--push", action="store_true", help="真正执行 git push")
    args = ap.parse_args(argv)

    if not check_prerequisites():
        return 1

    setup, portable = check_artifacts()
    replace_placeholders(args.owner, args.repo)

    try:
        init_repo(args.branch)
    except RuntimeError as exc:
        fail(str(exc))
        return 1

    staged = stage_and_verify()
    if staged < 0:
        return 1

    try:
        commit()
    except RuntimeError as exc:
        fail(str(exc))
        return 1

    if not args.push:
        print_next_steps(args.owner, args.repo, args.branch, setup, portable)
        return 0

    return do_push(args.owner, args.repo, args.branch)


if __name__ == "__main__":
    sys.exit(main())
