"""Supabase upsert helpers for future scrapers."""

from typing import Any

from database.supabase_client import supabase


def _as_list(row_or_rows: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    return row_or_rows if isinstance(row_or_rows, list) else [row_or_rows]


def _return_shape(data: list[dict[str, Any]], single: bool) -> dict[str, Any] | list[dict[str, Any]]:
    if single:
        return data[0] if data else {}
    return data


def upsert_liga(liga: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    """Upsert one or more rows into ligas."""
    single = isinstance(liga, dict)
    rows = _as_list(liga)
    res = (
        supabase.table("ligas")
        .upsert(rows, on_conflict="nombre,pais")
        .execute()
    )
    return _return_shape(res.data or [], single)


def get_liga_by_id(liga_id: int) -> dict[str, Any] | None:
    """Return one liga row by id, if it exists."""
    res = (
        supabase.table("ligas")
        .select("*")
        .eq("id", liga_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def upsert_equipo(equipo: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    """Upsert one or more rows into equipos."""
    single = isinstance(equipo, dict)
    rows = _as_list(equipo)
    res = (
        supabase.table("equipos")
        .upsert(rows, on_conflict="nombre,liga_id,temporada")
        .execute()
    )
    return _return_shape(res.data or [], single)


def get_equipo_by_name(liga_id: int, temporada: str, nombre: str) -> dict[str, Any] | None:
    """Return one equipo row by exact name/league/season."""
    res = (
        supabase.table("equipos")
        .select("*")
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .eq("nombre", nombre)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def list_equipos_by_liga(liga_id: int, temporada: str) -> list[dict[str, Any]]:
    """Return all equipos for one league/season."""
    res = (
        supabase.table("equipos")
        .select("*")
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .execute()
    )
    return res.data or []


def upsert_jugador(jugador: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    """Upsert one or more rows into jugadores."""
    single = isinstance(jugador, dict)
    rows = _as_list(jugador)
    res = (
        supabase.table("jugadores")
        .upsert(rows, on_conflict="nombre,equipo_id")
        .execute()
    )
    return _return_shape(res.data or [], single)


def get_jugador_by_name_equipo(nombre: str, equipo_id: int) -> dict[str, Any] | None:
    """Return one jugador row by exact name and team id."""
    res = (
        supabase.table("jugadores")
        .select("*")
        .eq("nombre", nombre)
        .eq("equipo_id", equipo_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def upsert_estadisticas_jugador(
    estadisticas: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any] | list[dict[str, Any]]:
    """Upsert one or more rows into estadisticas_jugador."""
    single = isinstance(estadisticas, dict)
    rows = _as_list(estadisticas)
    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    return _return_shape(res.data or [], single)


def upsert_partido(partido: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    """Upsert one or more rows into partidos."""
    single = isinstance(partido, dict)
    rows = _as_list(partido)
    conflict = "sofascore_id"
    if not all(row.get("sofascore_id") for row in rows):
        conflict = "liga_id,temporada,equipo_local,equipo_visitante,jornada"

    res = (
        supabase.table("partidos")
        .upsert(rows, on_conflict=conflict)
        .execute()
    )
    return _return_shape(res.data or [], single)
