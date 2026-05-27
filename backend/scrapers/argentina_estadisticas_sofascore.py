"""Liga Profesional Argentina player statistics scraper from Sofascore."""

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
from scrapers.common.normalizers import calculate_per90, normalize_name, safe_float, safe_int


SCRAPER_NAME = "argentina_estadisticas_sofascore"
CFG = get_league("argentina")

TOURNAMENT_ID = CFG["sofascore_tournament_id"]
SEASON_ID = CFG["sofascore_season_id"]
DB_LIGA_ID = CFG["db_liga_id"]
DB_TEMPORADA = CFG["temporada"]
PAGE_SIZE = 100
REQUEST_DELAY = 0.5
PLAYER_DELAY = 0.08
BATCH_SIZE = 100

API = "https://api.sofascore.com/api/v1"
SESSION = requests.Session(impersonate="chrome124")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.sofascore.com/",
    "Origin": "https://www.sofascore.com",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(SCRAPER_NAME)


def _get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    url = f"{API}/{endpoint.lstrip('/')}"
    response = SESSION.get(url, headers=HEADERS, params=params, timeout=25)
    response.raise_for_status()
    return response.json()


TEAM_PREFIXES = {
    "aa",
    "ac",
    "ca",
    "cas",
    "club",
    "atletico",
    "cs",
    "csd",
    "de",
    "fc",
    "la",
    "santa",
}


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


def canonical_team_name(value: Any) -> str:
    name = _team_key(value)
    if not name:
        return ""
    if name in TEAM_ALIASES:
        return TEAM_ALIASES[name]
    compact = " ".join(part for part in name.split() if part not in TEAM_PREFIXES)
    if compact in TEAM_ALIASES:
        return TEAM_ALIASES[compact]
    return compact or name


def fetch_summary_stats(season_id: int = SEASON_ID) -> list[dict[str, Any]]:
    log_scraper_event(SCRAPER_NAME, "info", "Fetching Argentina paginated Sofascore summary stats")
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


def fetch_player_overall(sofascore_player_id: int, season_id: int = SEASON_ID) -> dict[str, Any]:
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
    return normalize_db_players(jugadores, equipos_by_id)


def normalize_db_players(jugadores: list[dict[str, Any]], equipos_by_id: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
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
    return rows


def match_players(
    db_players: list[dict[str, Any]],
    exact: dict[tuple[str, str], dict[str, Any]],
    by_name: dict[str, list[dict[str, Any]]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], dict[str, Any]]:
    matched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    summary = {"matched_exact": 0, "matched_by_name": 0, "unmatched": 0, "ambiguous": 0, "unmatched_samples": []}
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
    return round((saves / total) * 100, 2) if total > 0 else None


def transform_stats(db_player: dict[str, Any], ss_record: dict[str, Any], overall: dict[str, Any]) -> dict[str, Any] | None:
    stats = overall or ss_record.get("summary") or {}
    goles = safe_int(stats.get("goals"))
    asistencias = safe_int(stats.get("assists"))
    minutos = safe_int(stats.get("minutesPlayed"))
    regates = safe_int(stats.get("successfulDribbles"))
    pases_pct = safe_float(stats.get("accuratePassesPercentage"), 0)
    pases = safe_int(stats.get("accuratePasses"))
    intercepciones = safe_int(stats.get("interceptions"))
    entradas = safe_int(stats.get("tacklesWon"))
    if entradas is None:
        entradas = safe_int(stats.get("tackles"))
    recuperaciones = safe_int(stats.get("ballRecovery"))
    if recuperaciones is None and (entradas is not None or intercepciones is not None):
        recuperaciones = (entradas or 0) + (intercepciones or 0)

    saves = safe_int(stats.get("saves"))
    goals_conceded = safe_int(stats.get("goalsConceded"))
    ga = (goles or 0) + (asistencias or 0) if (goles is not None or asistencias is not None) else None

    if not any(
        value is not None
        for value in (goles, asistencias, minutos, regates, pases_pct, pases, intercepciones, entradas, saves)
    ):
        return None

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
        "xg": safe_float(stats.get("expectedGoals")),
        "xa": safe_float(stats.get("expectedAssists")),
        "regates": regates,
        "pases_completados": pases if pases is not None else safe_int(pases_pct),
        "intercepciones": intercepciones,
        "entradas": entradas,
        "recuperaciones": recuperaciones,
        "portero_paradas": saves,
        "portero_goles_encajados": goals_conceded,
        "portero_paradas_pct": _goalkeeper_save_pct(saves, goals_conceded),
    }


def generate_rows(
    matched_players: list[tuple[dict[str, Any], dict[str, Any]]],
    season_id: int = SEASON_ID,
    fetch_overall: bool = True,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows = []
    errors = []
    for index, (db_player, ss_record) in enumerate(matched_players, 1):
        if index > 1 and fetch_overall:
            time.sleep(PLAYER_DELAY)
        overall = fetch_player_overall(ss_record["sofascore_player_id"], season_id) if fetch_overall else {}
        row = transform_stats(db_player, ss_record, overall)
        if row is None:
            errors.append(f"No stats for {db_player.get('nombre')} ({db_player.get('equipo_nombre')})")
            continue
        rows.append(row)
        if index % 100 == 0:
            log_scraper_event(SCRAPER_NAME, "info", f"Processed {index}/{len(matched_players)} matched players")
    return rows, errors


def upsert_rows(rows: list[dict[str, Any]]) -> int:
    total = 0
    for index in range(0, len(rows), BATCH_SIZE):
        result = upsert_estadisticas_jugador(rows[index : index + BATCH_SIZE])
        total += len(result) if isinstance(result, list) else int(bool(result))
    return total


def run(dry_run: bool = False, fast: bool = False) -> dict[str, Any]:
    summary_rows = fetch_summary_stats(SEASON_ID)
    exact, by_name = build_sofascore_index(summary_rows)
    db_players = load_supabase_players()
    matched, match_summary = match_players(db_players, exact, by_name)
    rows, errors = generate_rows(matched, SEASON_ID, fetch_overall=not fast)
    upserted = 0 if dry_run else upsert_rows(rows)
    return {
        "dry_run": dry_run,
        "season_id": SEASON_ID,
        "jugadores_sofascore": len({row["sofascore_player_id"] for row in exact.values()}),
        "jugadores_supabase": len(db_players),
        "jugadores_emparejados": len(matched),
        "matched_exact": match_summary["matched_exact"],
        "matched_by_name": match_summary["matched_by_name"],
        "unmatched": match_summary["unmatched"],
        "ambiguous": match_summary["ambiguous"],
        "filas_generadas": len(rows),
        "filas_upsertadas": upserted,
        "errores": errors,
        "unmatched_samples": match_summary["unmatched_samples"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Argentina player stats from Sofascore")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and transform without writing")
    parser.add_argument("--fast", action="store_true", help="Skip per-player overall calls")
    args = parser.parse_args()
    result = run(dry_run=args.dry_run, fast=args.fast)
    log.info("RESUMEN ARGENTINA ESTADISTICAS: %s", result)


if __name__ == "__main__":
    main()
