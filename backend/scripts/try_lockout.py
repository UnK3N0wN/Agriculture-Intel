import sys

import requests

BASE = "http://127.0.0.1:8000/api"
USER = sys.argv[1] if len(sys.argv) > 1 else "demo"

for attempt in range(1, 7):
    r = requests.post(f"{BASE}/auth/login/", json={"username": USER, "password": "definitely-wrong"}, timeout=10)
    print(f"wrong attempt {attempt}: {r.status_code} {r.json()} Retry-After={r.headers.get('Retry-After')}")

r = requests.post(f"{BASE}/auth/login/", json={"username": USER, "password": "Str0ng-Passw0rd!x"}, timeout=10)
print(f"correct password while locked: {r.status_code} {r.json()}")