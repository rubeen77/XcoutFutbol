"""
Shared Sofascore fetch/parse helpers for LaLiga Hypermotion dry-run scrapers.

This module only fetches and transforms external data. It does not write to
Supabase.
"""

import sys
import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

try:
    from curl_cffi import requests
except ImportError:  # pragma: no cover - fallback for local environments
    requests = None

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from scrapers.common.logger import log_scraper_event
from scrapers.common.normalizers import normalize_name, safe_int


SCRAPER_NAME = "hypermotion_sofascore"
API_BASE = "https://api.sofascore.com/api/v1"
CFG = get_league("hypermotion")

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


def _get(endpoint: str) -> dict[str, Any]:
    """Fetch a Sofascore JSON endpoint."""
    url = f"{API_BASE}/{endpoint.lstrip('/')}"
    if requests is not None:
        session_kwargs = {"impersonate": "chrome124"} if "curl_cffi" in str(requests) else {}
        session = requests.Session(**session_kwargs)
        response = session.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.json()

    request = Request(url, headers=HEADERS)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_seasons() -> dict[str, Any]:
    """Fetch available Sofascore seasons for Hypermotion."""
    tournament_id = CFG["sofascore_tournament_id"]
    return _get(f"unique-tournament/{tournament_id}/seasons")


def parse_season_id(payload: dict[str, Any]) -> int | None:
    """Find the current season id from Sofascore's seasons response."""
    configured = CFG.get("sofascore_season_id")
    if configured:
        return safe_int(configured)

    seasons = payload.get("seasons") or []
    for season in seasons:
        year = str(season.get("year") or "")
        if ("2025" in year and "2026" in year) or year in {"25/26", "2025/26"}:
            return safe_int(season.get("id"))

    if seasons:
        return safe_int(seasons[0].get("id"))
    return None


def fetch_standings(season_id: int | None = None) -> dict[str, Any]:
    """Fetch total standings for Hypermotion."""
    if season_id is None:
        season_id = parse_season_id(fetch_seasons())
    if season_id is None:
        raise RuntimeError("No Sofascore season_id found for Hypermotion.")

    tournament_id = CFG["sofascore_tournament_id"]
    endpoint = f"unique-tournament/{tournament_id}/season/{season_id}/standings/total"
    log_scraper_event(SCRAPER_NAME, "info", f"Fetching standings season_id={season_id}")
    return _get(endpoint)


def parse_standings_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract standings rows from Sofascore payload."""
    standings = payload.get("standings") or []
    if not standings:
        return []
    return standings[0].get("rows") or []


def transform_team_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Transform a Sofascore standings row into a team-shaped record."""
    team = row.get("team") or {}
    name = team.get("name") or team.get("shortName") or ""
    team_id = safe_int(team.get("id"))
    return {
        "liga_id": CFG["db_liga_id"],
        "temporada": CFG["temporada"],
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
    """Transform a Sofascore standings row into classification data."""
    team = transform_team_from_row(row)
    scores_for = safe_int(row.get("scoresFor"))
    scores_against = safe_int(row.get("scoresAgainst"))
    return {
        "liga_id": CFG["db_liga_id"],
        "temporada": CFG["temporada"],
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
    }
