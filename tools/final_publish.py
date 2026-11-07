r"""LanPulse 最终发布：清理旧版本 → 更新 About → 重建 Release → 推送。

按用户要求执行：
  1. 删除 v1.0.0 Release 与 tag（彻底移除旧版本痕迹）
  2. 更新仓库 About（描述 + topics）
  3. 重建 v1.1.0 Release 描述（当作全新产品表述，无旧版本内容）
  4. 强推所有提交
  5. 上传重新构建的安装包（替换旧构建）
  6. Packages 板块保持为空（用户选择方案 C）

用法：
    python tools/final_publish.py            # 预检
    python tools/final_publish.py --execute  # 执行
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
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
REPO = "LanPulse"
VERSION = "1.1.0"
TAG = f"v{VERSION}"
OLD_TAG = "v1.0.0"

ASSETS = [
    f"LanPulse-{VERSION}-Setup.exe",
    f"LanPulse-{VERSION}-win64-portable.zip",
    "SHA256SUMS.txt",
]

#: 仓库 About。描述要能一眼说清"这是什么"，topics 服务于搜索。
DESCRIPTION = (
    "Windows 网络体检与一键修复 —— 14 项检测 / 6 个场景 / 根因分析 / "
    "15 个可回滚修复动作 · 中英双语 · 全本地运行"
)
TOPICS = [
    "windows", "network", "diagnostics", "dns", "hosts", "mtu",
    "troubleshooting", "network-monitoring", "pyside6", "python",
    "system-tools", "bilingual",
]


def token() -> str:
    p = ROOT / ".gh_token"
    if not p.is_file():
        print("[X] .gh_token 不存在")
        raise SystemExit(2)
    return p.read_text(encoding="ascii", errors="replace").strip()


def api(method: str, path: str, tok: str, *, body: dict | None = None,
        raw: bytes | None = None, base: str = API) -> tuple[int, object]:
    url = f"{base}{path}" if path.startswith("/") else path
    data = raw if raw is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None)
    headers = {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
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


def step(m: str) -> None:
    print(f"\n[发布] {m}")


def ok(m: str) -> None:
    print(f"  [OK] {m}")


def warn(m: str) -> None:
    print(f"  [!]  {m}")


def fail(m: str) -> None:
    print(f"  [X]  {m}")


# --------------------------------------------------------------------------- #
def precheck(tok: str) -> bool:
    step("预检")
    code, data = api("GET", "/user", tok)
    if code != 200 or not isinstance(data, dict):
        fail(f"Token 无效（HTTP {code}）")
        return False
    ok(f"身份：{data.get('login')}")

    missing = [a for a in ASSETS if not (ROOT / "release" / a).is_file()]
    if missing:
        fail(f"缺少产物：{missing}")
        return False
    for a in ASSETS:
        mb = (ROOT / "release" / a).stat().st_size / 1024 / 1024
        ok(f"{a}  {mb:.2f} MB")

    code, repo = api("GET", f"/repos/{OWNER}/{REPO}", tok)
    if code != 200:
        fail(f"仓库不可访问（HTTP {code}）")
        return False
    ok(f"仓库：{repo.get('full_name')}（{repo.get('size')} KB）")

    code, rels = api("GET", f"/repos/{OWNER}/{REPO}/releases", tok)
    if code == 200 and isinstance(rels, list):
        ok(f"现有 Release {len(rels)} 个")
        for r in rels:
            print(f"       {r.get('tag_name')}  资产 {len(r.get('assets', []))}")
    return True


def delete_old_release(tok: str) -> bool:
    """删除 v1.0.0 的 Release 与 tag。"""
    step(f"删除旧版本 {OLD_TAG}")
    code, rel = api("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{OLD_TAG}", tok)
    if code == 200 and isinstance(rel, dict):
        rid = rel["id"]
        code2, _ = api("DELETE", f"/repos/{OWNER}/{REPO}/releases/{rid}", tok)
        if code2 == 204:
            ok(f"Release 已删除（id={rid}）")
        else:
            fail(f"删除 Release 失败（HTTP {code2}）")
            return False
    else:
        ok("Release 不存在，跳过")

    # 删除 tag 引用
    code, ref = api("GET", f"/repos/{OWNER}/{REPO}/git/ref/tags/{OLD_TAG}", tok)
    if code == 200:
        code2, _ = api("DELETE", f"/repos/{OWNER}/{REPO}/git/refs/tags/{OLD_TAG}", tok)
        if code2 == 204:
            ok(f"tag {OLD_TAG} 已删除")
        else:
            fail(f"删除 tag 失败（HTTP {code2}）")
            return False
    else:
        ok("tag 不存在，跳过")
    return True


def update_about(tok: str) -> bool:
    step("更新仓库 About")
    code, data = api("PATCH", f"/repos/{OWNER}/{REPO}", tok, body={
        "description": DESCRIPTION,
        "homepage": "",
    })
    if code != 200:
        fail(f"更新描述失败（HTTP {code}）")
        print(f"    {data}")
        return False
    ok("描述已更新")

    code, data = api("PUT", f"/repos/{OWNER}/{REPO}/topics", tok,
                     body={"names": TOPICS})
    if code == 200:
        got = data.get("names", []) if isinstance(data, dict) else []
        ok(f"topics 已设置（{len(got)} 个）")
    else:
        fail(f"设置 topics 失败（HTTP {code}）")
        print(f"    {data}")
        return False
    return True


def release_notes() -> str:
    p = ROOT / "CHANGELOG.md"
    if p.is_file():
        import re

        text = p.read_text(encoding="utf-8")
        m = re.search(rf"## \[{re.escape(VERSION)}\][^\n]*\n(.*?)(?=\n## \[|\Z)",
                      text, re.S)
        if m:
            return m.group(1).strip()[:60000]
    return f"LanPulse {VERSION}"


def rebuild_release(tok: str) -> int | None:
    """重建 v1.1.0 Release（删除旧的，用新描述重建）。"""
    step(f"重建 Release {TAG}")
    code, rel = api("GET", f"/repos/{OWNER}/{REPO}/releases/tags/{TAG}", tok)
    if code == 200 and isinstance(rel, dict):
        rid = rel["id"]
        code2, _ = api("DELETE", f"/repos/{OWNER}/{REPO}/releases/{rid}", tok)
        if code2 == 204:
            ok(f"旧 Release 已删除（id={rid}），将以新描述重建")
        else:
            warn(f"删除旧 Release 失败（HTTP {code2}），尝试复用")

    code, data = api("POST", f"/repos/{OWNER}/{REPO}/releases", tok, body={
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


def push(tok: str) -> bool:
    step("推送代码")
    remote = f"https://github.com/{OWNER}/{REPO}.git"
    code, existing = git("remote", "get-url", "origin")
    if code == 0 and existing.strip():
        git("remote", "set-url", "origin", remote)
    else:
        git("remote", "add", "origin", remote)
    ok(f"origin -> {remote}")

    auth = f"https://x-access-token:{tok}@github.com/{OWNER}/{REPO}.git"
    code, out = git("push", "--force", "-u", auth, "main")
    # 推送后立刻摘掉凭据，并修正 branch.main.remote
    git("remote", "set-url", "origin", remote)
    git("config", "--local", "branch.main.remote", "origin")
    git("config", "--local", "branch.main.merge", "refs/heads/main")

    if code == 0:
        ok("推送成功")
        return True
    fail("推送失败")
    print(f"    {out[:700]}")
    return False


def upload(tok: str, rid: int) -> bool:
    step("上传产物")
    code, existing = api("GET", f"/repos/{OWNER}/{REPO}/releases/{rid}/assets", tok)
    have = set()
    if code == 200 and isinstance(existing, list):
        have = {a.get("name") for a in existing if isinstance(a, dict)}

    all_ok = True
    for name in ASSETS:
        if name in have:
            # 同名资产必须先删再传，否则新构建的包不会被替换
            for a in existing:
                if a.get("name") == name:
                    api("DELETE", f"/repos/{OWNER}/{REPO}/releases/assets/{a['id']}", tok)
                    break
        path = ROOT / "release" / name
        mb = path.stat().st_size / 1024 / 1024
        print(f"  上传 {name}（{mb:.1f} MB）…")
        q = urllib.parse.quote(name)
        code, data = api("POST",
                         f"/repos/{OWNER}/{REPO}/releases/{rid}/assets?name={q}",
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
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    print("=" * 66)
    print(f"LanPulse {TAG} 最终发布")
    print("=" * 66)

    tok = token()
    if not precheck(tok):
        return 1

    if not args.execute:
        print("\n  预检通过。加 --execute 执行：")
        print(f"    1. 删除 {OLD_TAG} Release 与 tag")
        print("    2. 更新仓库 About（描述 + topics）")
        print(f"    3. 重建 {TAG} Release（新描述）")
        print("    4. 强推 3 个提交")
        print("    5. 上传 3 个产物（替换旧构建）")
        return 0

    if not delete_old_release(tok):
        return 3
    if not update_about(tok):
        return 4
    rid = rebuild_release(tok)
    if rid is None:
        return 5
    if not push(tok):
        return 6
    ok_all = upload(tok, rid)

    print("\n" + "=" * 66)
    print(f"仓库  ：https://github.com/{OWNER}/{REPO}")
    print(f"Release：https://github.com/{OWNER}/{REPO}/releases/tag/{TAG}")
    if not ok_all:
        warn("部分产物未上传")
    print("=" * 66)
    return 0 if ok_all else 7


if __name__ == "__main__":
    sys.exit(main())
