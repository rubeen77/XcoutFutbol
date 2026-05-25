"""
Load LaLiga Hypermotion data into Supabase.

Scope:
  - liga existence
  - teams + classification from Sofascore
  - players from Transfermarkt ES2

This script uses the common loader/logger modules for Supabase interaction and
logging. It supports --dry-run and does not modify tables or other leagues.
"""

import argparse
import sys
import unicodedata
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.leagues import get_league
from scrapers.common.logger import log_scraper_event
from scrapers.hypermotion_clasificacion_sofascore import run as run_clasificacion


SCRAPER_NAME = "load_hypermotion_supabase"
CFG = get_league("hypermotion")
LOADERS = None
LOADERS_ERROR = None


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


def _norm(value: Any) -> str:
    if value is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(value))
    return " ".join(nfkd.encode("ascii", "ignore").decode("ascii").lower().split())


def _empty_summary(dry_run: bool) -> dict[str, Any]:
    return {
        "dry_run": dry_run,
        "liga_insertada": False,
        "liga_existente": False,
        "equipos_detectados": 0,
        "jugadores_detectados": 0,
        "equipos_insertados": 0,
        "jugadores_insertados": 0,
        "registros_actualizados": 0,
        "errores": [],
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


def _build_team_maps() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    loaders = _loaders_optional()
    equipos = loaders.list_equipos_by_liga(CFG["db_liga_id"], CFG["temporada"]) if loaders else []
    by_norm = {_norm(equipo.get("nombre")): equipo for equipo in equipos}
    aliases = {
        _norm(source): _norm(target)
        for source, target in (CFG.get("aliases_equipos") or {}).items()
    }
    return by_norm, aliases


def _resolve_team_id(
    team_name: str,
    teams_by_norm: dict[str, dict[str, Any]],
    aliases: dict[str, str],
) -> int | None:
    norm = _norm(team_name)
    alias_target = aliases.get(norm)
    if alias_target and alias_target in teams_by_norm:
        return teams_by_norm[alias_target]["id"]
    if norm in teams_by_norm:
        return teams_by_norm[norm]["id"]

    stripped = " ".join(
        part for part in norm.split()
        if part not in {"fc", "cf", "cd", "rcd", "ud", "sd", "ad"}
    )
    for team_norm, equipo in teams_by_norm.items():
        team_stripped = " ".join(
            part for part in team_norm.split()
            if part not in {"fc", "cf", "cd", "rcd", "ud", "sd", "ad"}
        )
        if stripped and stripped == team_stripped:
            return equipo["id"]
    return None


def ensure_liga(dry_run: bool, summary: dict[str, Any]) -> None:
    loaders = _loaders_optional() if dry_run else _loaders_required()
    existing = loaders.get_liga_by_id(CFG["db_liga_id"]) if loaders else None
    if existing:
        summary["liga_existente"] = True
        log_scraper_event(SCRAPER_NAME, "info", f"Liga exists: id={CFG['db_liga_id']}")
        return

    row = {
        "id": CFG["db_liga_id"],
        "nombre": CFG["nombre"],
        "pais": CFG["pais"],
        "temporada_actual": CFG["temporada"],
    }
    if dry_run:
        summary["liga_insertada"] = True
        log_scraper_event(SCRAPER_NAME, "info", f"[dry-run] Would insert liga: {row}")
        return

    loaders.upsert_liga(row)
    summary["liga_insertada"] = True
    log_scraper_event(SCRAPER_NAME, "info", f"Liga inserted/upserted: id={CFG['db_liga_id']}")


def load_teams_and_classification(dry_run: bool, summary: dict[str, Any]) -> list[dict[str, Any]]:
    classification = run_clasificacion()["clasificacion"]
    summary["equipos_detectados"] = len(classification)
    planned_team_rows = []

    for row in classification:
        try:
            equipo_row = _team_row_from_classification(row)
            planned_team_rows.append(equipo_row)
            loaders = _loaders_optional() if dry_run else _loaders_required()
            existing = (
                loaders.get_equipo_by_name(
                    CFG["db_liga_id"],
                    CFG["temporada"],
                    equipo_row["nombre"],
                )
                if loaders
                else None
            )
            if dry_run:
                if existing:
                    summary["registros_actualizados"] += 1
                else:
                    summary["equipos_insertados"] += 1
                continue

            loaders.upsert_equipo(equipo_row)
            if existing:
                summary["registros_actualizados"] += 1
            else:
                summary["equipos_insertados"] += 1
        except Exception as exc:
            message = f"Equipo error {row.get('equipo_nombre')}: {exc}"
            summary["errores"].append(message)
            log_scraper_event(SCRAPER_NAME, "error", message)
    return planned_team_rows


def _is_planned_team(team_name: str, planned_team_rows: list[dict[str, Any]]) -> bool:
    norm = _norm(team_name)
    planned = {_norm(row.get("nombre")) for row in planned_team_rows}
    if norm in planned:
        return True
    stripped = " ".join(
        part for part in norm.split()
        if part not in {"fc", "cf", "cd", "rcd", "ud", "sd", "ad"}
    )
    return any(
        stripped == " ".join(
            part for part in planned_norm.split()
            if part not in {"fc", "cf", "cd", "rcd", "ud", "sd", "ad"}
        )
        for planned_norm in planned
    )


def load_players(
    dry_run: bool,
    summary: dict[str, Any],
    planned_team_rows: list[dict[str, Any]],
) -> None:
    try:
        from scrapers.hypermotion_plantillas_transfermarkt import run as run_plantillas

        plantillas = run_plantillas()
    except Exception as exc:
        message = f"Transfermarkt fetch/parse failed: {exc}"
        summary["errores"].append(message)
        log_scraper_event(SCRAPER_NAME, "error", message)
        return

    players = plantillas["jugadores"]
    summary["jugadores_detectados"] = len(players)
    teams_by_norm, aliases = _build_team_maps()

    for player in players:
        try:
            equipo_id = _resolve_team_id(player.get("equipo_nombre", ""), teams_by_norm, aliases)
            if equipo_id is None:
                if dry_run and _is_planned_team(player.get("equipo_nombre", ""), planned_team_rows):
                    summary["jugadores_insertados"] += 1
                    continue
                message = f"Equipo no resuelto para jugador {player.get('nombre')} ({player.get('equipo_nombre')})"
                summary["errores"].append(message)
                log_scraper_event(SCRAPER_NAME, "warning", message)
                continue

            player_row = _player_row_from_transfermarkt(player, equipo_id)
            loaders = _loaders_optional() if dry_run else _loaders_required()
            existing = (
                loaders.get_jugador_by_name_equipo(player_row["nombre"], equipo_id)
                if loaders
                else None
            )
            if dry_run:
                if existing:
                    summary["registros_actualizados"] += 1
                else:
                    summary["jugadores_insertados"] += 1
                continue

            loaders.upsert_jugador(player_row)
            if existing:
                summary["registros_actualizados"] += 1
            else:
                summary["jugadores_insertados"] += 1
        except Exception as exc:
            message = f"Jugador error {player.get('nombre')}: {exc}"
            summary["errores"].append(message)
            log_scraper_event(SCRAPER_NAME, "error", message)


def run(dry_run: bool = False) -> dict[str, Any]:
    summary = _empty_summary(dry_run)
    log_scraper_event(
        SCRAPER_NAME,
        "info",
        f"Starting Hypermotion Supabase load dry_run={dry_run}",
    )
    ensure_liga(dry_run, summary)
    planned_team_rows = load_teams_and_classification(dry_run, summary)
    load_players(dry_run, summary, planned_team_rows)
    log_scraper_event(SCRAPER_NAME, "info", f"Summary: {summary}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Hypermotion into Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and count without writing")
    args = parser.parse_args()
    summary = run(dry_run=args.dry_run)
    print(summary)


if __name__ == "__main__":
    main()
