"""
Endpoints de partidos:
  GET /partidos        — partidos de una jornada (o todos los de la temporada)
  GET /partidos/{id}   — detalle de un partido con eventos
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from database.supabase_client import supabase

router = APIRouter()

# Columnas comunes de partido con nombres de equipo embebidos
PARTIDO_SELECT = (
    "id, sofascore_id, jornada, fecha, estado, "
    "goles_local, goles_visitante, xg_local, xg_visitante, "
    "equipo_local, equipo_visitante, "
    "local:equipos!partidos_equipo_local_fkey(id, nombre), "
    "visitante:equipos!partidos_equipo_visitante_fkey(id, nombre)"
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

    res = q.execute()
    partidos = res.data

    # Filtro por equipo (local o visitante) — post-fetch
    if equipo_id is not None:
        partidos = [
            p for p in partidos
            if p.get("equipo_local") == equipo_id or p.get("equipo_visitante") == equipo_id
        ]

    return {"total": len(partidos), "partidos": partidos}


# ---------------------------------------------------------------------------
# GET /partidos/{id}
# ---------------------------------------------------------------------------

@router.get("/{partido_id}")
def detalle_partido(partido_id: int):
    res = (
        supabase.table("partidos")
        .select(PARTIDO_SELECT)
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
