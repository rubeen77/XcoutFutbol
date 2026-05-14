"""
Diagnóstico: qué devuelve Sofascore para J29/J33/J34 de Ligue 1 25/26
"""
import sys, time
sys.path.insert(0, '.')
from curl_cffi import requests as cffi_requests

TOURNAMENT_ID = 34
SEASON_ID     = 77356  # Ligue 1 25/26

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
}
API = "https://api.sofascore.com/api/v1"
_session = cffi_requests.Session(impersonate="chrome120")

def fetch_round(j):
    url = f"{API}/unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/events/round/{j}"
    r = _session.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return []
    return r.json().get("events", [])

# Parejas de equipos que buscamos (nombres DB normalizados aproximados)
TARGET_PAIRS = [
    ("brest", "strasbourg"),
    ("lens",  "paris saint"),
]

print("=== DIAGNÓSTICO SOFASCORE LIGUE 1 25/26 ===\n")

for jornada in [29, 30, 31, 32, 33, 34]:
    events = fetch_round(jornada)
    finished = [e for e in events if e.get("status", {}).get("type") == "finished"]
    not_fin  = [e for e in events if e.get("status", {}).get("type") != "finished"]

    print(f"J{jornada}: {len(events)} eventos ({len(finished)} finished, {len(not_fin)} otros)")

    for ev in events:
        home = ev.get("homeTeam", {}).get("name", "?")
        away = ev.get("awayTeam", {}).get("name", "?")
        status = ev.get("status", {}).get("type", "?")
        hs = ev.get("homeScore", {})
        as_ = ev.get("awayScore", {})
        gl = hs.get("normaltime", hs.get("current"))
        gv = as_.get("normaltime", as_.get("current"))
        round_n = ev.get("roundInfo", {}).get("round")

        # Siempre mostrar los partidos que nos interesan
        low_home = home.lower()
        low_away = away.lower()
        es_target = any(
            (a in low_home and b in low_away) or (b in low_home and a in low_away)
            for a, b in TARGET_PAIRS
        )
        if es_target or jornada in (33, 34):
            print(f"  [{status:12}] round={round_n}  {home} {gl}-{gv} {away}")

    time.sleep(0.8)

print("\nDONE")
