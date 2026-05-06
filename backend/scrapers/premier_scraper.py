"""
Premier League Scraper — jugadores, equipos, estadísticas, partidos y fotos

Fuentes:
  FBref (via soccerdata) → jugadores, equipos, estadísticas base
  FBref schedule         → partidos 2025/26
  Transfermarkt          → fotos y valor de mercado

Liga en Supabase: id=24 (ya existe)
Temporada: 2526

Uso:
  python backend/scrapers/premier_scraper.py
"""

import re
import sys
import time
import difflib
import logging
import unicodedata
from pathlib import Path
from typing import Optional

import pandas as pd
import soccerdata as sd
import cloudscraper
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
FBREF_LIGA   = "ENG-Premier League"
DB_LIGA_ID   = 24
DB_TEMPORADA = "2526"
TM_LIGA_CODE = "GB1"
TM_SEASON    = 2025
TM_BASE      = "https://www.transfermarkt.es"
REQUEST_DELAY = 2.0

CARGAR_PARTIDOS = True
CARGAR_TM       = True

JOIN_ON = ["player", "team"]

_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


# ─── Helpers genéricos ────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())

def _val(v):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v

def _int(v):
    v = _val(v)
    return int(v) if v is not None else None

def _float(v, decimals=2):
    v = _val(v)
    return round(float(v), decimals) if v is not None else None

def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        f"{a}__{b}" if b else a
        for a, b in (c if isinstance(c, tuple) else (c, "") for c in df.columns)
    ]
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 1 — FBref: jugadores y estadísticas
# ═══════════════════════════════════════════════════════════════════════════════

def load_fbref_stats() -> pd.DataFrame:
    log.info("[FBref] Cargando stats Premier League 2025/26...")
    fbref = sd.FBref(leagues=FBREF_LIGA, seasons=DB_TEMPORADA)

    log.info("  stat_type='standard'...")
    df_std  = _flatten(fbref.read_player_season_stats(stat_type="standard").reset_index())
    log.info("    %d filas", len(df_std))

    log.info("  stat_type='misc'...")
    df_misc = _flatten(fbref.read_player_season_stats(stat_type="misc").reset_index())
    log.info("    %d filas", len(df_misc))

    log.info("  stat_type='shooting'...")
    df_shot = _flatten(fbref.read_player_season_stats(stat_type="shooting").reset_index())
    log.info("    %d filas", len(df_shot))

    misc_cols = JOIN_ON + [c for c in ["Performance__TklW", "Performance__Int"] if c in df_misc.columns]
    shot_cols = JOIN_ON + [c for c in ["Standard__Sh", "Standard__SoT"] if c in df_shot.columns]

    merged = df_std.merge(df_misc[misc_cols],  on=JOIN_ON, how="left", suffixes=("", "_misc"))
    merged = merged.merge(df_shot[shot_cols],   on=JOIN_ON, how="left", suffixes=("", "_shot"))
    log.info("  Merged: %d filas, %d columnas.", len(merged), len(merged.columns))
    return merged


def upsert_equipos(equipos: list[str]) -> dict:
    log.info("[1/4] Upsertando %d equipos Premier League...", len(equipos))
    rows = [{"nombre": e, "liga_id": DB_LIGA_ID, "temporada": DB_TEMPORADA} for e in equipos]
    res = (
        supabase.table("equipos")
        .upsert(rows, on_conflict="nombre,liga_id,temporada")
        .execute()
    )
    mapping = {r["nombre"]: r["id"] for r in res.data}
    log.info("      %d equipos OK.", len(mapping))
    return mapping


def upsert_jugadores(df: pd.DataFrame, equipo_map: dict) -> dict:
    log.info("[2/4] Upsertando jugadores...")
    rows = []
    for _, row in df.iterrows():
        nombre        = _val(row.get("player"))
        equipo_nombre = _val(row.get("team"))
        if not nombre or not equipo_nombre:
            continue
        edad = None
        raw = _val(row.get("age"))
        if raw:
            try:
                edad = int(str(raw).split("-")[0])
            except (ValueError, IndexError):
                pass
        equipo_id = equipo_map.get(equipo_nombre)
        if not equipo_id:
            continue
        rows.append({
            "nombre":       nombre,
            "equipo_id":    equipo_id,
            "posicion":     _val(row.get("pos")),
            "edad":         edad,
            "nacionalidad": _val(row.get("nation")),
        })
    res = (
        supabase.table("jugadores")
        .upsert(rows, on_conflict="nombre,equipo_id")
        .execute()
    )
    mapping = {(r["nombre"], r["equipo_id"]): r["id"] for r in res.data}
    log.info("      %d jugadores OK.", len(mapping))
    return mapping


def upsert_estadisticas(df: pd.DataFrame, jugador_map: dict, equipo_map: dict) -> int:
    log.info("[3/4] Upsertando estadísticas...")
    rows = []
    skipped = 0

    for _, row in df.iterrows():
        nombre        = _val(row.get("player"))
        equipo_nombre = _val(row.get("team"))
        equipo_id     = equipo_map.get(equipo_nombre)
        jugador_id    = jugador_map.get((nombre, equipo_id))

        if not jugador_id:
            skipped += 1
            continue

        tklw = _int(row.get("Performance__TklW"))
        ints = _int(row.get("Performance__Int"))
        recuperaciones = None
        if tklw is not None or ints is not None:
            recuperaciones = (tklw or 0) + (ints or 0)

        rows.append({
            "jugador_id":         jugador_id,
            "temporada":          DB_TEMPORADA,
            "liga_id":            DB_LIGA_ID,
            "goles":              _int(row.get("Performance__Gls")),
            "asistencias":        _int(row.get("Performance__Ast")),
            "minutos":            _int(row.get("Playing Time__Min")),
            "goles_por_90":       _float(row.get("Per 90 Minutes__Gls"), 3),
            "asistencias_por_90": _float(row.get("Per 90 Minutes__Ast"), 3),
            "ga_por_90":          _float(row.get("Per 90 Minutes__G+A"), 3),
            "recuperaciones":     recuperaciones,
            "tiros_totales":      _int(row.get("Standard__Sh")),
            "tiros_a_puerta":     _int(row.get("Standard__SoT")),
            "xg":                 None,
            "xa":                 None,
            "pases_completados":  None,
            "regates":            None,
            "presiones":          None,
        })

    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    log.info("      %d estadísticas OK, %d skipped.", len(res.data), skipped)
    return len(res.data)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2 — FBref: partidos
# ═══════════════════════════════════════════════════════════════════════════════

_equipo_cache: dict[str, int] = {}
_equipo_keys:  list[str]      = []

PL_ALIASES: dict[str, str] = {
    "manchester utd": "manchester united",
    "man utd":        "manchester united",
    "man city":       "manchester city",
    "manchester city fc": "manchester city",
    "spurs":          "tottenham hotspur",
    "tottenham":      "tottenham hotspur",
    "wolves":         "wolverhampton wanderers",
    "wolverhampton":  "wolverhampton wanderers",
    "newcastle":      "newcastle united",
    "west ham":       "west ham united",
    "brighton":       "brighton & hove albion",
    "leicester":      "leicester city",
    "nottm forest":   "nottingham forest",
    "nottingham":     "nottingham forest",
    "nott'ham forest":"nottingham forest",
    "brentford":      "brentford",
    "fulham":         "fulham",
    "crystal palace": "crystal palace",
    "ipswich":        "ipswich town",
    "bournemouth":    "afc bournemouth",
    "aston villa":    "aston villa",
    "arsenal":        "arsenal",
    "chelsea":        "chelsea",
    "everton":        "everton",
    "southampton":    "southampton",
}


def _load_equipo_cache(equipo_map: dict):
    global _equipo_cache, _equipo_keys
    _equipo_cache = {_norm(nombre): eid for nombre, eid in equipo_map.items()}
    _equipo_keys  = list(_equipo_cache.keys())


def _resolve_equipo(nombre: str) -> Optional[int]:
    if not nombre:
        return None
    n = _norm(nombre)
    alias = PL_ALIASES.get(n)
    if alias and _norm(alias) in _equipo_cache:
        return _equipo_cache[_norm(alias)]
    if n in _equipo_cache:
        return _equipo_cache[n]
    for k, eid in _equipo_cache.items():
        if n in k or k in n:
            return eid
    close = difflib.get_close_matches(n, _equipo_keys, n=1, cutoff=0.70)
    if close:
        return _equipo_cache[close[0]]
    log.warning("  Equipo no resuelto: '%s'", nombre)
    return None


def _parse_score(score: str):
    if not score or not isinstance(score, str):
        return None, None
    for sep in ["–", "-", "−"]:
        if sep in score:
            parts = score.split(sep)
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()), int(parts[1].strip())
                except ValueError:
                    pass
    return None, None


def load_and_save_partidos(equipo_map: dict) -> int:
    log.info("[FBref Partidos] Descargando calendario Premier League...")
    fbref = sd.FBref(leagues=FBREF_LIGA, seasons=DB_TEMPORADA)
    df    = fbref.read_schedule().reset_index()
    log.info("  %d partidos en el calendario.", len(df))

    _load_equipo_cache(equipo_map)

    rows = []
    sin_score = 0
    for _, row in df.iterrows():
        home_id = _resolve_equipo(str(row.get("home_team") or ""))
        away_id = _resolve_equipo(str(row.get("away_team") or ""))
        if not home_id or not away_id:
            continue

        goles_l, goles_v = _parse_score(str(row.get("score")) if pd.notna(row.get("score")) else "")
        if goles_l is None:
            sin_score += 1

        fecha_iso = None
        fecha_raw = row.get("date")
        if pd.notna(fecha_raw):
            try:
                fecha_iso = pd.Timestamp(fecha_raw).isoformat()
            except Exception:
                pass

        rows.append({
            "liga_id":          DB_LIGA_ID,
            "temporada":        DB_TEMPORADA,
            "jornada":          int(row["week"]) if pd.notna(row.get("week")) else None,
            "fecha":            fecha_iso,
            "equipo_local":     home_id,
            "equipo_visitante": away_id,
            "goles_local":      goles_l,
            "goles_visitante":  goles_v,
            "xg_local":         None,
            "xg_visitante":     None,
            "estado":           "finalizado" if goles_l is not None else "programado",
        })

    log.info("  Con resultado: %d | Programados: %d", len(rows) - sin_score, sin_score)

    total = 0
    BATCH = 50
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i + BATCH]
        res = (
            supabase.table("partidos")
            .upsert(batch, on_conflict="liga_id,temporada,equipo_local,equipo_visitante,jornada")
            .execute()
        )
        total += len(res.data)
        log.info("  Lote %d/%d: %d OK", i // BATCH + 1, -(-len(rows) // BATCH), len(res.data))

    log.info("[4/4] Partidos guardados: %d", total)
    return total


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 3 — Transfermarkt: fotos y valor de mercado
# ═══════════════════════════════════════════════════════════════════════════════

def _get_html(url: str) -> Optional[BeautifulSoup]:
    try:
        r = _scraper.get(url, timeout=20)
        if r.status_code != 200:
            log.warning("  HTTP %d para %s", r.status_code, url)
            return None
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        log.warning("  Error en %s: %s", url, e)
        return None


def _parse_valor(text: str) -> Optional[float]:
    if not text or text.strip() in ("-", ""):
        return None
    text = text.strip().lower().replace(",", ".")
    m = re.search(r"([\d.]+)\s*(mill|mio|m\b)", text)
    if m:
        return round(float(m.group(1)), 2)
    m = re.search(r"([\d.]+)\s*(mil|k\b|tsd)", text)
    if m:
        return round(float(m.group(1)) / 1000, 3)
    return None


def get_tm_teams() -> list[dict]:
    log.info("[TM 1/3] Obteniendo equipos Premier League desde Transfermarkt...")
    url  = f"{TM_BASE}/premier-league/startseite/wettbewerb/{TM_LIGA_CODE}/saison_id/{TM_SEASON}"
    soup = _get_html(url)
    if not soup:
        log.warning("  No se pudo cargar TM. Saltando fotos.")
        return []

    teams, seen = [], set()
    for a in soup.select("td.hauptlink a[href*='/startseite/verein/']"):
        href = a.get("href", "")
        m    = re.search(r"(/[^/]+/startseite/verein/(\d+))", href)
        if not m:
            continue
        slug_path = m.group(1)
        team_id   = m.group(2)
        name      = a.text.strip()
        if team_id in seen:
            continue
        seen.add(team_id)
        teams.append({
            "name":      name,
            "tm_id":     team_id,
            "kader_url": f"{TM_BASE}{slug_path.replace('/startseite/', '/kader/')}/saison_id/{TM_SEASON}",
        })

    log.info("      %d equipos TM.", len(teams))
    return teams


def scrape_tm_squads(teams: list[dict]) -> pd.DataFrame:
    log.info("[TM 2/3] Scraping plantillas TM (%d equipos)...", len(teams))
    all_players = []
    for i, team in enumerate(teams, 1):
        soup = _get_html(team["kader_url"])
        if not soup:
            continue
        for row in soup.select("table.items tbody tr.odd, table.items tbody tr.even"):
            name_el = row.select_one("td.hauptlink a")
            img_el  = row.select_one("img.bilderrahmen-fixed")
            val_el  = row.select_one("td.rechts.hauptlink")
            if not name_el:
                continue
            name  = name_el.text.strip()
            foto  = None
            if img_el:
                foto = img_el.get("data-src") or img_el.get("src")
                if foto:
                    foto = foto.replace("/medium/", "/big/")
            all_players.append({
                "nombre":        name,
                "nombre_norm":   _norm(name),
                "equipo_tm":     team["name"],
                "foto_url":      foto,
                "valor_mercado": _parse_valor(val_el.text if val_el else ""),
            })
        log.info("      [%d/%d] %s — %d jugadores", i, len(teams), team["name"],
                 sum(1 for p in all_players if p["equipo_tm"] == team["name"]))
        if i < len(teams):
            time.sleep(REQUEST_DELAY)

    df = pd.DataFrame(all_players)
    log.info("      Total TM: %d jugadores.", len(df))
    return df


def apply_tm_data(df_tm: pd.DataFrame, equipo_map: dict):
    log.info("[TM 3/3] Cruzando con Supabase y actualizando fotos/valores...")

    res = (
        supabase.table("jugadores")
        .select("id, nombre, equipo_id")
        .in_("equipo_id", list(equipo_map.values()))
        .execute()
    )
    supa_rows = res.data

    # Índices de cruce
    full_idx: dict[tuple, int]   = {}
    name_idx: dict[str, int]     = {}
    equipo_norm_map = {_norm(nombre): eid for nombre, eid in equipo_map.items()}

    for _, row in df_tm.iterrows():
        e_norm = _norm(row["equipo_tm"])
        full_idx[(row["nombre_norm"], e_norm)] = _
        name_idx.setdefault(row["nombre_norm"], _)

    updates_jug     = []
    updates_hist    = []

    for r in supa_rows:
        n     = _norm(r["nombre"])
        eid   = r["equipo_id"]
        enom  = next((k for k, v in equipo_norm_map.items() if v == eid), "")
        idx   = full_idx.get((n, _norm(enom)))
        if idx is None:
            idx = name_idx.get(n)
        if idx is None:
            continue

        tm_row = df_tm.iloc[idx]
        foto   = tm_row.get("foto_url")
        valor  = tm_row.get("valor_mercado")

        if not foto and not valor:
            continue
        upd = {"id": r["id"], "nombre": r["nombre"], "equipo_id": r["equipo_id"]}
        if foto:
            upd["foto_url"] = foto
        if valor:
            upd["valor_mercado"] = valor
        updates_jug.append(upd)
        if valor:
            updates_hist.append({
                "jugador_id": r["id"],
                "temporada":  DB_TEMPORADA,
                "valor":      valor,
            })

    # Upsert jugadores (on_conflict por id)
    if updates_jug:
        BATCH = 100
        for i in range(0, len(updates_jug), BATCH):
            supabase.table("jugadores") \
                .upsert(updates_jug[i:i+BATCH], on_conflict="id") \
                .execute()
        log.info("      %d jugadores actualizados con foto/valor.", len(updates_jug))

    # Upsert historial
    if updates_hist:
        supabase.table("valor_mercado_historia") \
            .upsert(updates_hist, on_conflict="jugador_id,temporada") \
            .execute()
        log.info("      %d entradas valor_mercado_historia.", len(updates_hist))


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRYPOINT
# ═══════════════════════════════════════════════════════════════════════════════

def run():
    log.info("=" * 62)
    log.info(" Premier League Scraper — temporada %s", DB_TEMPORADA)
    log.info(" liga_id=%d", DB_LIGA_ID)
    log.info("=" * 62)

    # ── FBref: stats ──────────────────────────────────────────────────────────
    df         = load_fbref_stats()
    equipos    = sorted(df["team"].dropna().unique().tolist())
    equipo_map = upsert_equipos(equipos)
    jugador_map = upsert_jugadores(df, equipo_map)
    stats_ok    = upsert_estadisticas(df, jugador_map, equipo_map)

    # ── FBref: partidos ───────────────────────────────────────────────────────
    partidos_ok = 0
    if CARGAR_PARTIDOS:
        log.info("")
        partidos_ok = load_and_save_partidos(equipo_map)

    # ── Transfermarkt: fotos y valores ────────────────────────────────────────
    if CARGAR_TM:
        log.info("")
        tm_teams = get_tm_teams()
        if tm_teams:
            df_tm = scrape_tm_squads(tm_teams)
            apply_tm_data(df_tm, equipo_map)

    # ── Resumen ───────────────────────────────────────────────────────────────
    log.info("")
    log.info("=" * 62)
    log.info(" RESUMEN FINAL")
    log.info("  Equipos insertados  : %d", len(equipo_map))
    log.info("  Jugadores insertados: %d", len(jugador_map))
    log.info("  Estadísticas        : %d", stats_ok)
    log.info("  Partidos            : %d", partidos_ok)
    log.info("")
    log.info("  PENDIENTE:")
    log.info("    xG/xA   -> adaptar understat_scraper.py para ENG-Premier-League")
    log.info("    regates -> adaptar sofascore_stats_scraper.py para PL (tournamentId)")
    log.info("    porteros-> adaptar porteros_scraper.py para PL (season_id Sofascore)")
    log.info("=" * 62)


if __name__ == "__main__":
    run()
