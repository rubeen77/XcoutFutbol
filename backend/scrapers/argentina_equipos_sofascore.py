"""Liga Profesional Argentina teams scraper from Sofascore."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.argentina_sofascore_common import (
    fetch_seasons,
    fetch_standings,
    parse_season_id,
    parse_standings_rows,
    transform_team_from_row,
)
from scrapers.common.logger import log_scraper_event


SCRAPER_NAME = "argentina_equipos_sofascore"
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")


def fetch() -> dict:
    seasons_payload = fetch_seasons()
    season_id = parse_season_id(seasons_payload)
    standings_payload = fetch_standings(season_id)
    return {"season_id": season_id, "seasons": seasons_payload, "standings": standings_payload}


def parse(raw: dict) -> list[dict]:
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
    return [transform_team_from_row(row) for row in rows]


def run() -> dict:
    raw = fetch()
    rows = parse(raw)
    data = transform(rows)
    log_scraper_event(SCRAPER_NAME, "info", f"Teams transformed: {len(data)}")
    return {"season_id": raw["season_id"], "total": len(data), "equipos": data}


if __name__ == "__main__":
    result = run()
    for row in result["equipos"]:
        print(row)
