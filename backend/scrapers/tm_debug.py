"""
Diagnóstico: prueba el endpoint ceapi de TM para el historial de valor.
Uso:
  python scrapers/tm_debug.py
"""
import re
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scrapers.transfermarkt_scraper import HEADERS
import requests

# Vedat Muriqi — ID 339041
TEST_ID  = "339041"
API_URL  = f"https://www.transfermarkt.es/ceapi/marketValueDevelopment/graph/{TEST_ID}"

def main():
    print(f"\nFetcheando ceapi: {API_URL}\n")
    try:
        r = requests.get(API_URL, headers=HEADERS, timeout=15)
        print(f"HTTP status: {r.status_code}")
        print(f"Content-Type: {r.headers.get('Content-Type','')}")
        print(f"\nRespuesta completa:\n")
        try:
            data = r.json()
            print(json.dumps(data, indent=2, ensure_ascii=False)[:3000])
        except Exception:
            print(r.text[:2000])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
