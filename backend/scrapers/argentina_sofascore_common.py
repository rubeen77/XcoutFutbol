"""
Shared Sofascore helpers for Liga Profesional Argentina scrapers.

This module fetches and transforms external data only. Writes happen in the
dedicated loader script.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

try:
    from curl_cffi import requests
except ImportError:  # pragma: no cover
    requests = None

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from scrapers.common.logger import log_scraper_event
from scrapers.common.normalizers import normalize_name, safe_int


SCRAPER_NAME = "argentina_sofascore"
API_BASE = "https://api.sofascore.com/api/v1"
CFG = get_league("argentina")

TOURNAMENT_ID = CFG["sofascore_tournament_id"]
SEASON_ID = CFG["sofascore_season_id"]
DB_LIGA_ID = CFG["db_liga_id"]
DB_TEMPORADA = CFG["temporada"]
PRIMARY_STANDINGS_BLOCK = "Anual 2026"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}


def _get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API_BASE}/{endpoint.lstrip('/')}"
    if requests is not None:
        session = requests.Session(impersonate="chrome124")
        response = session.get(url, headers=HEADERS, params=params, timeout=25)
        response.raise_for_status()
        return response.json()

    if params:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode(params)}"
    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_seasons() -> dict[str, Any]:
    return _get(f"unique-tournament/{TOURNAMENT_ID}/seasons")


def parse_season_id(payload: dict[str, Any]) -> int | None:
    configured = safe_int(SEASON_ID)
    if configured is not None:
        return configured

    seasons = payload.get("seasons") or []
    for season in seasons:
        text = " ".join(str(season.get(key, "")) for key in ("name", "year"))
        if "2026" in text:
            return safe_int(season.get("id"))
    if seasons:
        return safe_int(seasons[0].get("id"))
    return None


def fetch_standings(season_id: int | None = None) -> dict[str, Any]:
    if season_id is None:
        season_id = parse_season_id(fetch_seasons())
    if season_id is None:
        raise RuntimeError("No Sofascore season_id found for Argentina")

    log_scraper_event(SCRAPER_NAME, "info", f"Fetching Argentina standings season_id={season_id}")
    return _get(f"unique-tournament/{TOURNAMENT_ID}/season/{season_id}/standings/total")


def parse_standings_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    standings = payload.get("standings") or []
    for block in standings:
        name = str(block.get("name") or "")
        if name == PRIMARY_STANDINGS_BLOCK:
            return block.get("rows") or []

    for block in standings:
        name = str(block.get("name") or "").lower()
        if "anual" in name:
            return block.get("rows") or []

    return (standings[0].get("rows") or []) if standings else []


def transform_team_from_row(row: dict[str, Any]) -> dict[str, Any]:
    team = row.get("team") or {}
    name = team.get("name") or team.get("shortName") or ""
    team_id = safe_int(team.get("id"))
    return {
        "liga_id": DB_LIGA_ID,
        "temporada": DB_TEMPORADA,
        "sofascore_team_id": team_id,
        "nombre": name,
        "nombre_normalizado": normalize_name(name),
        "slug": team.get("slug"),
        "nombre_corto": team.get("shortName"),
        "codigo": team.get("nameCode"),
        "pais": ((team.get("country") or {}).get("name")),
        "escudo_url": f"https://api.sofascore.app/api/v1/team/{team_id}/image" if team_id else None,
    }


def transform_standings_row(row: dict[str, Any]) -> dict[str, Any]:
    team = transform_team_from_row(row)
    scores_for = safe_int(row.get("scoresFor"))
    scores_against = safe_int(row.get("scoresAgainst"))
    return {
        "liga_id": DB_LIGA_ID,
        "temporada": DB_TEMPORADA,
        "sofascore_team_id": team["sofascore_team_id"],
        "equipo_nombre": team["nombre"],
        "equipo_nombre_normalizado": team["nombre_normalizado"],
        "posicion_clasificacion": safe_int(row.get("position")),
        "puntos": safe_int(row.get("points")),
        "partidos_jugados": safe_int(row.get("matches")),
        "victorias": safe_int(row.get("wins")),
        "empates": safe_int(row.get("draws")),
        "derrotas": safe_int(row.get("losses")),
        "goles_favor": scores_for,
        "goles_contra": scores_against,
        "diferencia_goles": (
            scores_for - scores_against
            if scores_for is not None and scores_against is not None
            else safe_int(row.get("scoreDiffFormatted"))
        ),
        "bloque_clasificacion": PRIMARY_STANDINGS_BLOCK,
    }
