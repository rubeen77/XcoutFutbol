"""
Endpoints de jugadores:
  GET /jugadores          — lista con filtros opcionales
  GET /jugadores/ranking  — top N por métrica
  GET /jugadores/{id}     — perfil completo con estadísticas
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from database.supabase_client import supabase

router = APIRouter()

METRICAS_VALIDAS = {"goles", "asistencias", "xg", "xa", "ga_por_90", "valor_mercado", "minutos"}


# ---------------------------------------------------------------------------
# GET /jugadores
# ---------------------------------------------------------------------------

@router.get("")
def listar_jugadores(
    liga_id:           Optional[int]   = Query(None, description="ID de liga (1 = LaLiga)"),
    equipo_id:         Optional[int]   = Query(None, description="ID de equipo"),
    posicion:          Optional[str]   = Query(None, description="FW, MF, DF, GK"),
    min_goles:         Optional[int]   = Query(None, ge=0),
    max_valor_mercado: Optional[float] = Query(None, ge=0, description="Millones €"),
    temporada:         str             = Query("2526"),
    limit:             int             = Query(50, ge=1, le=1000),
    offset:            int             = Query(0, ge=0),
):
    # Partir desde estadisticas_jugador para garantizar que los stats están presentes
    q = (
        supabase.table("estadisticas_jugador")
        .select(
            "goles, asistencias, xg, xa, minutos, "
            "pases_completados, regates, presiones, recuperaciones, "
            "goles_por_90, asistencias_por_90, ga_por_90, "
            "jugadores(id, nombre, posicion, edad, nacionalidad, foto_url, valor_mercado, equipo_id, "
            "  equipos(id, nombre, liga_id))"
        )
        .eq("temporada", temporada)
    )

    if liga_id is not None:
        q = q.eq("liga_id", liga_id)
    if min_goles is not None:
        q = q.gte("goles", min_goles)

    res = q.execute()
    filas = res.data

    # Filtros post-fetch sobre campos de jugadores
    if equipo_id is not None or posicion is not None or max_valor_mercado is not None:
        filtradas = []
        for f in filas:
            j = f.get("jugadores") or {}
            if equipo_id is not None and j.get("equipo_id") != equipo_id:
                continue
            if posicion is not None and posicion.upper() not in (j.get("posicion") or "").upper():
                continue
            if max_valor_mercado is not None and (j.get("valor_mercado") or 0) > max_valor_mercado:
                continue
            filtradas.append(f)
        filas = filtradas

    # Paginación manual tras filtros
    total = len(filas)
    filas = filas[offset: offset + limit]

    # Aplanar: mover campos de jugadores al nivel raíz para respuesta más limpia
    jugadores = []
    for f in filas:
        j = f.pop("jugadores", {}) or {}
        jugadores.append({**j, "stats": f})

    return {"total": total, "jugadores": jugadores}


# ---------------------------------------------------------------------------
# GET /jugadores/ranking  (debe ir ANTES de /{id} para que no colisione)
# ---------------------------------------------------------------------------

@router.get("/ranking")
def ranking_jugadores(
    metrica:   str = Query("goles", description=f"Una de: {', '.join(sorted(METRICAS_VALIDAS))}"),
    temporada: str = Query("2526"),
    limit:     int = Query(20, ge=1, le=100),
    posicion:  Optional[str] = Query(None, description="FW, MF, DF, GK"),
):
    if metrica not in METRICAS_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"Métrica inválida. Usa una de: {', '.join(sorted(METRICAS_VALIDAS))}",
        )

    # valor_mercado está en jugadores, el resto en estadisticas_jugador
    if metrica == "valor_mercado":
        q = (
            supabase.table("jugadores")
            .select("id, nombre, posicion, edad, foto_url, valor_mercado, equipos(nombre)")
            .not_.is_("valor_mercado", "null")
            .order("valor_mercado", desc=True)
            .limit(limit)
        )
        if posicion:
            q = q.ilike("posicion", f"%{posicion}%")
        res = q.execute()
        return {"metrica": metrica, "temporada": temporada, "ranking": res.data}

    # Métricas en estadisticas_jugador
    q = (
        supabase.table("estadisticas_jugador")
        .select(
            f"{metrica}, jugador_id, temporada, liga_id, goles, asistencias, xg, xa, "
            f"minutos, goles_por_90, asistencias_por_90, ga_por_90, "
            f"jugadores(id, nombre, posicion, edad, foto_url, valor_mercado, equipos(nombre))"
        )
        .eq("temporada", temporada)
        .not_.is_(metrica, "null")
        .order(metrica, desc=True)
        .limit(limit)
    )
    res = q.execute()
    datos = res.data

    if posicion:
        pos_upper = posicion.upper()
        datos = [
            r for r in datos
            if pos_upper in ((r.get("jugadores") or {}).get("posicion") or "").upper()
        ]

    return {"metrica": metrica, "temporada": temporada, "ranking": datos}


# ---------------------------------------------------------------------------
# GET /jugadores/{id}
# ---------------------------------------------------------------------------

@router.get("/{jugador_id}")
def perfil_jugador(jugador_id: int):
    res = (
        supabase.table("jugadores")
        .select(
            "id, nombre, posicion, edad, nacionalidad, foto_url, valor_mercado, equipo_id, "
            "equipos(id, nombre, liga_id), "
            "estadisticas_jugador(temporada, liga_id, goles, asistencias, xg, xa, minutos, "
            "  pases_completados, regates, presiones, recuperaciones, "
            "  goles_por_90, asistencias_por_90, ga_por_90), "
            "valor_mercado_historia(temporada, valor)"
        )
        .eq("id", jugador_id)
        .single()
        .execute()
    )

    if not res.data:
        raise HTTPException(status_code=404, detail=f"Jugador {jugador_id} no encontrado")

    return res.data
