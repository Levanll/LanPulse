"""把三个 Release 的说明更新为中英对照。

用户要求：
  * 每个版本的描述改为中英对照，先中文后英文（与仓库 About 的格式一致）
  * 不改版本号，只更新描述
  * 更新后直接提交到 GitHub

只改 body，不动 tag、资产与版本号。
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"D:\Documents\deepseek-harness\default-workspace\lanpulse")
sys.path.insert(0, str(ROOT / "tools"))
try:
    from _console import setup_console

    setup_console()
except ImportError:
    pass

API = "https://api.github.com"
OWNER = "Levanll"
REPO = "LanPulse"
BODIES = ROOT / "docs" / "release-notes"
TAGS = ("v1.1.0", "v1.2.0", "v1.2.1")


def token() -> str:
    p = ROOT / ".gh_token"
    if not p.is_file():
        print("[X] .gh_token 不存在")
        raise SystemExit(2)
    return p.read_text(encoding="ascii", errors="replace").strip()


def api(method: str, path: str, tok: str, *, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        headers={
            "Authorization": "Bearer " + tok,
            "Accept": "application/vnd.github+json",
            "User-Agent": "LanPulse",
            "X-GitHub-Api-Version": "2022-11-28",
            **({"Content-Type": "application/json"} if data else {}),
        },
        method=method,
    )
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


SEPARATOR = "\n\n---\n\n<!-- English version below / 以下为英文版 -->\n\n"


def do_merge() -> int:
    """把 docs/release-notes 下的中文与英文稿合并成 <tag>.merged.md。"""
    tags = sorted({p.name.replace(".en.md", "").replace(".md", "")
                   for p in BODIES.glob("v*.md")
                   if ".merged" not in p.name})
    for tag in tags:
        zh_path = BODIES / f"{tag}.md"
        en_path = BODIES / f"{tag}.en.md"
        if not (zh_path.is_file() and en_path.is_file()):
            print(f"[!] {tag}: 缺少中文或英文稿")
            continue
        zh = zh_path.read_text(encoding="utf-8").strip()
        en = en_path.read_text(encoding="utf-8").strip()
        merged = zh + SEPARATOR + en + "\n"
        (BODIES / f"{tag}.merged.md").write_text(merged, encoding="utf-8")
        print(f"{tag}: 中文 {len(zh)} + 英文 {len(en)} = {len(merged)} 字符")
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "merge":
        return do_merge()

    tok = token()

    # 预检：确认 token 与仓库可访问
    code, me = api("GET", "/user", tok)
    if code != 200:
        print(f"[X] Token 无效（HTTP {code}）")
        return 1
    print(f"身份：{me.get('login')}\n")

    # 先取回当前状态，用于事后核对
    code, rels = api("GET", f"/repos/{OWNER}/{REPO}/releases", tok)
    if code != 200:
        print(f"[X] 读取 Release 失败（HTTP {code}）")
        return 1
    before = {r["tag_name"]: r for r in rels}

    failures = 0
    for tag in TAGS:
        if tag not in before:
            print(f"[!] {tag} 不存在，跳过")
            failures += 1
            continue

        rel = before[tag]
        rid = rel["id"]
        merged_path = BODIES / f"{tag}.merged.md"
        if not merged_path.is_file():
            print(f"[X] 缺少 {merged_path.name}")
            failures += 1
            continue
        body = merged_path.read_text(encoding="utf-8")

        print(f"[{tag}] id={rid}")
        print(f"  旧 body: {len(rel.get('body') or '')} 字符  资产 {len(rel['assets'])}")
        print(f"  新 body: {len(body)} 字符（中英对照）")

        code, data = api("PATCH", f"/repos/{OWNER}/{REPO}/releases/{rid}", tok,
                         body={"body": body})
        if code == 200:
            print(f"  [OK] 已更新")
        else:
            print(f"  [X] 更新失败（HTTP {code}）")
            print(f"      {data}")
            failures += 1
        print()

    # 事后核对
    print("=" * 66)
    code, rels2 = api("GET", f"/repos/{OWNER}/{REPO}/releases", tok)
    if code == 200:
        print("核对结果：")
        for r in rels2:
            body = r.get("body") or ""
            has_sep = "<!-- English version below" in body
            has_zh = "本次更新" in body or "首个公开版本" in body
            has_en = "## What's new" in body
            mark = "OK" if (has_sep and has_zh and has_en) else "FAIL"
            print(f"  [{mark}] {r['tag_name']}  body={len(body)} 字符  "
                  f"中文={has_zh} 分隔={has_sep} 英文={has_en}  "
                  f"资产={len(r['assets'])}")
    print("=" * 66)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
