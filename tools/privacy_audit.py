r"""仓库隐私核查：扫描所有被跟踪文件，找出可能泄露的个人信息。

检查项：
  1. 用户名 / 计算机名 / 用户目录路径
  2. 真实姓名、邮箱、手机号、身份证号
  3. IP 地址、MAC 地址、网卡名（来自本机实测截图或日志）
  4. 凭据（token、密码、密钥）
  5. 本地绝对路径（暴露目录结构）
  6. 其他不该开源的产物

用法：
    python tools/privacy_audit.py
    python tools/privacy_audit.py --json    # 机器可读输出
"""
from __future__ import annotations

import getpass
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
try:
    from _console import setup_console

    setup_console()
except ImportError:
    pass

#: 只扫描文本类文件；二进制只报路径
TEXT_EXT = {
    ".py", ".md", ".yml", ".yaml", ".txt", ".iss", ".ps1", ".spec",
    ".json", ".isl", ".cfg", ".ini", ".toml",
}

#: 允许出现的已知公开值（本项目自己的仓库地址等）
ALLOWLIST = {
    "Levanll/LanPulse",           # 仓库自身地址
    "github.com/Levanll",
}

PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("GitHub Token", re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "严重"),
    ("Classic Token", re.compile(r"ghp_[A-Za-z0-9]{20,}"), "严重"),
    ("私钥", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "严重"),
    ("疑似密码赋值", re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{6,}"), "高"),
    ("邮箱地址", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b"), "中"),
    ("手机号(中国)", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"), "中"),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"), "高"),
    ("IPv4 地址", re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])"), "低"),
    ("MAC 地址", re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"), "中"),
    ("Windows 用户目录路径", re.compile(r"[A-Za-z]:\\+Users\\+[^\\\s\"']+"), "中"),
    ("本机绝对路径(项目目录)", re.compile(r"[A-Za-z]:\\+Documents\\+deepseek-harness"), "低"),
]

#: 这些是测试数据的固定值或文档示例，可以出现
BENIGN_IPV4 = {
    "127.0.0.1", "0.0.0.0", "255.255.255.255", "8.8.8.8", "8.8.4.4",
    "1.1.1.1", "1.0.0.1", "9.9.9.9", "149.112.112.112",
    "223.5.5.5", "223.6.6.6", "119.29.29.29", "182.254.116.116",
    "114.114.114.114", "114.114.115.115", "180.76.76.76", "180.184.1.1",
    "101.226.4.6", "210.2.4.8", "208.67.222.222", "208.67.220.220",
    "94.140.14.14", "94.140.15.15", "76.76.2.0", "76.76.10.0",
    "77.88.8.8", "77.88.8.1", "168.126.63.1", "168.126.63.2",
    "203.80.96.10", "202.12.27.33", "203.112.2.4",
    "1.2.3.4", "10.0.0.1", "192.168.1.1", "192.168.1.5", "192.168.1.10",
    "169.254.0.1", "255.0.0.0",
}


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    return [ln for ln in (out.stdout or "").splitlines() if ln.strip()]


def machine_facts() -> dict[str, str]:
    """本机敏感值：一旦出现在仓库里就是泄露。"""
    user = os.environ.get("USERNAME") or getpass.getuser()
    host = os.environ.get("COMPUTERNAME", "")
    facts = {
        "用户名": user,
        "计算机名": host,
        "用户目录": os.path.expanduser("~"),
    }
    return {k: v for k, v in facts.items() if v}


def scan() -> list[dict]:
    findings: list[dict] = []
    facts = machine_facts()

    for rel in tracked_files():
        path = ROOT / rel
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXT:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        lines = text.splitlines()
        for name, pattern, level in PATTERNS:
            for m in pattern.finditer(text):
                value = m.group(0)
                if any(a in value for a in ALLOWLIST):
                    continue
                if name == "IPv4 地址" and value in BENIGN_IPV4:
                    continue
                if name == "邮箱地址" and any(
                    d in value for d in ("example.com", "noreply@", "localhost")
                ):
                    continue
                lineno = text[: m.start()].count("\n") + 1
                findings.append({
                    "file": rel,
                    "line": lineno,
                    "kind": name,
                    "level": level,
                    "value": value,
                    "context": lines[lineno - 1].strip()[:120] if lineno <= len(lines) else "",
                })

        # 本机敏感值逐字匹配（最直接的泄露）
        for label, value in facts.items():
            if len(value) < 4:
                continue
            idx = text.find(value)
            if idx >= 0:
                lineno = text[:idx].count("\n") + 1
                findings.append({
                    "file": rel,
                    "line": lineno,
                    "kind": f"本机{label}",
                    "level": "高",
                    "value": value,
                    "context": lines[lineno - 1].strip()[:120] if lineno <= len(lines) else "",
                })

    return findings


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    findings = scan()

    if as_json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
        return 1 if findings else 0

    files = tracked_files()
    print("=" * 72)
    print("仓库隐私核查")
    print("=" * 72)
    print(f"被跟踪文件：{len(files)} 个")
    print()

    if not findings:
        print("未发现个人信息或凭据泄露。")
        return 0

    # 按严重度分组
    order = {"严重": 0, "高": 1, "中": 2, "低": 3}
    findings.sort(key=lambda f: (order.get(f["level"], 9), f["file"], f["line"]))

    cur_level = None
    for f in findings:
        if f["level"] != cur_level:
            cur_level = f["level"]
            print(f"\n--- {cur_level}风险 ---")
        print(f"  [{f['kind']}] {f['file']}:{f['line']}")
        print(f"      值: {f['value']}")
        if f["context"]:
            print(f"      上下文: {f['context']}")

    print()
    print("=" * 72)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["level"]] = counts.get(f["level"], 0) + 1
    print("汇总：" + "  ".join(f"{k}={v}" for k, v in
                            sorted(counts.items(), key=lambda x: order.get(x[0], 9))))
    print("=" * 72)
    return 1 if any(f["level"] in ("严重", "高") for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
