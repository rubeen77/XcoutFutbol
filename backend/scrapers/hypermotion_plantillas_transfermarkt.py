"""
LaLiga Hypermotion squad scraper from Transfermarkt ES2.

Phase 1 only: fetch, parse and transform. No Supabase writes.
"""

import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

import cloudscraper
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from scrapers.common.logger import log_scraper_event
from scrapers.common.normalizers import normalize_name, parse_market_value


SCRAPER_NAME = "hypermotion_plantillas_transfermarkt"
TM_BASE = "https://www.transfermarkt.es"
LIGA_ID = 33
TM_SEASON = 2025
TM_LIGA_CODE = "ES2"
REQUEST_DELAY = 1.5
CFG = get_league("hypermotion")

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


def _get(url: str) -> BeautifulSoup:
    response = _scraper.get(url, timeout=25)
    if response.status_code != 200:
        raise RuntimeError(f"Transfermarkt HTTP {response.status_code}: {url}")
    return BeautifulSoup(response.content, "lxml")


def get_team_ids() -> list[dict[str, Any]]:
    """Get team ids and squad URLs from the Transfermarkt league page."""
    url = f"{TM_BASE}/laliga2/startseite/wettbewerb/{TM_LIGA_CODE}/saison_id/{TM_SEASON}"
    log_scraper_event(SCRAPER_NAME, "info", f"Fetching teams: {url}")
    soup = _get(url)

    teams = []
    seen = set()
    for a in soup.select("td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m = re.search(r"(/[^/]+/startseite/verein/(\d+))", href)
        if not m:
            continue

        slug_path = m.group(1)
        team_id = m.group(2)
        name = a.text.strip()

        if team_id in seen:
            continue
        seen.add(team_id)

        teams.append({
            "name": name,
            "tm_id": team_id,
            "nombre_normalizado": normalize_name(name),
            "kader_url": f"{TM_BASE}{slug_path.replace('/startseite/', '/kader/')}/saison_id/{TM_SEASON}",
        })

    log_scraper_event(SCRAPER_NAME, "info", f"Equipos encontrados: {len(teams)}")
    for team in teams:
        log_scraper_event(SCRAPER_NAME, "info", f"  ID={team['tm_id']} {team['name']}")
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
    m = re.search(r"/spieler/(\d+)", player_url)
    return m.group(1) if m else None


def _extract_position(row) -> str | None:
    inline_table = row.select_one("table.inline-table")
    if not inline_table:
        return None
    lines = [
        text.strip()
        for text in inline_table.get_text("\n", strip=True).splitlines()
        if text.strip()
    ]
    return lines[-1] if len(lines) > 1 else None


def _extract_age(row) -> int | None:
    text = row.get_text(" ", strip=True)
    m = re.search(r"\((\d{2})\)", text)
    return int(m.group(1)) if m else None


def _extract_nationality(row) -> str | None:
    flag = row.select_one("img.flaggenrahmen")
    return (flag.get("title") or flag.get("alt")) if flag else None


def scrape_squad(team: dict[str, Any]) -> list[dict[str, Any]]:
    """Scrape one team squad using the same pattern as existing TM scrapers."""
    soup = _get(team["kader_url"])
    players = []
    for row in soup.select("table.items tbody tr.odd, table.items tbody tr.even"):
        name_el = row.select_one("td.hauptlink a")
        img_el = row.select_one("img.bilderrahmen-fixed")
        val_el = row.select_one("td.rechts.hauptlink")

        if not name_el:
            continue

        name = name_el.text.strip()

        foto = None
        if img_el:
            foto = img_el.get("data-src") or img_el.get("src")
            if foto:
                foto = foto.replace("/medium/", "/big/")

        player_url = _extract_player_url(row)

        players.append({
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
            "valor_mercado": parse_market_value(val_el.text if val_el else ""),
            "player_url": player_url,
        })

    return players


def scrape_all_squads(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Scrape all team squads."""
    log_scraper_event(SCRAPER_NAME, "info", f"Procesando plantillas: {len(teams)} equipos")
    all_players = []
    for idx, team in enumerate(teams, start=1):
        log_scraper_event(SCRAPER_NAME, "info", f"  [{idx}/{len(teams)}] {team['name']}")
        players = scrape_squad(team)
        log_scraper_event(SCRAPER_NAME, "info", f"       Jugadores encontrados: {len(players)}")
        all_players.extend(players)
        if idx < len(teams):
            time.sleep(REQUEST_DELAY)

    log_scraper_event(SCRAPER_NAME, "info", f"Jugadores encontrados total: {len(all_players)}")
    return all_players


def fetch() -> dict[str, Any]:
    """Fetch Transfermarkt teams and squads."""
    teams = get_team_ids()
    players = scrape_all_squads(teams)
    return {"teams": teams, "players": players}


def parse(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep a fetch/parse/transform shape for the new pipeline."""
    return raw


def transform(parsed: dict[str, Any]) -> dict[str, Any]:
    """Transform parsed Transfermarkt records into DB-ready dictionaries."""
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

    return {
        "equipos": teams,
        "jugadores": players,
    }


def run() -> dict[str, Any]:
    """Dry-run Transfermarkt squad pipeline."""
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
    print({
        "equipos": len(result["equipos"]),
        "jugadores": len(result["jugadores"]),
        "primeros_equipos": result["equipos"][:5],
        "primeros_jugadores": result["jugadores"][:5],
    })
