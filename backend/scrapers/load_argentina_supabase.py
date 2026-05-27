"""Load Liga Profesional Argentina data into Supabase."""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from scrapers.argentina_clasificacion_sofascore import run as run_clasificacion
from scrapers.argentina_estadisticas_sofascore import (
    SEASON_ID,
    TOURNAMENT_ID,
    build_sofascore_index,
    fetch_summary_stats,
    match_players,
    normalize_db_players,
    run as run_estadisticas,
)
from scrapers.argentina_partidos_sofascore import run as run_partidos
from scrapers.argentina_plantillas_transfermarkt import run as run_plantillas
from scrapers.common.logger import log_scraper_event
from scrapers.common.normalizers import normalize_name, safe_int


SCRAPER_NAME = "load_argentina_supabase"
CFG = get_league("argentina")
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

LOADERS = None
LOADERS_ERROR = None
STRIP_TOKENS = {"aa", "ac", "ca", "cas", "club", "atletico", "cs", "csd", "fc"}


def _loaders_required() -> Any:
    global LOADERS
    if LOADERS is None:
        from scrapers.common import loaders

        LOADERS = loaders
    return LOADERS


def _loaders_optional() -> Any | None:
    global LOADERS_ERROR
    if LOADERS_ERROR is not None:
        return None
    try:
        return _loaders_required()
    except Exception as exc:
        LOADERS_ERROR = str(exc)
        log_scraper_event(SCRAPER_NAME, "warning", f"Supabase loaders unavailable: {exc}")
        return None


def _strip(name_norm: str) -> str:
    return " ".join(part for part in name_norm.split() if part not in STRIP_TOKENS)


def _team_key(value: Any) -> str:
    cleaned = str(value or "").replace("(", " ").replace(")", " ").replace(".", " ")
    return normalize_name(cleaned)


def _aliases() -> dict[str, str]:
    aliases = {
        _team_key(source): _team_key(target)
        for source, target in (CFG.get("aliases_equipos") or {}).items()
    }
    aliases.update({target: target for target in aliases.values()})
    return aliases


ALIASES = _aliases()


def _canonical_team(value: Any) -> str:
    norm = _team_key(value)
    if not norm:
        return ""
    if norm in ALIASES:
        return ALIASES[norm]
    stripped = _strip(norm)
    return ALIASES.get(stripped, stripped or norm)


def _empty_summary(dry_run: bool) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "liga_insertada": False,
        "liga_existente": False,
        "equipos_detectados": 0,
        "jugadores_detectados": 0,
        "estadisticas_detectadas": 0,
        "estadisticas_emparejadas": 0,
        "partidos_detectados": 0,
        "partidos_emparejados": 0,
        "rondas_detectadas": 0,
        "equipos_insertados": 0,
        "jugadores_insertados": 0,
        "estadisticas_insertadas": 0,
        "partidos_insertados": 0,
        "registros_actualizados": 0,
        "errores": [],
        "aliases_sugeridos": [],
    }


def _team_row_from_classification(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "nombre": row["equipo_nombre"],
        "liga_id": CFG["db_liga_id"],
        "temporada": CFG["temporada"],
        "posicion_clasificacion": row.get("posicion_clasificacion"),
        "puntos": row.get("puntos"),
        "escudo_url": (
            f"https://api.sofascore.app/api/v1/team/{row['sofascore_team_id']}/image"
            if row.get("sofascore_team_id")
            else None
        ),
    }


def _player_row_from_transfermarkt(player: dict[str, Any], equipo_id: int) -> dict[str, Any]:
    return {
        "nombre": player["nombre"],
        "equipo_id": equipo_id,
        "posicion": player.get("posicion"),
        "edad": player.get("edad"),
        "nacionalidad": player.get("nacionalidad"),
        "foto_url": player.get("foto_url"),
        "valor_mercado": player.get("valor_mercado"),
    }


def _build_team_map_from_rows(team_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_norm = {}
    for index, row in enumerate(team_rows, 1):
        fake_row = {"id": row.get("id") or -index, **row}
        by_norm[_canonical_team(row.get("nombre"))] = fake_row
        by_norm[normalize_name(row.get("nombre"))] = fake_row
    return by_norm


def _build_team_map_from_db() -> dict[str, dict[str, Any]]:
    loaders = _loaders_optional()
    equipos = loaders.list_equipos_by_liga(CFG["db_liga_id"], CFG["temporada"]) if loaders else []
    return _build_team_map_from_rows(equipos)


def _resolve_team_id(team_name: str, teams_by_norm: dict[str, dict[str, Any]]) -> int | None:
    canonical = _canonical_team(team_name)
    if canonical in teams_by_norm:
        return teams_by_norm[canonical]["id"]
    norm = _team_key(team_name)
    if norm in teams_by_norm:
        return teams_by_norm[norm]["id"]
    stripped = _strip(norm)
    if stripped in teams_by_norm:
        return teams_by_norm[stripped]["id"]
    return None


def ensure_liga(dry_run: bool, summary: dict[str, Any]) -> None:
    loaders = _loaders_optional() if dry_run else _loaders_required()
    existing = loaders.get_liga_by_id(CFG["db_liga_id"]) if loaders else None
    if existing:
        summary["liga_existente"] = True
        return

    row = {
        "id": CFG["db_liga_id"],
        "nombre": CFG["nombre"],
        "pais": CFG["pais"],
        "temporada_actual": CFG["temporada"],
    }
    if dry_run:
        summary["liga_insertada"] = True
        return

    loaders.upsert_liga(row)
    summary["liga_insertada"] = True


def load_teams(dry_run: bool, summary: dict[str, Any]) -> list[dict[str, Any]]:
    classification = run_clasificacion()["clasificacion"]
    summary["equipos_detectados"] = len(classification)
    team_rows = [_team_row_from_classification(row) for row in classification]

    loaders = _loaders_optional() if dry_run else _loaders_required()
    for row in team_rows:
        existing = (
            loaders.get_equipo_by_name(CFG["db_liga_id"], CFG["temporada"], row["nombre"])
            if loaders
            else None
        )
        if dry_run:
            summary["registros_actualizados" if existing else "equipos_insertados"] += 1
            continue
        result = loaders.upsert_equipo(row)
        row["id"] = result.get("id") if isinstance(result, dict) else row.get("id")
        summary["registros_actualizados" if existing else "equipos_insertados"] += 1
    return team_rows


def load_players(dry_run: bool, summary: dict[str, Any], team_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    plantillas = run_plantillas()
    players = plantillas["jugadores"]
    summary["jugadores_detectados"] = len(players)
    teams_by_norm = _build_team_map_from_rows(team_rows) if dry_run else _build_team_map_from_db()
    equipos_by_id = {team["id"]: team for team in teams_by_norm.values() if team.get("id") is not None}

    planned_players = []
    loaders = _loaders_optional() if dry_run else _loaders_required()
    for index, player in enumerate(players, 1):
        equipo_id = _resolve_team_id(player.get("equipo_nombre", ""), teams_by_norm)
        if equipo_id is None:
            message = f"Equipo no resuelto para jugador {player.get('nombre')} ({player.get('equipo_nombre')})"
            summary["errores"].append(message)
            if player.get("equipo_nombre"):
                summary["aliases_sugeridos"].append(player.get("equipo_nombre"))
            continue

        player_row = _player_row_from_transfermarkt(player, equipo_id)
        if dry_run:
            player_row["id"] = -index
            planned_players.append(player_row)
            summary["jugadores_insertados"] += 1
            continue

        existing = loaders.get_jugador_by_name_equipo(player_row["nombre"], equipo_id)
        result = loaders.upsert_jugador(player_row)
        if isinstance(result, dict):
            player_row["id"] = result.get("id")
        planned_players.append(player_row)
        summary["registros_actualizados" if existing else "jugadores_insertados"] += 1

    return planned_players, equipos_by_id


def load_stats(dry_run: bool, summary: dict[str, Any], players: list[dict[str, Any]], equipos_by_id: dict[int, dict[str, Any]]) -> None:
    summary_rows = fetch_summary_stats(SEASON_ID)
    exact, by_name = build_sofascore_index(summary_rows)
    summary["estadisticas_detectadas"] = len({row["sofascore_player_id"] for row in exact.values()})

    if dry_run:
        db_players = normalize_db_players(players, equipos_by_id)
        matched, match_summary = match_players(db_players, exact, by_name)
        summary["estadisticas_emparejadas"] = len(matched)
        summary["aliases_sugeridos"].extend(
            f"{item['jugador']} ({item['equipo']})" for item in match_summary.get("unmatched_samples", [])
        )
        return

    result = run_estadisticas(dry_run=False, fast=False)
    summary["estadisticas_emparejadas"] = result["jugadores_emparejados"]
    summary["estadisticas_insertadas"] = result["filas_upsertadas"]
    for item in result.get("unmatched_samples", []):
        summary["aliases_sugeridos"].append(f"{item['jugador']} ({item['equipo']})")


def _get_round_events(round_number: int) -> list[dict[str, Any]]:
    endpoint = f"unique-tournament/{TOURNAMENT_ID}/season/{SEASON_ID}/events/round/{round_number}"
    response = SESSION.get(f"{API}/{endpoint}", headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.json().get("events") or []


def _event_team_names(event: dict[str, Any]) -> tuple[str | None, str | None]:
    home = event.get("homeTeam") or {}
    away = event.get("awayTeam") or {}
    return home.get("name"), away.get("name")


def _ts_to_iso(timestamp: Any) -> str | None:
    ts = safe_int(timestamp)
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def load_matches(dry_run: bool, summary: dict[str, Any], team_rows: list[dict[str, Any]]) -> None:
    if not dry_run:
        result = run_partidos(dry_run=False)
        summary["partidos_detectados"] = result["partidos_encontrados"]
        summary["partidos_emparejados"] = result["partidos_emparejados"]
        summary["partidos_insertados"] = result["filas_upsertadas"]
        summary["rondas_detectadas"] = result["rondas_encontradas"]
        summary["errores"].extend(result["errores"])
        return

    teams_by_norm = _build_team_map_from_rows(team_rows)
    rounds = set()
    consecutive_empty_after_data = 0
    for round_number in range(1, 41):
        try:
            events = _get_round_events(round_number)
        except Exception:
            if rounds:
                consecutive_empty_after_data += 1
                if consecutive_empty_after_data >= 3:
                    break
            continue
        if events:
            rounds.add(round_number)
            consecutive_empty_after_data = 0
        elif rounds:
            consecutive_empty_after_data += 1
            if consecutive_empty_after_data >= 3:
                break
        for event in events:
            home_name, away_name = _event_team_names(event)
            summary["partidos_detectados"] += 1
            if _resolve_team_id(home_name or "", teams_by_norm) and _resolve_team_id(away_name or "", teams_by_norm):
                summary["partidos_emparejados"] += 1
            else:
                if home_name and not _resolve_team_id(home_name, teams_by_norm):
                    summary["aliases_sugeridos"].append(home_name)
                if away_name and not _resolve_team_id(away_name, teams_by_norm):
                    summary["aliases_sugeridos"].append(away_name)
        time.sleep(0.2)
    summary["rondas_detectadas"] = len(rounds)


def run(dry_run: bool = False) -> dict[str, Any]:
    summary = _empty_summary(dry_run)
    log_scraper_event(SCRAPER_NAME, "info", f"Starting Argentina Supabase load dry_run={dry_run}")
    ensure_liga(dry_run, summary)
    team_rows = load_teams(dry_run, summary)
    players, equipos_by_id = load_players(dry_run, summary, team_rows)
    load_stats(dry_run, summary, players, equipos_by_id)
    load_matches(dry_run, summary, team_rows)
    summary["aliases_sugeridos"] = sorted(set(summary["aliases_sugeridos"]))[:50]
    log_scraper_event(SCRAPER_NAME, "info", f"Summary: {summary}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Argentina into Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and count without writing")
    args = parser.parse_args()
    print(run(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
