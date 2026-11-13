import pathlib, subprocess
root = pathlib.Path(r"D:\Documents\deepseek-harness\default-workspace\lanpulse")
tok = (root/".gh_token").read_text(encoding="ascii", errors="replace").strip()
url = "https://x-access-token:" + tok + "@github.com/Levanll/LanPulse.git"
c = subprocess.run(["git","add","-A"], cwd=root, capture_output=True, text=True)
c = subprocess.run(["git","commit","-m","docs: HANDOFF 更新到 v1.3.0"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
print("commit:", (c.stdout or "").strip()[:100])
try:
    r = subprocess.run(["git","push",url,"main"], cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("push rc:", r.returncode)
    print(((r.stdout or "")+(r.stderr or "")).replace(tok,"<TOKEN>")[:400])
finally:
    subprocess.run(["git","remote","set-url","origin","https://github.com/Levanll/LanPulse.git"], cwd=root)
    print("remote restored")