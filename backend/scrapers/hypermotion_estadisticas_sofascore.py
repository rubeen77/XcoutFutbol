"""
LaLiga Hypermotion player statistics scraper from Sofascore.

Creates base rows in estadisticas_jugador for liga_id=33 using the same
Sofascore API style already used by the existing league scrapers.

Usage:
  conda run -n xcout --no-capture-output python backend/scrapers/hypermotion_estadisticas_sofascore.py --dry-run
  conda run -n xcout --no-capture-output python backend/scrapers/hypermotion_estadisticas_sofascore.py
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from database.supabase_client import supabase
from scrapers.common.loaders import upsert_estadisticas_jugador
from scrapers.common.logger import log_scraper_event
from scrapers.common.normalizers import (
    calculate_per90,
    normalize_name,
    safe_float,
    safe_int,
)


SCRAPER_NAME = "hypermotion_estadisticas_sofascore"
CFG = get_league("hypermotion")

TOURNAMENT_ID = 54
SEASON_ID = CFG.get("sofascore_season_id")
DB_LIGA_ID = 33
DB_TEMPORADA = CFG["temporada"]

PAGE_SIZE = 100
REQUEST_DELAY = 0.8
PLAYER_DELAY = 0.35
BATCH_SIZE = 100

API = "https://api.sofascore.com/api/v1"
SESSION = requests.Session(impersonate="chrome124")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(SCRAPER_NAME)


def _get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API}/{endpoint.lstrip('/')}"
    response = SESSION.get(url, headers=HEADERS, params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def _team_aliases() -> dict[str, str]:
    aliases = {
        normalize_name(source): normalize_name(target)
        for source, target in (CFG.get("aliases_equipos") or {}).items()
    }

    # Treat configured aliases as equivalent in both directions. This lets a DB
    # name and a Sofascore name converge on the same canonical form.
    aliases.update({target: target for target in aliases.values()})
    return aliases


TEAM_ALIASES = _team_aliases()
TEAM_PREFIXES = {"ad", "atletico", "ca", "cd", "cf", "fc", "rc", "rcd", "real", "sd", "ud"}


def canonical_team_name(value: Any) -> str:
    name = normalize_name(value)
    if not name:
        return ""
    if name in TEAM_ALIASES:
        return TEAM_ALIASES[name]

    stripped = " ".join(part for part in name.split() if part not in TEAM_PREFIXES)
    if stripped in TEAM_ALIASES:
        return TEAM_ALIASES[stripped]
    return stripped or name


def discover_season_id() -> int:
    log_scraper_event(SCRAPER_NAME, "info", "Fetching Sofascore seasons for Hypermotion")
    data = _get(f"unique-tournament/{TOURNAMENT_ID}/seasons")
    seasons = data.get("seasons") or []

    for season in seasons:
        text = " ".join(str(season.get(key, "")) for key in ("name", "year"))
        if "25/26" in text or "2025/26" in text or ("2025" in text and "2026" in text):
            season_id = safe_int(season.get("id"))
            if season_id is not None:
                log_scraper_event(
                    SCRAPER_NAME,
                    "info",
                    f"Using season_id={season_id} ({season.get('name')})",
                )
                return season_id

    if seasons:
        season_id = safe_int(seasons[0].get("id"))
        if season_id is not None:
            log_scraper_event(
                SCRAPER_NAME,
                "warning",
                f"Season 25/26 not found; using first season_id={season_id}",
            )
            return season_id

    raise RuntimeError("No Sofascore season_id found for Hypermotion")


def fetch_summary_stats(season_id: int) -> list[dict[str, Any]]:
    log_scraper_event(SCRAPER_NAME, "info", "Fetching paginated Sofascore summary stats")
    endpoint = f"unique-tournament/{TOURNAMENT_ID}/season/{season_id}/statistics"
    params = {
        "limit": PAGE_SIZE,
        "order": "-rating",
        "accumulation": "total",
        "group": "summary",
    }

    data = _get(endpoint, {**params, "offset": 0})
    pages = safe_int(data.get("pages")) or 1
    rows = data.get("results") or []

    for page in range(1, pages):
        time.sleep(REQUEST_DELAY)
        try:
            page_data = _get(endpoint, {**params, "offset": page * PAGE_SIZE})
            rows.extend(page_data.get("results") or [])
        except Exception as exc:
            log_scraper_event(SCRAPER_NAME, "warning", f"Skipping stats page {page}: {exc}")

    log_scraper_event(SCRAPER_NAME, "info", f"Sofascore summary rows fetched: {len(rows)}")
    return rows


def fetch_player_overall(sofascore_player_id: int, season_id: int) -> dict[str, Any]:
    endpoint = (
        f"player/{sofascore_player_id}/unique-tournament/{TOURNAMENT_ID}"
        f"/season/{season_id}/statistics/overall"
    )
    try:
        data = _get(endpoint)
        return data.get("statistics") or {}
    except Exception as exc:
        log_scraper_event(
            SCRAPER_NAME,
            "warning",
            f"Player statistics unavailable ss_player_id={sofascore_player_id}: {exc}",
        )
        return {}


def build_sofascore_index(summary_rows: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], dict], dict[str, list[dict]]]:
    exact: dict[tuple[str, str], dict[str, Any]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}

    for row in summary_rows:
        player = row.get("player") or {}
        team = row.get("team") or {}
        player_id = safe_int(player.get("id"))
        player_name = player.get("name")
        team_name = team.get("name")

        if player_id is None or not player_name:
            continue

        record = {
            "sofascore_player_id": player_id,
            "sofascore_team_id": safe_int(team.get("id")),
            "player_name": player_name,
            "player_norm": normalize_name(player_name),
            "team_name": team_name,
            "team_norm": canonical_team_name(team_name),
            "summary": row,
        }
        exact[(record["player_norm"], record["team_norm"])] = record
        by_name.setdefault(record["player_norm"], []).append(record)

    return exact, by_name


def load_supabase_players() -> list[dict[str, Any]]:
    log_scraper_event(SCRAPER_NAME, "info", "Loading Hypermotion teams and players from Supabase")
    equipos = (
        supabase.table("equipos")
        .select("id,nombre")
        .eq("liga_id", DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .execute()
        .data
        or []
    )
    equipo_ids = [equipo["id"] for equipo in equipos if equipo.get("id") is not None]
    equipos_by_id = {equipo["id"]: equipo for equipo in equipos}

    if not equipo_ids:
        return []

    jugadores = (
        supabase.table("jugadores")
        .select("id,nombre,equipo_id,posicion")
        .in_("equipo_id", equipo_ids)
        .execute()
        .data
        or []
    )

    rows = []
    for jugador in jugadores:
        equipo = equipos_by_id.get(jugador.get("equipo_id")) or {}
        rows.append(
            {
                "jugador_id": jugador.get("id"),
                "nombre": jugador.get("nombre"),
                "nombre_norm": normalize_name(jugador.get("nombre")),
                "equipo_id": jugador.get("equipo_id"),
                "equipo_nombre": equipo.get("nombre"),
                "equipo_norm": canonical_team_name(equipo.get("nombre")),
                "posicion": jugador.get("posicion"),
            }
        )

    log_scraper_event(SCRAPER_NAME, "info", f"Supabase players loaded: {len(rows)}")
    return rows


def match_players(
    db_players: list[dict[str, Any]],
    exact: dict[tuple[str, str], dict[str, Any]],
    by_name: dict[str, list[dict[str, Any]]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    summary = {
        "matched_exact": 0,
        "matched_by_name": 0,
        "unmatched": 0,
        "ambiguous": 0,
        "unmatched_samples": [],
    }

    for player in db_players:
        key = (player["nombre_norm"], player["equipo_norm"])
        ss_record = exact.get(key)

        if ss_record:
            summary["matched_exact"] += 1
            matched.append((player, ss_record))
            continue

        candidates = by_name.get(player["nombre_norm"], [])
        if len(candidates) == 1:
            summary["matched_by_name"] += 1
            matched.append((player, candidates[0]))
            continue

        if len(candidates) > 1:
            summary["ambiguous"] += 1
        else:
            summary["unmatched"] += 1

        if len(summary["unmatched_samples"]) < 20:
            summary["unmatched_samples"].append(
                {
                    "jugador": player.get("nombre"),
                    "equipo": player.get("equipo_nombre"),
                    "motivo": "ambiguous" if candidates else "no_match",
                }
            )

    return matched, summary


def _goalkeeper_save_pct(saves: int | None, goals_conceded: int | None) -> float | None:
    if saves is None or goals_conceded is None:
        return None
    total = saves + goals_conceded
    if total <= 0:
        return None
    return round((saves / total) * 100, 2)


def transform_stats(
    db_player: dict[str, Any],
    ss_record: dict[str, Any],
    overall: dict[str, Any],
) -> dict[str, Any] | None:
    stats = overall or ss_record.get("summary") or {}

    goles = safe_int(stats.get("goals"))
    asistencias = safe_int(stats.get("assists"))
    minutos = safe_int(stats.get("minutesPlayed"))
    regates = safe_int(stats.get("successfulDribbles"))
    pases_pct = safe_float(stats.get("accuratePassesPercentage"), 0)
    intercepciones = safe_int(stats.get("interceptions"))
    entradas = safe_int(stats.get("tacklesWon"))
    if entradas is None:
        entradas = safe_int(stats.get("tackles"))

    recuperaciones = safe_int(stats.get("ballRecovery"))
    if recuperaciones is None:
        tackles = safe_int(stats.get("tackles"))
        if tackles is not None or intercepciones is not None:
            recuperaciones = (tackles or 0) + (intercepciones or 0)

    saves = safe_int(stats.get("saves"))
    goals_conceded = safe_int(stats.get("goalsConceded"))

    if not any(
        value is not None
        for value in (
            goles,
            asistencias,
            minutos,
            regates,
            pases_pct,
            intercepciones,
            entradas,
            recuperaciones,
            saves,
            goals_conceded,
        )
    ):
        return None

    ga = None
    if goles is not None or asistencias is not None:
        ga = (goles or 0) + (asistencias or 0)

    return {
        "jugador_id": db_player["jugador_id"],
        "temporada": DB_TEMPORADA,
        "liga_id": DB_LIGA_ID,
        "goles": goles,
        "asistencias": asistencias,
        "minutos": minutos,
        "goles_por_90": calculate_per90(goles, minutos),
        "asistencias_por_90": calculate_per90(asistencias, minutos),
        "ga_por_90": calculate_per90(ga, minutos),
        "regates": regates,
        "pases_completados": safe_int(pases_pct),
        "intercepciones": intercepciones,
        "entradas": entradas,
        "recuperaciones": recuperaciones,
        "portero_paradas": saves,
        "portero_goles_encajados": goals_conceded,
        "portero_paradas_pct": _goalkeeper_save_pct(saves, goals_conceded),
        "xg": safe_float(stats.get("expectedGoals")),
        "xa": safe_float(stats.get("expectedAssists")),
    }


def generate_rows(
    matched_players: list[tuple[dict[str, Any], dict[str, Any]]],
    season_id: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = []
    errors = []

    for index, (db_player, ss_record) in enumerate(matched_players, 1):
        if index > 1:
            time.sleep(PLAYER_DELAY)

        overall = fetch_player_overall(ss_record["sofascore_player_id"], season_id)
        row = transform_stats(db_player, ss_record, overall)

        if row is None:
            errors.append(f"No stats for {db_player.get('nombre')} ({db_player.get('equipo_nombre')})")
            continue

        rows.append(row)

        if index % 50 == 0:
            log_scraper_event(
                SCRAPER_NAME,
                "info",
                f"Processed {index}/{len(matched_players)} matched players",
            )

    return rows, errors


def upsert_rows(rows: list[dict[str, Any]]) -> int:
    total = 0
    for index in range(0, len(rows), BATCH_SIZE):
        batch = rows[index : index + BATCH_SIZE]
        result = upsert_estadisticas_jugador(batch)
        total += len(result) if isinstance(result, list) else int(bool(result))
    return total


def run(dry_run: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    season_id = safe_int(SEASON_ID) if SEASON_ID else discover_season_id()
    if season_id is None:
        raise RuntimeError("No season_id resolved")

    log_scraper_event(
        SCRAPER_NAME,
        "info",
        f"Starting Hypermotion stats scraper tournament_id={TOURNAMENT_ID} season_id={season_id}",
    )

    summary_rows = fetch_summary_stats(season_id)
    exact, by_name = build_sofascore_index(summary_rows)
    db_players = load_supabase_players()
    matched, match_summary = match_players(db_players, exact, by_name)

    log_scraper_event(
        SCRAPER_NAME,
        "info",
        (
            "Matching done: "
            f"exact={match_summary['matched_exact']} "
            f"name={match_summary['matched_by_name']} "
            f"unmatched={match_summary['unmatched']} "
            f"ambiguous={match_summary['ambiguous']}"
        ),
    )

    rows, row_errors = generate_rows(matched, season_id)
    errors.extend(row_errors)

    upserted = 0
    if dry_run:
        log_scraper_event(SCRAPER_NAME, "info", f"[dry-run] Rows generated: {len(rows)}")
    else:
        upserted = upsert_rows(rows)
        log_scraper_event(SCRAPER_NAME, "info", f"Rows upserted: {upserted}")

    return {
        "dry_run": dry_run,
        "tournament_id": TOURNAMENT_ID,
        "season_id": season_id,
        "jugadores_sofascore": len({row["sofascore_player_id"] for row in exact.values()}),
        "jugadores_supabase": len(db_players),
        "jugadores_emparejados": len(matched),
        "matched_exact": match_summary["matched_exact"],
        "matched_by_name": match_summary["matched_by_name"],
        "unmatched": match_summary["unmatched"],
        "ambiguous": match_summary["ambiguous"],
        "unmatched_samples": match_summary["unmatched_samples"],
        "filas_generadas": len(rows),
        "filas_upsertadas": upserted,
        "errores": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Hypermotion player stats from Sofascore")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and transform without writing to Supabase")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run)

    log.info("=" * 68)
    log.info("RESUMEN HYPERMOTION ESTADISTICAS")
    log.info("  Dry-run                 : %s", result["dry_run"])
    log.info("  Tournament ID           : %s", result["tournament_id"])
    log.info("  Season ID               : %s", result["season_id"])
    log.info("  Jugadores Sofascore     : %s", result["jugadores_sofascore"])
    log.info("  Jugadores Supabase      : %s", result["jugadores_supabase"])
    log.info("  Emparejados             : %s", result["jugadores_emparejados"])
    log.info("    exactos               : %s", result["matched_exact"])
    log.info("    por nombre            : %s", result["matched_by_name"])
    log.info("  Sin match               : %s", result["unmatched"])
    log.info("  Ambiguos                : %s", result["ambiguous"])
    log.info("  Filas generadas         : %s", result["filas_generadas"])
    log.info("  Filas upsertadas        : %s", result["filas_upsertadas"])
    log.info("  Errores                 : %s", len(result["errores"]))
    if result["unmatched_samples"]:
        log.info("  Muestras sin match      : %s", result["unmatched_samples"][:10])
    if result["errores"]:
        log.info("  Primeros errores        : %s", result["errores"][:10])
    log.info("=" * 68)


if __name__ == "__main__":
    main()
