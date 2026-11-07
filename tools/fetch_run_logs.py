r"""抓取某次工作流运行的失败日志（带重试）。

用法：
    python tools/fetch_run_logs.py <run_id>
"""
from __future__ import annotations

import json
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


def tok() -> str:
    return (ROOT / ".gh_token").read_text(encoding="ascii", errors="replace").strip()


def fetch(path: str, *, accept: str = "application/vnd.github+json",
          retries: int = 4) -> bytes:
    """带重试的 GET。日志端点偶尔会因为连接被重置而失败。"""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(API + path, headers={
                "Authorization": f"Bearer {tok()}",
                "Accept": accept,
                "User-Agent": "LanPulse-Verify",
                "X-GitHub-Api-Version": "2022-11-28",
            })
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except (urllib.error.URLError, ConnectionResetError, TimeoutError) as exc:
            last = exc
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"抓取失败（已重试 {retries} 次）: {last}")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    run_id = argv[0]

    jobs = json.loads(fetch(f"/repos/{OWNER}/{REPO}/actions/runs/{run_id}/jobs"))
    for job in jobs.get("jobs", []):
        print(f"作业：{job['name']}  结论={job['conclusion']}")
        for step in job.get("steps", []):
            mark = step.get("conclusion") or "?"
            print(f"  [{mark}] {step['name']}")
        print()

        if job.get("conclusion") == "success":
            continue

        print("--- 失败步骤日志 ---")
        try:
            raw = fetch(f"/repos/{OWNER}/{REPO}/actions/jobs/{job['id']}/logs",
                        accept="application/vnd.github.raw")
            text = raw.decode("utf-8", errors="replace")
        except RuntimeError as exc:
            print(f"  (无法抓取日志: {exc})")
            continue

        lines = [ln.rstrip() for ln in text.splitlines()]
        # 优先打印错误标记行及其上下文
        err_idx = [i for i, ln in enumerate(lines)
                   if "##[error]" in ln or "FAILED" in ln or "Error:" in ln]
        if err_idx:
            for i in err_idx[:6]:
                print(f"  >>> {lines[i][:300]}")
                for ctx in lines[i + 1: i + 6]:
                    if ctx.strip():
                        print(f"      {ctx[:300]}")
                print()
        else:
            print("  （无显式错误标记，打印最后 40 行）")
            for ln in lines[-40:]:
                print(f"  {ln[:300]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
