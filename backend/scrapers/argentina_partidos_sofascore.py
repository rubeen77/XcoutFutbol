"""Liga Profesional Argentina matches scraper from Sofascore."""

from __future__ import annotations

import argparse
import difflib
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from database.supabase_client import supabase
from scrapers.common.loaders import upsert_partido
from scrapers.common.logger import log_scraper_event
from scrapers.common.normalizers import normalize_name, safe_int


SCRAPER_NAME = "argentina_partidos_sofascore"
CFG = get_league("argentina")

TOURNAMENT_ID = CFG["sofascore_tournament_id"]
SEASON_ID = CFG["sofascore_season_id"]
DB_LIGA_ID = CFG["db_liga_id"]
DB_TEMPORADA = CFG["temporada"]
MAX_ROUND = 40
REQUEST_DELAY = 0.5
BATCH_SIZE = 100

API = "https://api.sofascore.com/api/v1"
SESSION = requests.Session(impersonate="chrome124")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

ESTADO_MAP = {
    "notstarted": "programado",
    "inprogress": "en_directo",
    "finished": "finalizado",
    "postponed": "aplazado",
    "canceled": "aplazado",
    "cancelled": "aplazado",
    "interrupted": "aplazado",
}

STRIP_TOKENS = {"aa", "ac", "ca", "cas", "club", "atletico", "cs", "csd", "fc"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(SCRAPER_NAME)


def _get(endpoint: str) -> dict[str, Any]:
    url = f"{API}/{endpoint.lstrip('/')}"
    response = SESSION.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.json()


def _ts_to_iso(timestamp: Any) -> str | None:
    ts = safe_int(timestamp)
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _strip_tokens(name_norm: str) -> str:
    return " ".join(part for part in name_norm.split() if part not in STRIP_TOKENS)


def _team_key(value: Any) -> str:
    cleaned = str(value or "").replace("(", " ").replace(")", " ").replace(".", " ")
    return normalize_name(cleaned)


def _team_aliases() -> dict[str, str]:
    aliases = {
        _team_key(source): _team_key(target)
        for source, target in (CFG.get("aliases_equipos") or {}).items()
    }
    aliases.update({target: target for target in aliases.values()})
    return aliases


TEAM_ALIASES = _team_aliases()
_EQUIPO_CACHE: dict[str, int] = {}
_EQUIPO_KEYS: list[str] = []
_EQUIPO_STRIPPED: dict[str, int] = {}


def load_equipo_cache() -> None:
    global _EQUIPO_CACHE, _EQUIPO_KEYS, _EQUIPO_STRIPPED
    if _EQUIPO_CACHE:
        return

    res = (
        supabase.table("equipos")
        .select("id,nombre")
        .eq("liga_id", DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .execute()
    )
    for equipo in res.data or []:
        key = _team_key(equipo.get("nombre"))
        equipo_id = safe_int(equipo.get("id"))
        if key and equipo_id is not None:
            _EQUIPO_CACHE[key] = equipo_id
            stripped = _strip_tokens(key)
            if stripped:
                _EQUIPO_STRIPPED.setdefault(stripped, equipo_id)
    _EQUIPO_KEYS = list(_EQUIPO_CACHE.keys())
    log_scraper_event(SCRAPER_NAME, "info", f"Loaded Argentina teams: {len(_EQUIPO_CACHE)}")


def resolve_equipo(nombre: str | None) -> int | None:
    if not nombre:
        return None
    load_equipo_cache()
    name_norm = _team_key(nombre)
    alias_target = TEAM_ALIASES.get(name_norm)
    if alias_target and alias_target in _EQUIPO_CACHE:
        return _EQUIPO_CACHE[alias_target]
    if name_norm in _EQUIPO_CACHE:
        return _EQUIPO_CACHE[name_norm]

    stripped = _strip_tokens(name_norm)
    alias_stripped = TEAM_ALIASES.get(stripped)
    if alias_stripped and alias_stripped in _EQUIPO_CACHE:
        return _EQUIPO_CACHE[alias_stripped]
    if stripped in _EQUIPO_STRIPPED:
        return _EQUIPO_STRIPPED[stripped]

    for key, equipo_id in _EQUIPO_CACHE.items():
        key_stripped = _strip_tokens(key)
        if stripped and (stripped == key_stripped or stripped in key_stripped or key_stripped in stripped):
            return equipo_id

    close = difflib.get_close_matches(name_norm, _EQUIPO_KEYS, n=1, cutoff=0.72)
    return _EQUIPO_CACHE[close[0]] if close else None


def fetch_round_events(season_id: int, round_number: int) -> list[dict[str, Any]]:
    endpoint = f"unique-tournament/{TOURNAMENT_ID}/season/{season_id}/events/round/{round_number}"
    data = _get(endpoint)
    return data.get("events") or []


def parse_event(event: dict[str, Any]) -> dict[str, Any]:
    status = event.get("status") or {}
    home = event.get("homeTeam") or {}
    away = event.get("awayTeam") or {}
    home_score = event.get("homeScore") or {}
    away_score = event.get("awayScore") or {}
    round_info = event.get("roundInfo") or {}
    estado = ESTADO_MAP.get(status.get("type"), "programado")

    if estado == "finalizado":
        goles_local = home_score.get("normaltime")
        if goles_local is None:
            goles_local = home_score.get("current")
        goles_visitante = away_score.get("normaltime")
        if goles_visitante is None:
            goles_visitante = away_score.get("current")
    else:
        goles_local = home_score.get("current")
        goles_visitante = away_score.get("current")

    return {
        "sofascore_id": safe_int(event.get("id")),
        "liga_id": DB_LIGA_ID,
        "temporada": DB_TEMPORADA,
        "jornada": safe_int(round_info.get("round")),
        "fecha": _ts_to_iso(event.get("startTimestamp")),
        "equipo_local": resolve_equipo(home.get("name")),
        "equipo_visitante": resolve_equipo(away.get("name")),
        "goles_local": safe_int(goles_local),
        "goles_visitante": safe_int(goles_visitante),
        "estado": estado,
        "_equipo_local_nombre": home.get("name"),
        "_equipo_visitante_nombre": away.get("name"),
    }


def fetch_and_transform_matches(season_id: int = SEASON_ID) -> tuple[list[dict[str, Any]], list[str], set[int]]:
    rows = []
    errors = []
    rounds_found: set[int] = set()
    consecutive_empty_after_data = 0

    for round_number in range(1, MAX_ROUND + 1):
        try:
            events = fetch_round_events(season_id, round_number)
        except Exception as exc:
            message = f"Ronda {round_number}: fetch error: {exc}"
            if rounds_found:
                consecutive_empty_after_data += 1
                if consecutive_empty_after_data >= 3:
                    break
            else:
                errors.append(message)
                log_scraper_event(SCRAPER_NAME, "warning", message)
            continue

        if events:
            rounds_found.add(round_number)
            consecutive_empty_after_data = 0
        elif rounds_found:
            consecutive_empty_after_data += 1
            if consecutive_empty_after_data >= 3:
                break

        for event in events:
            row = parse_event(event)
            row["jornada"] = row["jornada"] or round_number
            if row["equipo_local"] is None:
                errors.append(f"Ronda {round_number}: local no resuelto '{row['_equipo_local_nombre']}'")
            if row["equipo_visitante"] is None:
                errors.append(f"Ronda {round_number}: visitante no resuelto '{row['_equipo_visitante_nombre']}'")
            rows.append(row)
        log_scraper_event(SCRAPER_NAME, "info", f"Ronda {round_number}: {len(events)} partidos")
        time.sleep(REQUEST_DELAY)

    return rows, errors, rounds_found


def _row_quality(row: dict[str, Any]) -> tuple[int, str]:
    score = 0
    if row.get("estado") == "finalizado":
        score += 4
    if row.get("goles_local") is not None and row.get("goles_visitante") is not None:
        score += 2
    if row.get("sofascore_id") is not None:
        score += 1
    return score, str(row.get("fecha") or "")


def db_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    valid_rows = []
    for row in rows:
        if row.get("equipo_local") is None or row.get("equipo_visitante") is None:
            continue
        valid_rows.append(
            {
                "sofascore_id": row["sofascore_id"],
                "liga_id": row["liga_id"],
                "temporada": row["temporada"],
                "jornada": row["jornada"],
                "fecha": row["fecha"],
                "equipo_local": row["equipo_local"],
                "equipo_visitante": row["equipo_visitante"],
                "goles_local": row["goles_local"],
                "goles_visitante": row["goles_visitante"],
                "estado": row["estado"],
            }
        )
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in valid_rows:
        key = (row["liga_id"], row["temporada"], row["equipo_local"], row["equipo_visitante"], row["jornada"])
        existing = deduped.get(key)
        if existing is None or _row_quality(row) > _row_quality(existing):
            deduped[key] = row
    return list(deduped.values()), len(valid_rows) - len(deduped)


def save_rows(rows: list[dict[str, Any]]) -> int:
    total = 0
    for index in range(0, len(rows), BATCH_SIZE):
        result = upsert_partido(rows[index : index + BATCH_SIZE])
        total += len(result) if isinstance(result, list) else int(bool(result))
    return total


def run(dry_run: bool = False) -> dict[str, Any]:
    load_equipo_cache()
    rows, errors, rounds = fetch_and_transform_matches(SEASON_ID)
    valid_rows, duplicate_count = db_rows(rows)
    upserted = 0 if dry_run else save_rows(valid_rows)
    return {
        "dry_run": dry_run,
        "season_id": SEASON_ID,
        "rondas_encontradas": len(rounds),
        "rondas": sorted(rounds),
        "partidos_encontrados": len(rows),
        "partidos_emparejados": len(valid_rows),
        "partidos_descartados": len(rows) - len(valid_rows),
        "duplicados_descartados": duplicate_count,
        "filas_upsertadas": upserted,
        "errores": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Argentina matches from Sofascore")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and transform without writing")
    args = parser.parse_args()
    result = run(dry_run=args.dry_run)
    log.info("RESUMEN ARGENTINA PARTIDOS: %s", result)


if __name__ == "__main__":
    main()
