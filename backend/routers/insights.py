"""
GET /insights/rankings      — top 5 por varias métricas
GET /insights/datos-curiosos — curiosidades calculadas desde los datos
GET /insights/quiz           — jugador aleatorio para adivinar
"""

import random
from fastapi import APIRouter, Query
from database.supabase_client import supabase

router = APIRouter()

STATS_SELECT = (
    "jugador_id, goles, asistencias, xg, xa, minutos, "
    "goles_por_90, asistencias_por_90, regates, recuperaciones, "
    "jugadores(id, nombre, posicion, foto_url, equipo_id, equipos(nombre))"
)


def _fmt(s):
    """Convierte una fila de estadisticas_jugador a shape plano."""
    j  = s.get("jugadores") or {}
    eq = (j.get("equipos") or {})
    goles = s.get("goles") or 0
    xg    = float(s.get("xg") or 0)
    return {
        "id":            j.get("id"),
        "nombre":        j.get("nombre", ""),
        "equipo":        eq.get("nombre", ""),
        "posicion":      j.get("posicion", ""),
        "foto_url":      j.get("foto_url"),
        "goles":         goles,
        "asistencias":   s.get("asistencias") or 0,
        "xg":            round(xg, 2),
        "xa":            round(float(s.get("xa") or 0), 2),
        "minutos":       s.get("minutos") or 0,
        "goles_por_90":  round(float(s.get("goles_por_90") or 0), 2),
        "regates":       round(float(s.get("regates") or 0), 2),
        "recuperaciones":round(float(s.get("recuperaciones") or 0), 2),
        "sobre_xg":      round(goles - xg, 2),
    }


def _top(lista, key, n=5, min_minutos=0):
    filtrado = [j for j in lista if j["minutos"] >= min_minutos and j.get(key) is not None]
    return sorted(filtrado, key=lambda x: x[key], reverse=True)[:n]


# ---------------------------------------------------------------------------
# GET /insights/rankings
# ---------------------------------------------------------------------------

@router.get("/rankings")
def rankings(temporada: str = Query("2526")):
    res = (
        supabase.table("estadisticas_jugador")
        .select(STATS_SELECT)
        .eq("temporada", temporada)
        .execute()
    )
    jugadores = [_fmt(s) for s in (res.data or []) if (s.get("jugadores") or {}).get("nombre")]

    return {
        "goleadores":     _top(jugadores, "goles"),
        "asistentes":     _top(jugadores, "asistencias"),
        "sobre_xg":       _top(jugadores, "sobre_xg"),
        "regates":        _top(jugadores, "regates"),
        "recuperaciones": _top(jugadores, "recuperaciones"),
        "g90":            _top(jugadores, "goles_por_90", min_minutos=500),
    }


# ---------------------------------------------------------------------------
# GET /insights/datos-curiosos
# ---------------------------------------------------------------------------

@router.get("/datos-curiosos")
def datos_curiosos(temporada: str = Query("2526")):
    # ── Jugadores ──
    res = (
        supabase.table("estadisticas_jugador")
        .select("jugador_id, goles, xg, minutos, jugadores(nombre, equipos(nombre))")
        .eq("temporada", temporada)
        .execute()
    )
    jugadores = []
    for s in (res.data or []):
        j  = s.get("jugadores") or {}
        eq = (j.get("equipos") or {})
        goles = s.get("goles") or 0
        xg    = float(s.get("xg") or 0)
        minutos = s.get("minutos") or 0
        jugadores.append({
            "nombre":   j.get("nombre", ""),
            "equipo":   eq.get("nombre", ""),
            "goles":    goles,
            "xg":       xg,
            "sobre_xg": goles - xg,
            "bajo_xg":  xg - goles,
            "minutos":  minutos,
        })

    with_mins = [j for j in jugadores if j["minutos"] >= 500]
    mejor_sobre = max(with_mins, key=lambda j: j["sobre_xg"]) if with_mins else None
    peor_bajo   = max(
        [j for j in with_mins if j["xg"] > 0],
        key=lambda j: j["bajo_xg"]
    ) if with_mins else None

    # ── Partidos ──
    part_res = (
        supabase.table("partidos")
        .select("jornada, goles_local, goles_visitante, equipo_local, equipo_visitante")
        .eq("temporada", temporada)
        .eq("estado", "finalizado")
        .execute()
    )
    partidos = part_res.data or []

    goles_x_jornada: dict = {}
    goles_casa: dict  = {}
    goles_fuera: dict = {}

    for p in partidos:
        j   = p.get("jornada")
        gl  = p.get("goles_local")  or 0
        gv  = p.get("goles_visitante") or 0
        eid_l = p.get("equipo_local")
        eid_v = p.get("equipo_visitante")

        if j is not None:
            goles_x_jornada[j] = goles_x_jornada.get(j, 0) + gl + gv
        if eid_l is not None:
            goles_casa[eid_l]  = goles_casa.get(eid_l, 0) + gl
        if eid_v is not None:
            goles_fuera[eid_v] = goles_fuera.get(eid_v, 0) + gv

    max_jornada     = max(goles_x_jornada, key=goles_x_jornada.get) if goles_x_jornada else None
    max_casa_id     = max(goles_casa,      key=goles_casa.get)       if goles_casa  else None
    max_fuera_id    = max(goles_fuera,     key=goles_fuera.get)      if goles_fuera else None

    # Nombres de equipos
    ids_needed = [x for x in [max_casa_id, max_fuera_id] if x is not None]
    eq_names: dict = {}
    if ids_needed:
        eq_res = (
            supabase.table("equipos")
            .select("id, nombre")
            .in_("id", ids_needed)
            .execute()
        )
        eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}

    return {
        "mejor_sobre_xg": {
            "jugador":    mejor_sobre["nombre"],
            "equipo":     mejor_sobre["equipo"],
            "goles":      mejor_sobre["goles"],
            "xg":         round(mejor_sobre["xg"], 2),
            "diferencia": round(mejor_sobre["sobre_xg"], 2),
        } if mejor_sobre else None,

        "peor_xg": {
            "jugador":    peor_bajo["nombre"],
            "equipo":     peor_bajo["equipo"],
            "goles":      peor_bajo["goles"],
            "xg":         round(peor_bajo["xg"], 2),
            "diferencia": round(peor_bajo["bajo_xg"], 2),
        } if peor_bajo else None,

        "jornada_max_goles": {
            "jornada": max_jornada,
            "goles":   goles_x_jornada.get(max_jornada),
        } if max_jornada else None,

        "mejor_equipo_casa": {
            "nombre": eq_names.get(max_casa_id, ""),
            "goles":  goles_casa.get(max_casa_id),
        } if max_casa_id else None,

        "mejor_equipo_fuera": {
            "nombre": eq_names.get(max_fuera_id, ""),
            "goles":  goles_fuera.get(max_fuera_id),
        } if max_fuera_id else None,
    }


# ---------------------------------------------------------------------------
# GET /insights/quiz
# ---------------------------------------------------------------------------

@router.get("/quiz")
def quiz(temporada: str = Query("2526")):
    res = (
        supabase.table("estadisticas_jugador")
        .select(
            "jugador_id, goles, asistencias, xg, minutos, goles_por_90, "
            "recuperaciones, regates, pases_completados, "
            "jugadores(id, nombre, posicion, foto_url, equipos(nombre))"
        )
        .eq("temporada", temporada)
        .execute()
    )

    candidatos = [
        s for s in (res.data or [])
        if (s.get("jugadores") or {}).get("nombre")
        and (s.get("minutos") or 0) >= 900
    ]

    if len(candidatos) < 4:
        return {"error": "No hay suficientes jugadores"}

    elegido     = random.choice(candidatos)
    elegido_pos = (elegido.get("jugadores") or {}).get("posicion", "")

    # Distractores de la misma posición para que la posición sea pista, no descarte
    misma_pos = [
        s for s in candidatos
        if s["jugador_id"] != elegido["jugador_id"]
        and (s.get("jugadores") or {}).get("posicion", "") == elegido_pos
    ]
    # Fallback: si no hay 3 de la misma posición, completar con el resto
    if len(misma_pos) < 3:
        otros = [s for s in candidatos if s["jugador_id"] != elegido["jugador_id"] and s not in misma_pos]
        random.shuffle(otros)
        misma_pos = misma_pos + otros
    distractores = random.sample(misma_pos, min(3, len(misma_pos)))

    j  = elegido["jugadores"]
    eq = (j.get("equipos") or {})

    opciones = [j["nombre"]] + [s["jugadores"]["nombre"] for s in distractores]
    random.shuffle(opciones)

    return {
        "jugador_id": j.get("id"),
        "nombre":     j.get("nombre"),
        "posicion":   j.get("posicion"),
        "equipo":     eq.get("nombre", ""),
        "foto_url":   j.get("foto_url"),
        "stats": {
            "goles":              elegido.get("goles") or 0,
            "asistencias":        elegido.get("asistencias") or 0,
            "xg":                 round(float(elegido.get("xg") or 0), 2),
            "minutos":            elegido.get("minutos") or 0,
            "goles_por_90":       round(float(elegido.get("goles_por_90") or 0), 2),
            "recuperaciones":     round(float(elegido.get("recuperaciones") or 0), 1),
            "regates":            round(float(elegido.get("regates") or 0), 1),
            "pases_completados":  round(float(elegido.get("pases_completados") or 0), 1),
        },
        "opciones": opciones,
    }
