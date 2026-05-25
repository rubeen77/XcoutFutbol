"""
LaLiga Hypermotion classification scraper from Sofascore.

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
    transform_standings_row,
)


SCRAPER_NAME = "hypermotion_clasificacion_sofascore"
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")


def fetch() -> dict:
    """Fetch raw Sofascore standings data."""
    seasons_payload = fetch_seasons()
    season_id = parse_season_id(seasons_payload)
    standings_payload = fetch_standings(season_id)
    return {
        "season_id": season_id,
        "seasons": seasons_payload,
        "standings": standings_payload,
    }


def parse(raw: dict) -> list[dict]:
    """Parse raw Sofascore payload into standings rows."""
    return parse_standings_rows(raw["standings"])


def transform(rows: list[dict]) -> list[dict]:
    """Transform standings rows into DB-ready classification dictionaries."""
    return [transform_standings_row(row) for row in rows]


def run() -> dict:
    """Dry-run classification pipeline."""
    raw = fetch()
    rows = parse(raw)
    data = transform(rows)
    log_scraper_event(SCRAPER_NAME, "info", f"Classification rows transformed: {len(data)}")
    return {
        "season_id": raw["season_id"],
        "total": len(data),
        "clasificacion": data,
    }


if __name__ == "__main__":
    result = run()
    for row in result["clasificacion"]:
        print(row)
