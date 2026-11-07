r"""触发并跟踪 Release 工作流（验证 CI 修复）。

用法：
    python tools/trigger_release.py              # 触发并等待
    python tools/trigger_release.py --watch-only # 只跟踪现有运行
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import sys as _sys
_sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from _console import setup_console as _setup_console
_setup_console()

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
OWNER, REPO = "Levanll", "LanPulse"
WORKFLOW = "release.yml"


def token() -> str:
    p = ROOT / ".gh_token"
    if not p.is_file():
        print("[X] .gh_token 不存在")
        raise SystemExit(2)
    return p.read_text(encoding="ascii", errors="replace").strip()


def call(method: str, path: str, tok: str, body: dict | None = None) -> tuple[int, object]:
    url = f"{API}{path}" if path.startswith("/") else path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {tok}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "LanPulse-Verify",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch-only", action="store_true")
    ap.add_argument("--tag", default="v1.0.0")
    args = ap.parse_args()

    tok = token()

    if not args.watch_only:
        print("=" * 62)
        print("触发 Release 工作流")
        print("=" * 62)
        code, data = call(
            "POST",
            f"/repos/{OWNER}/{REPO}/actions/workflows/{WORKFLOW}/dispatches",
            tok,
            {"ref": "main", "inputs": {"tag": args.tag}},
        )
        if code == 204:
            print("  [OK] 触发成功（HTTP 204）—— Actions: write 权限已生效")
        else:
            print(f"  [X]  触发失败（HTTP {code}）")
            print(f"      {data}")
            if code == 403:
                print("\n  提示：Fine-grained token 需勾选 Actions: Read and write")
            return 3

    # ---- 找到这次的运行 ----
    print("\n等待工作流启动…")
    run_id = None
    for _ in range(20):
        time.sleep(6)
        code, data = call(
            "GET", f"/repos/{OWNER}/{REPO}/actions/runs?per_page=10", tok
        )
        if code != 200 or not isinstance(data, dict):
            continue
        for run in data.get("workflow_runs", []):
            if run.get("path", "").endswith(WORKFLOW) and run.get("event") == "workflow_dispatch":
                run_id = run["id"]
                print(f"  找到运行 #{run.get('run_number')}  id={run_id}")
                print(f"  {run.get('html_url')}")
                break
        if run_id:
            break

    if not run_id:
        print("  [X] 未找到本次触发的工作流运行")
        return 4

    # ---- 跟踪到结束 ----
    print("\n跟踪执行状态（最长 20 分钟）…")
    last = ""
    for i in range(80):
        code, run = call("GET", f"/repos/{OWNER}/{REPO}/actions/runs/{run_id}", tok)
        if code != 200 or not isinstance(run, dict):
            time.sleep(10)
            continue
        status = run.get("status")
        conclusion = run.get("conclusion")
        if status != last:
            print(f"  [{time.strftime('%H:%M:%S')}] 状态={status}  结论={conclusion or '-'}")
            last = status
        if status == "completed":
            print()
            print("=" * 62)
            print(f"最终结论：{conclusion}")
            print("=" * 62)
            return 0 if conclusion == "success" else 5
        time.sleep(15)

    print("  超时，仍在运行")
    return 6


if __name__ == "__main__":
    sys.exit(main())
