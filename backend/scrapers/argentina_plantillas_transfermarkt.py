"""Liga Profesional Argentina squad scraper from Transfermarkt ARG1."""

from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from scrapers.common.logger import log_scraper_event
from scrapers.common.normalizers import normalize_name, parse_market_value


SCRAPER_NAME = "argentina_plantillas_transfermarkt"
TM_BASE = "https://www.transfermarkt.es"
TM_PATH = "primera-division"
TM_SEASON = 2025
CFG = get_league("argentina")
TM_LIGA_CODE = CFG["transfermarkt_code"]
REQUEST_DELAY = 1.2

SESSION = requests.Session(impersonate="chrome124")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")


def _get(url: str) -> BeautifulSoup:
    last_error = None
    for attempt in range(1, 4):
        try:
            response = SESSION.get(url, headers=HEADERS, timeout=25)
            response.raise_for_status()
            return BeautifulSoup(response.content, "lxml")
        except Exception as exc:
            last_error = exc
            log_scraper_event(SCRAPER_NAME, "warning", f"Transfermarkt attempt {attempt}/3 failed: {exc}")
            if attempt < 3:
                time.sleep(3 * attempt)
    raise RuntimeError(f"Transfermarkt fetch failed after retries: {url} ({last_error})")


def _team_url_from_href(href: str, page: str) -> str | None:
    match = re.search(r"^(/[^/]+)/(?:startseite|kader)/verein/(\d+)", href or "")
    if not match:
        return None
    slug, team_id = match.groups()
    return f"{TM_BASE}{slug}/{page}/verein/{team_id}/saison_id/{TM_SEASON}"


def get_team_ids() -> list[dict[str, Any]]:
    url = f"{TM_BASE}/{TM_PATH}/startseite/wettbewerb/{TM_LIGA_CODE}/saison_id/{TM_SEASON}"
    log_scraper_event(SCRAPER_NAME, "info", f"Fetching teams: {url}")
    soup = _get(url)

    teams = []
    seen = set()
    for a in soup.select("td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        match = re.search(r"/verein/(\d+)", href)
        if not match:
            continue

        team_id = match.group(1)
        name = a.get_text(strip=True)
        if not name or team_id in seen:
            continue
        seen.add(team_id)

        teams.append(
            {
                "name": name,
                "tm_id": team_id,
                "nombre_normalizado": normalize_name(name),
                "kader_url": _team_url_from_href(href, "kader"),
            }
        )

    log_scraper_event(SCRAPER_NAME, "info", f"Equipos encontrados: {len(teams)}")
    return teams


def _extract_player_url(row) -> str | None:
    for a in row.select("td.hauptlink a"):
        href = a.get("href", "")
        if "/spieler/" in href:
            return TM_BASE + href
    return None


def _extract_player_id(player_url: str | None) -> str | None:
    if not player_url:
        return None
    match = re.search(r"/spieler/(\d+)", player_url)
    return match.group(1) if match else None


def _extract_position(row) -> str | None:
    inline_table = row.select_one("table.inline-table")
    if not inline_table:
        return None
    lines = [text.strip() for text in inline_table.get_text("\n", strip=True).splitlines() if text.strip()]
    return lines[-1] if len(lines) > 1 else None


def _extract_age(row) -> int | None:
    text = row.get_text(" ", strip=True)
    match = re.search(r"\((\d{2})\)", text)
    return int(match.group(1)) if match else None


def _extract_nationality(row) -> str | None:
    flag = row.select_one("img.flaggenrahmen")
    return (flag.get("title") or flag.get("alt")) if flag else None


def scrape_squad(team: dict[str, Any]) -> list[dict[str, Any]]:
    soup = _get(team["kader_url"])
    players = []
    for row in soup.select("table.items tbody tr.odd, table.items tbody tr.even"):
        name_el = row.select_one("td.hauptlink a")
        img_el = row.select_one("img.bilderrahmen-fixed")
        val_el = row.select_one("td.rechts.hauptlink")
        if not name_el:
            continue

        name = name_el.get_text(strip=True)
        foto = None
        if img_el:
            foto = img_el.get("data-src") or img_el.get("src")
            if foto:
                foto = foto.replace("/medium/", "/big/")

        player_url = _extract_player_url(row)
        players.append(
            {
                "tm_player_id": _extract_player_id(player_url),
                "tm_team_id": team["tm_id"],
                "equipo_nombre": team["name"],
                "equipo_nombre_normalizado": team["nombre_normalizado"],
                "nombre": name,
                "nombre_normalizado": normalize_name(name),
                "posicion": _extract_position(row),
                "edad": _extract_age(row),
                "nacionalidad": _extract_nationality(row),
                "foto_url": foto,
                "valor_mercado": parse_market_value(val_el.get_text(strip=True) if val_el else ""),
                "player_url": player_url,
            }
        )
    return players


def scrape_all_squads(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    log_scraper_event(SCRAPER_NAME, "info", f"Procesando plantillas: {len(teams)} equipos")
    all_players = []
    for index, team in enumerate(teams, 1):
        log_scraper_event(SCRAPER_NAME, "info", f"  [{index}/{len(teams)}] {team['name']}")
        players = scrape_squad(team)
        log_scraper_event(SCRAPER_NAME, "info", f"       Jugadores encontrados: {len(players)}")
        all_players.extend(players)
        if index < len(teams):
            time.sleep(REQUEST_DELAY)
    log_scraper_event(SCRAPER_NAME, "info", f"Jugadores encontrados total: {len(all_players)}")
    return all_players


def fetch() -> dict[str, Any]:
    teams = get_team_ids()
    players = scrape_all_squads(teams)
    return {"teams": teams, "players": players}


def parse(raw: dict[str, Any]) -> dict[str, Any]:
    return raw


def transform(parsed: dict[str, Any]) -> dict[str, Any]:
    teams = [
        {
            "liga_id": CFG["db_liga_id"],
            "temporada": CFG["temporada"],
            "tm_team_id": team["tm_id"],
            "nombre": team["name"],
            "nombre_normalizado": team["nombre_normalizado"],
        }
        for team in parsed["teams"]
    ]
    players = [
        {
            "liga_id": CFG["db_liga_id"],
            "temporada": CFG["temporada"],
            **player,
        }
        for player in parsed["players"]
    ]
    return {"equipos": teams, "jugadores": players}


def run() -> dict[str, Any]:
    raw = fetch()
    parsed = parse(raw)
    data = transform(parsed)
    log_scraper_event(
        SCRAPER_NAME,
        "info",
        f"Teams transformed: {len(data['equipos'])}; players transformed: {len(data['jugadores'])}",
    )
    return data


if __name__ == "__main__":
    result = run()
    print(
        {
            "equipos": len(result["equipos"]),
            "jugadores": len(result["jugadores"]),
            "primeros_equipos": result["equipos"][:5],
            "primeros_jugadores": result["jugadores"][:5],
        }
    )
