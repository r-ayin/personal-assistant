#!/usr/bin/env python3
"""auto-ci-flash.py — 自动 CI 监测 + 下载 + 烧录流水线。

每 15 分钟检查 github 是否有新 commit，有则自动触发 CI 并烧录。
不需要 Claude 介入，也不需要你说"检查 CI"。
"""
import subprocess, time, json, urllib.request, os, sys

REPO = "r-ayin/personal-assistant"
TOKEN = os.environ.get("GH_TOKEN", os.environ.get("GITHUB_TOKEN", ""))
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json", "User-Agent": "auto-ci"}
LAST_CHECK_FILE = os.path.expanduser("~/.last_ci_sha")
CHECK_INTERVAL = 900  # 15 分钟

def api(path):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get_latest_sha():
    ref = api("git/ref/heads/main")
    return ref['object']['sha']

def trigger_ci():
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/build-dual-mode-firmware.yml/dispatches"
    data = json.dumps({"ref": "main", "inputs": {"pc_ip": "192.168.31.233", "pc_port": "8004"}}).encode()
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    urllib.request.urlopen(req)

def download_and_flash(run_id):
    # Download
    subprocess.run(["gh", "run", "download", str(run_id), "--repo", REPO,
                    "--dir", f"/e/x-tool/personal-assistant/xiaozhi-dual-mode-firmware-auto"],
                   capture_output=True)
    # Flash
    subprocess.run(["python", "-m", "esptool", "--chip", "esp32s3", "--port", "COM4",
                    "write-flash", "0x20000",
                    "/e/x-tool/personal-assistant/xiaozhi-dual-mode-firmware-auto/xiaozhi-dual-mode-firmware/xiaozhi.bin"],
                   capture_output=True)
    print(f"[auto-ci] Flashed run {run_id}")

def main():
    last_sha = ""
    if os.path.exists(LAST_CHECK_FILE):
        with open(LAST_CHECK_FILE) as f:
            last_sha = f.read().strip()

    try:
        current_sha = get_latest_sha()
    except Exception as e:
        print(f"[auto-ci] API error: {e}")
        return

    if current_sha == last_sha:
        return  # 无新代码

    print(f"[auto-ci] New commit: {current_sha[:10]} (was {last_sha[:10] if last_sha else 'none'})")

    # Check if there's a running CI
    runs = api("actions/workflows/build-dual-mode-firmware.yml/runs?per_page=3")
    for run in runs.get("workflow_runs", []):
        if run["head_sha"] == current_sha and run["status"] == "completed" and run["conclusion"] == "success":
            # 已有成功构建，直接下载
            run_id = run["id"]
            print(f"[auto-ci] Found existing success run #{run_id}")
            download_and_flash(run_id)
            with open(LAST_CHECK_FILE, "w") as f:
                f.write(current_sha)
            return

    # 无已完成构建，触发 CI
    try:
        trigger_ci()
        print(f"[auto-ci] Triggered CI for {current_sha[:10]}")
    except Exception as e:
        print(f"[auto-ci] Trigger failed: {e}")
        return

    # 等构建完成
    for _ in range(36):  # 最多等 3 小时
        time.sleep(300)
        runs = api("actions/workflows/build-dual-mode-firmware.yml/runs?per_page=3")
        for run in runs.get("workflow_runs", []):
            if run["head_sha"] == current_sha and run["status"] == "completed":
                if run["conclusion"] == "success":
                    download_and_flash(run["id"])
                else:
                    print(f"[auto-ci] Run failed: {run['conclusion']}")
                with open(LAST_CHECK_FILE, "w") as f:
                    f.write(current_sha)
                return
        print(f"[auto-ci] Waiting... {_+1}/36")

    print("[auto-ci] Timeout waiting for CI")

if __name__ == "__main__":
    main()
