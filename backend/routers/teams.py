"""
Endpoints de equipos:
  GET /equipos              — lista de equipos de una liga (con top 3 goleadores)
  GET /equipos/{id}/detalle — página detalle: equipo + clasificación liga + plantilla
  GET /equipos/{id}         — perfil legacy con partidos y totales
"""

from fastapi import APIRouter, HTTPException, Query
from database.supabase_client import supabase

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /equipos
# ---------------------------------------------------------------------------

@router.get("")
def listar_equipos(
    liga_id:   int = Query(1),
    temporada: str = Query("2526"),
):
    res = (
        supabase.table("equipos")
        .select("id, nombre, liga_id, temporada, posicion_clasificacion, puntos, escudo_url, ligas(nombre, pais)")
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .order("posicion_clasificacion", desc=False)
        .limit(100)
        .execute()
    )
    equipos = res.data or []

    # Top 3 goleadores por equipo en una sola query
    gol_res = (
        supabase.table("estadisticas_jugador")
        .select("goles, jugadores(id, nombre, foto_url, equipo_id)")
        .eq("temporada", temporada)
        .eq("liga_id", liga_id)
        .gte("goles", 1)
        .order("goles", desc=True)
        .limit(500)
        .execute()
    )

    top_gol: dict[int, list] = {}
    for row in (gol_res.data or []):
        j   = row.get("jugadores") or {}
        eid = j.get("equipo_id")
        if not eid:
            continue
        lst = top_gol.setdefault(eid, [])
        if len(lst) < 3:
            lst.append({
                "id":       j.get("id"),
                "nombre":   j.get("nombre"),
                "goles":    row.get("goles") or 0,
                "foto_url": j.get("foto_url"),
            })

    for equipo in equipos:
        equipo["top_goleadores"] = top_gol.get(equipo["id"], [])

    return {"total": len(equipos), "equipos": equipos}


# ---------------------------------------------------------------------------
# GET /equipos/{id}/detalle  (más específico — debe ir ANTES de /{id})
# ---------------------------------------------------------------------------

@router.get("/{equipo_id}/detalle")
def detalle_equipo_pagina(equipo_id: int, temporada: str = Query("2526")):
    eq_res = (
        supabase.table("equipos")
        .select("id, nombre, liga_id, temporada, posicion_clasificacion, puntos, escudo_url, ligas(nombre, pais)")
        .eq("id", equipo_id)
        .single()
        .execute()
    )
    if not eq_res.data:
        raise HTTPException(status_code=404, detail=f"Equipo {equipo_id} no encontrado")

    equipo  = eq_res.data
    liga_id = equipo["liga_id"]

    # Clasificación completa de la liga desde Supabase (actualizada por el scraper)
    clasif_res = (
        supabase.table("equipos")
        .select("id, nombre, posicion_clasificacion, puntos, escudo_url")
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .order("posicion_clasificacion", desc=False)
        .limit(30)
        .execute()
    )
    clasif = clasif_res.data or []

    # Plantilla con stats
    plantilla_res = (
        supabase.table("jugadores")
        .select(
            "id, nombre, posicion, edad, valor_mercado, foto_url, "
            "estadisticas_jugador(temporada, goles, asistencias, xg, xa, minutos, "
            "  goles_por_90, asistencias_por_90, ga_por_90)"
        )
        .eq("equipo_id", equipo_id)
        .eq("estadisticas_jugador.temporada", temporada)
        .execute()
    )

    return {
        "equipo":        equipo,
        "clasificacion": clasif,
        "plantilla":     plantilla_res.data or [],
    }


# ---------------------------------------------------------------------------
# GET /equipos/{id}  (legacy — con partidos y totales)
# ---------------------------------------------------------------------------

@router.get("/{equipo_id}")
def perfil_equipo(equipo_id: int, temporada: str = Query("2526")):
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

    totales = {"goles": 0, "asistencias": 0, "xg": 0.0, "xa": 0.0, "minutos": 0}
    for j in plantilla:
        stats = (j.get("estadisticas_jugador") or [{}])[0]
        totales["goles"]       += stats.get("goles") or 0
        totales["asistencias"] += stats.get("asistencias") or 0
        totales["xg"]          += stats.get("xg") or 0.0
        totales["xa"]          += stats.get("xa") or 0.0
        totales["minutos"]     += stats.get("minutos") or 0
    totales["xg"] = round(totales["xg"], 2)
    totales["xa"] = round(totales["xa"], 2)

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
