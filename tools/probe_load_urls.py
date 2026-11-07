r"""探测可用于缓冲膨胀测试的下载源（一次性调研脚本）。

缓冲膨胀测试必须真实产生下载流量，否则测出的"A 级"是假结论——
没有负载就测不出队列积压。本脚本逐个验证候选 URL 是否真能持续下载。
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request

CANDIDATES = [
    # 国内云厂商镜像（大文件，稳定）
    "https://mirrors.aliyun.com/ubuntu-releases/24.04/ubuntu-24.04.1-desktop-amd64.iso",
    "https://mirrors.tuna.tsinghua.edu.cn/ubuntu-releases/24.04/ubuntu-24.04.1-desktop-amd64.iso",
    "https://mirrors.ustc.edu.cn/ubuntu-releases/24.04/ubuntu-24.04.1-desktop-amd64.iso",
    "https://mirror.nju.edu.cn/ubuntu-releases/24.04/ubuntu-24.04.1-desktop-amd64.iso",
    # 电信/联通测速文件
    "http://speed.cloudflare.com/__down?bytes=10000000",
    "https://speed.cloudflare.com/__down?bytes=10000000",
    # 微信安装包 CDN（参考项目也用这个）
    "https://dldir1.qq.com/weixin/Windows/WeChatSetup.exe",
    # 阿里云 OSS 公开测试对象
    "https://mirrors.aliyun.com/deepin/releases/23/deepin-desktop-community-23-amd64.iso",
]

MAX_SECONDS = 4.0
CHUNK = 65536


def probe(url: str) -> tuple[bool, int, float, str]:
    """返回 (可用, 读取字节数, 耗时秒, 说明)。"""
    start = time.perf_counter()
    read = 0
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "LanPulse/1.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            while time.perf_counter() - start < MAX_SECONDS:
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                read += len(chunk)
                if read >= 3 * 1024 * 1024:
                    break
        elapsed = time.perf_counter() - start
        ok = read >= 512 * 1024        # 至少读到 512KB 才算"真能跑负载"
        return ok, read, elapsed, ""
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return False, read, time.perf_counter() - start, f"{type(exc).__name__}: {str(exc)[:70]}"


def main() -> int:
    print("探测缓冲膨胀测试的可用下载源：\n")
    good: list[tuple[str, float]] = []
    for url in CANDIDATES:
        ok, read, secs, err = probe(url)
        mb = read / 1024 / 1024
        speed = mb / secs if secs > 0 else 0
        mark = "OK  " if ok else "FAIL"
        print(f"[{mark}] {url[:72]}")
        if ok:
            print(f"       {mb:.2f} MB / {secs:.1f}s = {speed:.1f} MB/s")
            good.append((url, speed))
        else:
            print(f"       {mb:.2f} MB，{err}")

    print()
    if good:
        good.sort(key=lambda x: -x[1])
        print("推荐（按速度排序）：")
        for url, speed in good:
            print(f"  {speed:5.1f} MB/s  {url}")
        print("\n建议把最快的两个写进 LOAD_URLS，并保留一个 http:// 作为回退")
    else:
        print("没有可用的负载源。缓冲膨胀测试应改为 SKIP，而不是给出虚假的 A 级。")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
