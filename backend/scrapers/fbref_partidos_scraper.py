"""
FBref Partidos Scraper — Resultados de LaLiga 2025/26 via soccerdata

Fuente: FBref (a través de soccerdata), que proporciona el calendario completo
con resultados de todos los partidos jugados.

Inserta/actualiza en la tabla 'partidos' de Supabase.
Matching de equipos: nombre normalizado contra la tabla 'equipos'.

Uso:
  python fbref_partidos_scraper.py
"""

import sys
import difflib
import logging
import unicodedata
from pathlib import Path

import pandas as pd
import soccerdata as sd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

FBREF_LIGA   = "ESP-La Liga"
DB_LIGA_ID   = 1
DB_TEMPORADA = "2526"

# Aliases: nombre FBref normalizado → nombre en DB normalizado (temporada 2526)
FBREF_ALIASES: dict[str, str] = {
    "ath bilbao":      "athletic club",
    "athletic bilbao": "athletic club",
    "betis":           "real betis",
    "sociedad":        "real sociedad",
}


# ── Normalización ─────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())


# ── Cache de equipos ──────────────────────────────────────────────────────────

_cache: dict[str, int] = {}
_keys:  list[str]      = []


def _load_cache():
    global _cache, _keys
    if _cache:
        return
    res = (
        supabase.table("equipos")
        .select("id, nombre")
        .eq("liga_id", DB_LIGA_ID)
        .eq("temporada", DB_TEMPORADA)
        .execute()
    )
    for r in res.data:
        k = _norm(r["nombre"])
        if k:
            _cache[k] = r["id"]
    _keys = list(_cache.keys())
    log.info("Cache equipos: %d entradas.", len(_cache))
    for k in sorted(_keys):
        log.debug("  '%s' → %d", k, _cache[k])


def _resolve(nombre: str) -> int | None:
    if not nombre:
        return None
    _load_cache()
    n = _norm(nombre)

    # 1. Alias
    alias = FBREF_ALIASES.get(n)
    if alias and alias in _cache:
        return _cache[alias]

    # 2. Exacto
    if n in _cache:
        return _cache[n]

    # 3. La clave DB contiene el nombre FBref o viceversa
    for k, eid in _cache.items():
        if n in k or k in n:
            return eid

    # 4. difflib
    close = difflib.get_close_matches(n, _keys, n=1, cutoff=0.70)
    if close:
        log.debug("  difflib '%s' → '%s'", n, close[0])
        return _cache[close[0]]

    log.warning("  [!] Equipo no resuelto: '%s'", nombre)
    return None


# ── Parse del score FBref ("2–1") ─────────────────────────────────────────────

def _parse_score(score: str):
    """Devuelve (goles_local, goles_visitante) o (None, None) si no hay resultado."""
    if not score or not isinstance(score, str):
        return None, None
    # FBref usa el guión "–" (en dash) o "-"
    for sep in ["–", "-", "−"]:
        if sep in score:
            parts = score.split(sep)
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()), int(parts[1].strip())
                except ValueError:
                    pass
    return None, None


# ── Carga y guardado ──────────────────────────────────────────────────────────

def load_schedule() -> pd.DataFrame:
    log.info("Descargando calendario LaLiga 2025/26 desde FBref...")
    fbref = sd.FBref(leagues=FBREF_LIGA, seasons=DB_TEMPORADA)
    df = fbref.read_schedule().reset_index()
    log.info("Total partidos en calendario: %d", len(df))
    return df


def build_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    sin_equipo = []
    sin_score  = 0

    for _, row in df.iterrows():
        home_nombre = row.get("home_team") or ""
        away_nombre = row.get("away_team") or ""
        score       = row.get("score")
        jornada     = row.get("week")
        fecha_raw   = row.get("date")
        game_id     = row.get("game_id")

        home_id = _resolve(str(home_nombre))
        away_id = _resolve(str(away_nombre))

        if home_id is None:
            sin_equipo.append(f"local: '{home_nombre}'")
        if away_id is None:
            sin_equipo.append(f"visit: '{away_nombre}'")

        goles_l, goles_v = _parse_score(str(score) if pd.notna(score) else "")
        if goles_l is None:
            sin_score += 1

        # Fecha ISO
        fecha_iso = None
        if pd.notna(fecha_raw):
            try:
                fecha_iso = pd.Timestamp(fecha_raw).isoformat()
            except Exception:
                pass

        estado = "finalizado" if goles_l is not None else "programado"

        rows.append({
            "liga_id":          DB_LIGA_ID,
            "temporada":        DB_TEMPORADA,
            "jornada":          int(jornada) if pd.notna(jornada) else None,
            "fecha":            fecha_iso,
            "equipo_local":     home_id,
            "equipo_visitante": away_id,
            "goles_local":      goles_l,
            "goles_visitante":  goles_v,
            "xg_local":         None,
            "xg_visitante":     None,
            "estado":           estado,
            # game_id de FBref como clave de upsert (string)
            "fbref_game_id":    str(game_id) if pd.notna(game_id) else None,
        })

    log.info("Partidos con resultado: %d", len(rows) - sin_score)
    log.info("Partidos pendientes:    %d", sin_score)
    if sin_equipo:
        log.warning("Equipos no resueltos (%d):", len(sin_equipo))
        for s in sorted(set(sin_equipo)):
            log.warning("  %s", s)

    return rows


def save_rows(rows: list[dict]) -> int:
    if not rows:
        return 0

    # Supabase no tiene 'fbref_game_id' como columna necesariamente —
    # usamos on_conflict por (liga_id, temporada, jornada, equipo_local, equipo_visitante)
    # Para ello filtramos primero filas con equipos resueltos.
    validos = [r for r in rows if r["equipo_local"] and r["equipo_visitante"]]
    nulos   = len(rows) - len(validos)

    if nulos:
        log.warning("%d partidos descartados por equipos NULL.", nulos)

    # Eliminar campo fbref_game_id si la columna no existe en la tabla
    for r in validos:
        r.pop("fbref_game_id", None)

    # Upsert por (liga_id, temporada, equipo_local, equipo_visitante, jornada)
    BATCH = 50
    total = 0
    for i in range(0, len(validos), BATCH):
        batch = validos[i:i + BATCH]
        res = (
            supabase.table("partidos")
            .upsert(
                batch,
                on_conflict="liga_id,temporada,equipo_local,equipo_visitante,jornada",
            )
            .execute()
        )
        total += len(res.data)
        log.info("  Lote %d/%d: %d insertados/actualizados", i // BATCH + 1, -(-len(validos) // BATCH), len(res.data))

    return total


# ── Entrypoint ────────────────────────────────────────────────────────────────

def run():
    log.info("=" * 60)
    log.info(" FBref Partidos — LaLiga %s", DB_TEMPORADA)
    log.info("=" * 60)

    _load_cache()

    # Estado inicial
    antes = supabase.table("partidos").select("id", count="exact").execute()
    log.info("Partidos en DB antes: %d", antes.count)

    df   = load_schedule()
    rows = build_rows(df)
    n    = save_rows(rows)

    # Estado final
    despues = supabase.table("partidos").select("id", count="exact").execute()
    log.info("")
    log.info("=" * 60)
    log.info(" RESUMEN")
    log.info("  Partidos en calendario FBref : %d", len(rows))
    log.info("  Guardados/actualizados       : %d", n)
    log.info("  Partidos en DB antes         : %d", antes.count)
    log.info("  Partidos en DB después       : %d", despues.count)
    log.info("=" * 60)


if __name__ == "__main__":
    run()
