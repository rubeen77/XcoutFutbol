"""
Endpoints de equipos:
  GET /equipos       — lista de equipos de una liga
  GET /equipos/{id}  — perfil de un equipo con plantilla y stats agregadas
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from database.supabase_client import supabase

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /equipos
# ---------------------------------------------------------------------------

@router.get("")
def listar_equipos(
    liga_id:   int = Query(1, description="ID de liga (1 = LaLiga)"),
    temporada: str = Query("2526"),
):
    res = (
        supabase.table("equipos")
        .select("id, nombre, liga_id, temporada, posicion_clasificacion, puntos, escudo_url, ligas(nombre, pais)")
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .order("posicion_clasificacion", nullsfirst=False)
        .limit(100)
        .execute()
    )
    return {"total": len(res.data), "equipos": res.data}


# ---------------------------------------------------------------------------
# GET /equipos/{id}
# ---------------------------------------------------------------------------

@router.get("/{equipo_id}")
def perfil_equipo(equipo_id: int, temporada: str = Query("2526")):
    # Datos del equipo
    eq_res = (
        supabase.table("equipos")
        .select("id, nombre, liga_id, temporada, ligas(nombre, pais)")
        .eq("id", equipo_id)
        .single()
        .execute()
    )
    if not eq_res.data:
        raise HTTPException(status_code=404, detail=f"Equipo {equipo_id} no encontrado")

    equipo = eq_res.data

    # Plantilla con stats de la temporada
    plantilla_res = (
        supabase.table("jugadores")
        .select(
            "id, nombre, posicion, edad, nacionalidad, foto_url, valor_mercado, "
            "estadisticas_jugador(temporada, goles, asistencias, xg, xa, minutos, "
            "  goles_por_90, asistencias_por_90, ga_por_90)"
        )
        .eq("equipo_id", equipo_id)
        .eq("estadisticas_jugador.temporada", temporada)
        .order("nombre")
        .execute()
    )

    plantilla = plantilla_res.data

    # Calcular totales del equipo agregando estadísticas individuales
    totales = {"goles": 0, "asistencias": 0, "xg": 0.0, "xa": 0.0, "minutos": 0}
    for j in plantilla:
        stats = (j.get("estadisticas_jugador") or [{}])[0]
        totales["goles"]      += stats.get("goles") or 0
        totales["asistencias"] += stats.get("asistencias") or 0
        totales["xg"]         += stats.get("xg") or 0.0
        totales["xa"]         += stats.get("xa") or 0.0
        totales["minutos"]    += stats.get("minutos") or 0
    totales["xg"] = round(totales["xg"], 2)
    totales["xa"] = round(totales["xa"], 2)

    # Partidos del equipo en la temporada
    partidos_local = (
        supabase.table("partidos")
        .select("id, jornada, fecha, estado, goles_local, goles_visitante, equipo_visitante, visitante:equipos!partidos_equipo_visitante_fkey(nombre)")
        .eq("equipo_local", equipo_id)
        .eq("temporada", temporada)
        .order("jornada")
        .execute()
    )
    partidos_visit = (
        supabase.table("partidos")
        .select("id, jornada, fecha, estado, goles_local, goles_visitante, equipo_local, local:equipos!partidos_equipo_local_fkey(nombre)")
        .eq("equipo_visitante", equipo_id)
        .eq("temporada", temporada)
        .order("jornada")
        .execute()
    )

    return {
        **equipo,
        "temporada":          temporada,
        "plantilla":          plantilla,
        "totales_temporada":  totales,
        "partidos_local":     partidos_local.data,
        "partidos_visitante": partidos_visit.data,
    }
