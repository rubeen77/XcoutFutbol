"""
LaLiga Hypermotion teams scraper from Sofascore.

Phase 1 only: fetch, parse and transform. No Supabase writes.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.common.logger import log_scraper_event
from scrapers.hypermotion_sofascore_common import (
    parse_season_id,
    parse_standings_rows,
    fetch_seasons,
    fetch_standings,
    transform_team_from_row,
)


SCRAPER_NAME = "hypermotion_equipos_sofascore"
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")


def fetch() -> dict:
    """Fetch raw Sofascore standings data, used as source of teams."""
    seasons_payload = fetch_seasons()
    season_id = parse_season_id(seasons_payload)
    standings_payload = fetch_standings(season_id)
    return {
        "season_id": season_id,
        "seasons": seasons_payload,
        "standings": standings_payload,
    }


def parse(raw: dict) -> list[dict]:
    """Parse unique team rows from standings."""
    rows = parse_standings_rows(raw["standings"])
    seen = set()
    unique_rows = []
    for row in rows:
        team_id = ((row.get("team") or {}).get("id"))
        if team_id in seen:
            continue
        seen.add(team_id)
        unique_rows.append(row)
    return unique_rows


def transform(rows: list[dict]) -> list[dict]:
    """Transform team rows into DB-ready team dictionaries."""
    return [transform_team_from_row(row) for row in rows]


def run() -> dict:
    """Dry-run teams pipeline."""
    raw = fetch()
    rows = parse(raw)
    data = transform(rows)
    log_scraper_event(SCRAPER_NAME, "info", f"Teams transformed: {len(data)}")
    return {
        "season_id": raw["season_id"],
        "total": len(data),
        "equipos": data,
    }


if __name__ == "__main__":
    result = run()
    for row in result["equipos"]:
        print(row)
