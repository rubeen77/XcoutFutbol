"""Quick: find Premier League season ID on Sofascore for 2025/26."""
from curl_cffi import requests

SESSION = requests.Session(impersonate="chrome124")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}

r = SESSION.get(
    "https://api.sofascore.com/api/v1/unique-tournament/17/seasons",
    headers=HEADERS,
    timeout=15,
)
print("Status:", r.status_code)
data = r.json()
for s in data.get("seasons", []):
    print(f"  id={s['id']:8d}  year={s.get('year','?'):10s}  name={s.get('name','?')}")
