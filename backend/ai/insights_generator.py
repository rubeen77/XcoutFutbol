"""
Generador de análisis de jornada con Claude API.

Flujo:
  1. Consultar Supabase: resultados jornada + top goleadores + clasificación
  2. Construir prompt periodístico en español
  3. Llamar a Claude (claude-sonnet-4-20250514)
  4. Guardar en tabla analisis_jornada (upsert)
  5. Devolver el registro guardado
"""

import os
import logging
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

log = logging.getLogger(__name__)

LIGA_NOMBRES = {1: "LaLiga", 24: "Premier League", 25: "Bundesliga"}

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise EnvironmentError("ANTHROPIC_API_KEY no está definida en backend/.env")
        _client = anthropic.Anthropic(api_key=key)
    return _client


# ---------------------------------------------------------------------------
# Consultas a Supabase
# ---------------------------------------------------------------------------

def _datos_jornada(liga_id: int, jornada: int, temporada: str) -> dict:
    # Resultados de la jornada
    p_res = (
        supabase.table("partidos")
        .select(
            "goles_local, goles_visitante, "
            "local:equipos!partidos_equipo_local_fkey(nombre), "
            "visitante:equipos!partidos_equipo_visitante_fkey(nombre)"
        )
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .eq("jornada", jornada)
        .eq("estado", "finalizado")
        .execute()
    )
    partidos = p_res.data or []

    # Top 5 goleadores de la temporada
    g_res = (
        supabase.table("estadisticas_jugador")
        .select("goles, jugadores(nombre, equipos(nombre))")
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .not_.is_("goles", "null")
        .order("goles", desc=True)
        .limit(5)
        .execute()
    )
    goleadores = []
    for r in (g_res.data or []):
        j  = r.get("jugadores") or {}
        eq = (j.get("equipos") or {})
        goleadores.append({
            "nombre": j.get("nombre", ""),
            "equipo": eq.get("nombre", ""),
            "goles":  r.get("goles", 0),
        })

    COLS_EQ = "nombre, puntos, posicion_clasificacion"

    # Top 5 clasificación
    top_res = (
        supabase.table("equipos")
        .select(COLS_EQ)
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .not_.is_("posicion_clasificacion", "null")
        .order("posicion_clasificacion", desc=False)
        .limit(5)
        .execute()
    )

    # Zona descenso (último 3 por posición)
    desc_res = (
        supabase.table("equipos")
        .select(COLS_EQ)
        .eq("liga_id", liga_id)
        .eq("temporada", temporada)
        .not_.is_("posicion_clasificacion", "null")
        .order("posicion_clasificacion", desc=True)
        .limit(3)
        .execute()
    )
    descenso = list(reversed(desc_res.data or []))

    return {
        "partidos":      partidos,
        "goleadores":    goleadores,
        "clasificacion": top_res.data or [],
        "descenso":      descenso,
    }


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def _construir_prompt(liga_id: int, jornada: int, datos: dict) -> str:
    liga_nombre = LIGA_NOMBRES.get(liga_id, f"Liga {liga_id}")

    def fmt_partidos():
        if not datos["partidos"]:
            return "  (Sin datos de partidos finalizados)"
        lines = []
        for p in datos["partidos"]:
            loc = (p.get("local")     or {}).get("nombre", "?")
            vis = (p.get("visitante") or {}).get("nombre", "?")
            lines.append(f"  - {loc} {p.get('goles_local', 0)}-{p.get('goles_visitante', 0)} {vis}")
        return "\n".join(lines)

    def fmt_goleadores():
        if not datos["goleadores"]:
            return "  (Sin datos)"
        return "\n".join(
            f"  {i+1}. {j['nombre']} ({j['equipo']}): {j['goles']} goles"
            for i, j in enumerate(datos["goleadores"])
        )

    def fmt_tabla(equipos):
        if not equipos:
            return "  (Sin datos)"
        lines = []
        for eq in equipos:
            pos = eq.get("posicion_clasificacion", "?")
            pts = eq.get("puntos", 0)
            lines.append(f"  {pos}. {eq['nombre']} — {pts} pts")
        return "\n".join(lines)

    return f"""Eres un periodista deportivo experto en fútbol. Analiza la jornada {jornada} de {liga_nombre}.

DATOS JORNADA {jornada}:

Resultados:
{fmt_partidos()}

Top goleadores temporada:
{fmt_goleadores()}

Clasificación (top 5):
{fmt_tabla(datos["clasificacion"])}

Zona de descenso:
{fmt_tabla(datos["descenso"])}

FORMATO DE RESPUESTA:
- Primera línea: "TITULAR: " seguido de un titular llamativo (máx 10 palabras)
- Luego exactamente 3 párrafos separados por línea en blanco
- Párrafo 1: resultado(s) más destacado(s) de la jornada
- Párrafo 2: situación de los goleadores y jugadores en forma
- Párrafo 3: lectura de la clasificación y la zona de descenso
- Tono periodístico, directo, con energía. Sin clichés. Sin markdown."""


# ---------------------------------------------------------------------------
# Parser de respuesta
# ---------------------------------------------------------------------------

def _parsear(texto: str) -> tuple[str, str]:
    lines  = texto.strip().splitlines()
    titulo = ""
    resto  = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("TITULAR:") and not titulo:
            titulo = stripped.removeprefix("TITULAR:").strip()
        else:
            resto.append(line)
    # Fallback si Claude no siguió el formato
    if not titulo and resto:
        titulo = resto.pop(0).strip()
    contenido = "\n".join(resto).strip()
    return titulo, contenido


# ---------------------------------------------------------------------------
# Función pública
# ---------------------------------------------------------------------------

def generar_analisis_jornada(liga_id: int, jornada: int, temporada: str = "2526") -> dict:
    """
    Devuelve el análisis de una jornada. Si ya existe en Supabase lo recupera;
    si no, lo genera con Claude, lo guarda y lo devuelve.
    """
    # 1. Caché: ¿ya existe?
    cache = (
        supabase.table("analisis_jornada")
        .select("*")
        .eq("liga_id",   liga_id)
        .eq("temporada", temporada)
        .eq("jornada",   jornada)
        .limit(1)
        .execute()
    )
    if cache.data:
        log.info("analisis_jornada: caché hit (liga=%d j=%d)", liga_id, jornada)
        return cache.data[0]

    # 2. Datos de Supabase
    log.info("analisis_jornada: generando con Claude (liga=%d j=%d)…", liga_id, jornada)
    datos  = _datos_jornada(liga_id, jornada, temporada)
    prompt = _construir_prompt(liga_id, jornada, datos)

    # 3. Claude API
    client  = _get_client()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    titulo, contenido = _parsear(message.content[0].text)

    # 4. Guardar
    ahora = datetime.now(timezone.utc).isoformat()
    row   = {
        "liga_id":     liga_id,
        "temporada":   temporada,
        "jornada":     jornada,
        "titulo":      titulo,
        "contenido":   contenido,
        "generado_en": ahora,
    }
    res     = (
        supabase.table("analisis_jornada")
        .upsert(row, on_conflict="liga_id,temporada,jornada")
        .execute()
    )
    guardado = res.data[0] if res.data else {**row, "id": None}
    log.info("analisis_jornada: guardado '%s'", titulo)
    return guardado


def ultima_jornada_finalizada(liga_id: int, temporada: str = "2526") -> int | None:
    """Devuelve el número de la última jornada con al menos un partido finalizado."""
    res = (
        supabase.table("partidos")
        .select("jornada")
        .eq("liga_id",   liga_id)
        .eq("temporada", temporada)
        .eq("estado",    "finalizado")
        .order("jornada", desc=True)
        .limit(1)
        .execute()
    )
    if res.data:
        return res.data[0]["jornada"]
    return None
