import socket
import subprocess
import time
import os

def is_port_open(host="localhost", port=9222) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0

def initBrowser(checkPortOpenNum: int) -> bool:
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    args = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.path.expanduser('~/chrome-playwright-profile')}"
    ]
    subprocess.Popen(args)
    for _ in range(checkPortOpenNum):
        if is_port_open():
            return True
        time.sleep(0.5)
    return False