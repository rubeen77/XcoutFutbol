"""
Endpoints de partidos:
  GET /partidos        — partidos de una jornada (o todos los de la temporada)
  GET /partidos/{id}   — detalle de un partido con eventos
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from database.supabase_client import supabase

router = APIRouter()

# Columnas para la lista de partidos
PARTIDO_SELECT = (
    "id, sofascore_id, jornada, fecha, estado, "
    "goles_local, goles_visitante, xg_local, xg_visitante, "
    "equipo_local, equipo_visitante, "
    "local:equipos!partidos_equipo_local_fkey(id, nombre, escudo_url), "
    "visitante:equipos!partidos_equipo_visitante_fkey(id, nombre, escudo_url)"
)

# Columnas para el detalle — incluye clasificación de cada equipo
PARTIDO_DETALLE_SELECT = (
    "id, sofascore_id, jornada, fecha, estado, "
    "goles_local, goles_visitante, xg_local, xg_visitante, "
    "equipo_local, equipo_visitante, "
    "local:equipos!partidos_equipo_local_fkey(id, nombre, puntos, posicion_clasificacion, escudo_url), "
    "visitante:equipos!partidos_equipo_visitante_fkey(id, nombre, puntos, posicion_clasificacion, escudo_url)"
)


# ---------------------------------------------------------------------------
# GET /partidos
# ---------------------------------------------------------------------------

@router.get("")
def listar_partidos(
    jornada:   Optional[int] = Query(None, description="Número de jornada"),
    liga_id:   int           = Query(1, description="ID de liga"),
    temporada: str           = Query("2526"),
    estado:    Optional[str] = Query(None, description="programado | en_directo | finalizado | aplazado"),
    equipo_id: Optional[int] = Query(None, description="Filtrar partidos de un equipo"),
):
    q = (
        supabase.table("partidos")
        .select(PARTIDO_SELECT)
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .order("jornada", desc=False)
        .order("fecha", desc=False)
    )

    if jornada is not None:
        q = q.eq("jornada", jornada)
    if estado:
        q = q.eq("estado", estado)

    res = q.range(0, 499).execute()
    partidos = res.data

    # Filtro por equipo (local o visitante) — post-fetch
    if equipo_id is not None:
        partidos = [
            p for p in partidos
            if p.get("equipo_local") == equipo_id or p.get("equipo_visitante") == equipo_id
        ]

    return {"total": len(partidos), "partidos": partidos}


# ---------------------------------------------------------------------------
# GET /partidos/recientes  (antes de /{id} para evitar colisión de rutas)
# ---------------------------------------------------------------------------

@router.get("/recientes")
def partidos_recientes(
    liga_id:   int = Query(1),
    temporada: str = Query("2526"),
    limit:     int = Query(4),
):
    """Últimos partidos finalizados de una liga, ordenados por jornada y fecha desc."""
    res = (
        supabase.table("partidos")
        .select(PARTIDO_SELECT)
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .not_.is_("goles_local", "null")
        .order("jornada", desc=True)
        .order("fecha", desc=True)
        .limit(limit)
        .execute()
    )
    return {"partidos": res.data or []}


# ---------------------------------------------------------------------------
# GET /partidos/count  (debe ir ANTES de /{id} para que no colisione)
# ---------------------------------------------------------------------------

@router.get("/count")
def contar_partidos(temporada: str = Query("2526")):
    res = (
        supabase.table("partidos")
        .select("id", count="exact")
        .eq("temporada", temporada)
        .limit(1)
        .execute()
    )
    return {"count": res.count or 0}


# ---------------------------------------------------------------------------
# GET /partidos/eliminatorias  (antes de /{id} para evitar colisión de rutas)
# ---------------------------------------------------------------------------

@router.get("/eliminatorias")
def eliminatorias_ucl(
    liga_id:   int = Query(28),
    temporada: str = Query("2526"),
):
    """Cruces de la fase eliminatoria agrupados por ronda: Octavos→Cuartos→Semis→Final."""
    res = (
        supabase.table("eliminatorias")
        .select("*")
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .order("orden", desc=False)
        .execute()
    )

    RONDA_ORDER = {"Octavos": 1, "Cuartos": 2, "Semifinales": 3, "Final": 4}

    rondas: dict[str, list] = {}
    for cruce in (res.data or []):
        rondas.setdefault(cruce.get("ronda", ""), []).append(cruce)

    rondas_sorted = sorted(rondas.items(), key=lambda x: RONDA_ORDER.get(x[0], 99))

    return {
        "rondas": [
            {"ronda": ronda, "cruces": sorted(cruces, key=lambda c: c.get("orden") or 0)}
            for ronda, cruces in rondas_sorted
        ]
    }


# ---------------------------------------------------------------------------
# GET /partidos/{id}
# ---------------------------------------------------------------------------

@router.get("/{partido_id}")
def detalle_partido(partido_id: int):
    res = (
        supabase.table("partidos")
        .select(PARTIDO_DETALLE_SELECT)
        .eq("id", partido_id)
        .single()
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail=f"Partido {partido_id} no encontrado")

    partido = res.data
    sofascore_id = partido.get("sofascore_id")

    # Eventos: se obtienen en tiempo real desde Sofascore si hay sofascore_id
    eventos = []
    if sofascore_id:
        try:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from scrapers.sofascore_scraper import get_match_events
            eventos = get_match_events(sofascore_id)
        except Exception:
            eventos = []

    return {**partido, "eventos": eventos}
