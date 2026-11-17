import io
import json
import random
import sys
import time

import requests
from PIL import Image

BASE = "http://127.0.0.1:8000/api"
hint = sys.argv[1] if len(sys.argv) > 1 else "Tomato"  # try: mock-fail, mock-bad, mock-reject

login = requests.post(f"{BASE}/auth/login/", json={"username": "demo", "password": "Str0ng-Passw0rd!x"}, timeout=10)
login.raise_for_status()
headers = {"Authorization": f"Bearer {login.json()['access']}"}

# A random colour gives every run a different image, so the duplicate check doesn't reuse an old job.
buf = io.BytesIO()
Image.new("RGB", (400, 300), tuple(random.randint(0, 255) for _ in range(3))).save(buf, "JPEG")

r = requests.post(
    f"{BASE}/scans/", headers=headers,
    files={"image": ("leaf.jpg", buf.getvalue(), "image/jpeg")}, data={"crop_hint": hint}, timeout=30,
)
print("submit:", r.status_code, r.json())
task_id = r.json()["task_id"]

for _ in range(60):
    time.sleep(3)
    s = requests.get(f"{BASE}/scans/status/{task_id}/", headers=headers, timeout=10).json()
    print("status:", s["status"], "| attempts:", s["attempts"])
    if s["status"] in ("succeeded", "failed"):
        print(json.dumps(s, indent=2))
        break