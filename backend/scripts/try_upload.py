import io

import requests
from PIL import Image

BASE = "http://127.0.0.1:8000/api"

login = requests.post(
    f"{BASE}/auth/login/", json={"username": "demo", "password": "Str0ng-Passw0rd!x"}, timeout=10
)
login.raise_for_status()
headers = {"Authorization": f"Bearer {login.json()['access']}"}

buf = io.BytesIO()
Image.new("RGB", (400, 300), (40, 160, 70)).save(buf, "JPEG")
good = buf.getvalue()

r = requests.post(
    f"{BASE}/scans/", headers=headers,
    files={"image": ("fake.jpg", b"this is not an image" * 20, "image/jpeg")}, timeout=30,
)
print("fake image:", r.status_code, r.json())

for i in range(1, 12):
    r = requests.post(
        f"{BASE}/scans/", headers=headers,
        files={"image": ("leaf.jpg", good, "image/jpeg")}, data={"crop_hint": "Tomato"}, timeout=30,
    )
    print(f"valid upload {i}: {r.status_code} {r.json()} Retry-After={r.headers.get('Retry-After')}")