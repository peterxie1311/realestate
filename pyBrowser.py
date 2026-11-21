import os
import shutil
import socket
import subprocess
import sys
import time


def is_port_open(host="localhost", port=9222) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


def initBrowser(checkPortOpenNum: int) -> bool:
    if is_port_open():
        return True

    configured = os.environ.get("CHROME_PATH")
    candidates = [configured] if configured else []
    if sys.platform == "darwin":
        candidates.append("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    candidates += ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]
    chrome_path = next(
        (path for path in candidates if path and (shutil.which(path) or os.path.isfile(path))),
        None,
    )
    if not chrome_path:
        raise RuntimeError(
            "Chrome/Chromium not found. Install Chromium or set CHROME_PATH."
        )
    args = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.path.expanduser('~/chrome-playwright-profile')}",
    ]
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        args.append("--headless=new")
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(max(checkPortOpenNum, 20)):
        if is_port_open():
            return True
        time.sleep(0.5)
    return False
