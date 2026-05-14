"""
FBref Serie A Scraper — Serie A 2025/26 (liga_id=26)

Carga desde cero la Serie A en Supabase en 6 fases:
  1. standard   -> equipos + jugadores (upsert) + estadisticas basicas (INSERT)
  2. keeper     -> portero_paradas, portero_goles_encajados, portero_paradas_pct (UPDATE)
  3. shooting   -> xg como valor inicial desde FBref (UPDATE; Understat lo sobreescribe)
  4. misc       -> recuperaciones, intercepciones, entradas (UPDATE)
  5. Understat  -> xg, xa definitivos (UPDATE)
  6. schedule   -> partidos (upsert)

Uso (desde backend/):
  conda activate xcout
  python scrapers/fbref_seriea.py
"""

import io
import sys
import math
import time
import difflib
import logging
import unicodedata
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
import soccerdata as sd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

TEMPORADA   = "2526"
LIGA_ID     = 26
LEAGUE_STR  = "ITA-Serie A"
LIGA_NOMBRE = "Serie A"
LIGA_PAIS   = "Italia"
MIN_MINUTOS = 90
PAGE_DELAY  = 8  # segundos entre peticiones a FBref

# Aliases FBref nombre normalizado -> nombre en DB para el schedule
FBREF_ALIASES: dict[str, str] = {
    "inter":           "inter milan",
    "internazionale":  "inter milan",
    "milan":           "ac milan",
    "roma":            "as roma",
    "lazio":           "ss lazio",
    "napoli":          "ssc napoli",
    "atalanta":        "atalanta bc",
    "fiorentina":      "acf fiorentina",
    "bologna":         "bologna fc",
    "torino":          "torino fc",
    "genoa":           "genoa cfc",
    "cagliari":        "cagliari calcio",
    "lecce":           "us lecce",
    "udinese":         "udinese calcio",
    "empoli":          "empoli fc",
    "verona":          "hellas verona",
    "hellas verona":   "hellas verona",
    "monza":           "ac monza",
    "venezia":         "venezia fc",
    "como":            "como 1907",
    "parma":           "parma calcio 1913",
}


# --- Helpers ------------------------------------------------------------------

_CHAR_MAP = str.maketrans({
    'ı': 'i', 'İ': 'I', 'ğ': 'g', 'Ğ': 'G',
    'ş': 's', 'Ş': 'S', 'ð': 'd', 'Ð': 'D',
    'þ': 'th', 'ø': 'o', 'Ø': 'O',
    'æ': 'ae', 'Æ': 'Ae', 'ł': 'l', 'Ł': 'L',
    'ß': 'ss', "'": '', '’': '', '‘': '',
    '-': ' ', '–': ' ', '—': ' ',
})

def _norm(text: str) -> str:
    if not text:
        return ""
    text = str(text).translate(_CHAR_MAP)
    nfkd = unicodedata.normalize("NFKD", text)
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


def _safe_int(v) -> "int | None":
    v = _val(v)
    if v is None:
        return None
    try:
        f = float(str(v).replace(",", ""))
        return None if (math.isnan(f) or math.isinf(f)) else int(round(f))
    except Exception:
        return None


def _safe_float(v, dec: int = 2) -> "float | None":
    v = _val(v)
    if v is None:
        return None
    try:
        f = float(str(v).replace(",", ""))
        return None if (math.isnan(f) or math.isinf(f)) else round(f, dec)
    except Exception:
        return None


def _flatten(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        f"{a}__{b}" if b else a
        for a, b in (c if isinstance(c, tuple) else (c, "") for c in df.columns)
    ]
    return df


def _find_col(df: pd.DataFrame, *keywords, reject=None) -> "str | None":
    reject = [r.lower() for r in (reject or [])]
    for col in df.columns:
        cl = col.lower()
        if all(k.lower() in cl for k in keywords) and not any(r in cl for r in reject):
            return col
    return None


def _is_aggregate(team_name: str) -> bool:
    if not team_name:
        return False
    return "squad" in str(team_name).lower() or "club" in str(team_name).lower()


# --- Resolve + update shared --------------------------------------------------

def _resolve(pnorm, snorm, full_map, name_map, last_map):
    return (
        full_map.get((pnorm, snorm)) or
        name_map.get(pnorm) or
        (last_map.get(pnorm.split()[-1]) if pnorm else None)
    )


def update_supabase(rows, full_map, name_map, last_map, label) -> tuple:
    ok = sin_match = 0
    fallos = []
    for row in rows:
        pnorm = row["player_norm"]
        snorm = row["squad_norm"]
        jid   = _resolve(pnorm, snorm, full_map, name_map, last_map)
        if not jid:
            sin_match += 1
            fallos.append(f"{pnorm} ({snorm})")
            continue
        data = {k: v for k, v in row.items()
                if k not in ("player_norm", "squad_norm") and v is not None}
        if not data:
            continue
        try:
            supabase.table("estadisticas_jugador") \
                .update(data) \
                .eq("jugador_id", jid) \
                .eq("temporada", TEMPORADA) \
                .eq("liga_id", LIGA_ID) \
                .execute()
            ok += 1
        except Exception as e:
            log.warning("  Error %s jid=%d: %s", label, jid, e)
    log.info("  [%-20s] OK=%3d | sin_match=%3d", label, ok, sin_match)
    if fallos:
        log.info("    Fallos muestra: %s", ", ".join(fallos[:6]))
    return ok, sin_match


# --- Fase 1: standard → equipos + jugadores + estadisticas basicas -----------

def load_standard() -> pd.DataFrame:
    log.info("[1] Descargando standard stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="standard").reset_index())
        log.info("    shape=%s | cols=%s", df.shape, list(df.columns[:12]))
        return df
    except Exception as e:
        log.error("    Error: %s", e)
        return pd.DataFrame()


def upsert_equipos(df: pd.DataFrame) -> dict:
    nombres = sorted(
        n for n in df.get("team", pd.Series()).dropna().unique()
        if not _is_aggregate(n)
    )
    rows = [{"nombre": n, "liga_id": LIGA_ID, "temporada": TEMPORADA} for n in nombres]
    log.info("    Upserting %d equipos...", len(rows))
    res = (
        supabase.table("equipos")
        .upsert(rows, on_conflict="nombre,liga_id,temporada")
        .execute()
    )
    mapping = {r["nombre"]: r["id"] for r in res.data}
    log.info("    %d equipos upsertados: %s", len(mapping), sorted(mapping.keys()))
    return mapping


def upsert_jugadores(df: pd.DataFrame, equipo_map: dict) -> "tuple[dict, dict, dict]":
    nuevos = []
    seen   = set()
    for _, row in df.iterrows():
        nombre = _val(row.get("player"))
        if not nombre:
            continue
        equipo_nombre = _val(row.get("team"))
        if _is_aggregate(equipo_nombre):
            continue
        equipo_id = equipo_map.get(equipo_nombre)
        if not equipo_id:
            continue
        key = (_norm(str(nombre)), equipo_id)
        if key in seen:
            continue
        seen.add(key)

        edad = None
        raw_age = _val(row.get("age"))
        if raw_age:
            try:
                edad = int(str(raw_age).split("-")[0])
            except (ValueError, IndexError):
                pass

        nuevos.append({
            "nombre":       nombre,
            "equipo_id":    equipo_id,
            "posicion":     _val(row.get("pos")),
            "edad":         edad,
            "nacionalidad": _val(row.get("nation")),
        })

    if nuevos:
        log.info("    Insertando %d jugadores...", len(nuevos))
        supabase.table("jugadores").upsert(nuevos, on_conflict="nombre,equipo_id").execute()

    # Recargar mapa completo desde DB
    eq_res   = (supabase.table("equipos").select("id, nombre")
                .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute())
    eq_ids   = [e["id"] for e in (eq_res.data or [])]
    eq_names = {e["id"]: e["nombre"] for e in (eq_res.data or [])}

    all_jug = []
    for i in range(0, len(eq_ids), 50):
        res = (supabase.table("jugadores").select("id, nombre, equipo_id")
               .in_("equipo_id", eq_ids[i:i+50]).execute())
        all_jug.extend(res.data or [])

    full_map: dict = {}
    name_map: dict = {}
    last_map: dict = {}
    for r in all_jug:
        jid  = r["id"]
        name = _norm(r.get("nombre") or "")
        team = _norm(eq_names.get(r.get("equipo_id"), ""))
        if not name:
            continue
        full_map[(name, team)] = jid
        if name not in name_map:
            name_map[name] = jid
        last = name.split()[-1]
        if last and last not in last_map:
            last_map[last] = jid

    log.info("    %d jugadores en mapa.", len(name_map))
    return full_map, name_map, last_map


def build_standard_rows(df: pd.DataFrame, full_map, name_map, last_map) -> list[dict]:
    rows    = []
    skipped = 0
    for _, row in df.iterrows():
        player = _val(row.get("player"))
        if not player or str(player).strip().lower() == "player":
            continue
        pnorm   = _norm(str(player))
        snorm   = _norm(str(row.get("team") or ""))
        min_val = _safe_int(row.get("Playing Time__Min"))
        if min_val is not None and min_val < MIN_MINUTOS:
            skipped += 1
            continue
        jid = _resolve(pnorm, snorm, full_map, name_map, last_map)
        if not jid:
            skipped += 1
            continue
        rows.append({
            "jugador_id":         jid,
            "temporada":          TEMPORADA,
            "liga_id":            LIGA_ID,
            "goles":              _safe_int(row.get("Performance__Gls")),
            "asistencias":        _safe_int(row.get("Performance__Ast")),
            "minutos":            min_val,
            "goles_por_90":       _safe_float(row.get("Per 90 Minutes__Gls"), 3),
            "asistencias_por_90": _safe_float(row.get("Per 90 Minutes__Ast"), 3),
            "ga_por_90":          _safe_float(row.get("Per 90 Minutes__G+A"), 3),
        })
    log.info("    %d filas standard | %d skipped", len(rows), skipped)
    return rows


def insert_estadisticas(rows: list[dict]) -> int:
    if not rows:
        log.info("    Nada que insertar.")
        return 0
    seen: dict[tuple, int] = {}
    for i, r in enumerate(rows):
        seen[(r["jugador_id"], r["temporada"])] = i
    rows_dedup = [rows[i] for i in seen.values()]
    if len(rows) != len(rows_dedup):
        log.info("    Duplicados eliminados: %d", len(rows) - len(rows_dedup))
    res = (
        supabase.table("estadisticas_jugador")
        .upsert(rows_dedup, on_conflict="jugador_id,temporada,liga_id")
        .execute()
    )
    log.info("    %d estadisticas insertadas.", len(res.data))
    return len(res.data)


# --- Fase 2: keeper -----------------------------------------------------------

def extract_keepers() -> list[dict]:
    log.info("[2] Descargando keeper stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="keeper").reset_index())
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    col_ga  = _find_col(df, "ga",    reject=["90", "%", "pct", "save"])
    col_sv  = _find_col(df, "saves", reject=["%", "pct", "90"])
    col_pct = (
        _find_col(df, "save%") or
        next((c for c in df.columns if "save%" in c.lower() or "sv%" in c.lower()), None)
    )
    if not col_ga:
        col_ga = next(
            (c for c in df.columns if c.strip().lower() in ("performance__ga", "ga")), None
        )
    log.info("    GA=%s  Saves=%s  Save%%=%s", col_ga, col_sv, col_pct)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue
        ga  = _safe_int(r.get(col_ga))       if col_ga  else None
        sv  = _safe_int(r.get(col_sv))       if col_sv  else None
        pct = _safe_float(r.get(col_pct), 1) if col_pct else None
        if pct is None and sv is not None and ga is not None:
            total = sv + ga
            pct   = round(sv / total * 100, 1) if total > 0 else None
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "portero_goles_encajados": ga,
            "portero_paradas":         sv,
            "portero_paradas_pct":     pct,
        })
    log.info("    %d porteros.", len(rows))
    return rows


# --- Fase 3: shooting → xG inicial FBref -------------------------------------

def extract_shooting() -> list[dict]:
    log.info("[3] Descargando shooting stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="shooting").reset_index())
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    col_xg = (
        _find_col(df, "expected__xg", reject=["np", "90", "/90"]) or
        _find_col(df, "xg",           reject=["np", "90", "/90"])
    )
    log.info("    xG <- %s", col_xg)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "xg": _safe_float(r.get(col_xg)) if col_xg else None,
        })
    log.info("    %d jugadores.", len(rows))
    return rows


# --- Fase 4: misc → recuperaciones -------------------------------------------

def extract_misc() -> list[dict]:
    log.info("[4] Descargando misc stats (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = _flatten(fbref.read_player_season_stats(stat_type="misc").reset_index())
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    col_tklw = (
        _find_col(df, "performance__tklw") or
        next((c for c in df.columns if c.lower() in ("performance__tklw", "tklw")), None)
    )
    col_int = (
        _find_col(df, "performance__int") or
        next((c for c in df.columns if c.lower() in ("performance__int", "int")), None)
    )
    log.info("    TklW=%s  Int=%s", col_tklw, col_int)

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player or player == "player":
            continue
        tklw  = _safe_int(r.get(col_tklw)) if col_tklw else None
        ints  = _safe_int(r.get(col_int))  if col_int  else None
        recup = (tklw or 0) + (ints or 0) if (tklw is not None or ints is not None) else None
        rows.append({
            "player_norm":    player,
            "squad_norm":     squad,
            "entradas":       tklw,
            "intercepciones": ints,
            "recuperaciones": recup,
        })
    log.info("    %d jugadores.", len(rows))
    return rows


# --- Fase 5: xG/xA desde Understat -------------------------------------------

def extract_understat() -> list[dict]:
    log.info("[5] Descargando xG/xA (Understat)...")
    try:
        us  = sd.Understat(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df  = us.read_player_season_stats().reset_index()
        log.info("    shape=%s", df.shape)
    except Exception as e:
        log.error("    Error: %s", e)
        return []

    rows = []
    for _, r in df.iterrows():
        player = _norm(str(r.get("player") or ""))
        squad  = _norm(str(r.get("team")   or ""))
        if not player:
            continue
        rows.append({
            "player_norm": player, "squad_norm": squad,
            "xg": _safe_float(r.get("xg")),
            "xa": _safe_float(r.get("xa")),
        })
    log.info("    %d jugadores.", len(rows))
    return rows


# --- Fase 6: partidos ---------------------------------------------------------

_equipo_cache: dict[str, int] = {}
_equipo_keys:  list[str]      = []


def _load_equipo_cache():
    global _equipo_cache, _equipo_keys
    if _equipo_cache:
        return
    res = (
        supabase.table("equipos").select("id, nombre")
        .eq("liga_id", LIGA_ID).eq("temporada", TEMPORADA).execute()
    )
    for r in res.data:
        k = _norm(r["nombre"])
        if k:
            _equipo_cache[k] = r["id"]
    _equipo_keys = list(_equipo_cache.keys())
    log.info("    Cache equipos: %d.", len(_equipo_cache))


def _resolve_equipo(nombre: str) -> "int | None":
    if not nombre:
        return None
    _load_equipo_cache()
    n     = _norm(nombre)
    alias = FBREF_ALIASES.get(n)
    if alias and alias in _equipo_cache:
        return _equipo_cache[alias]
    if n in _equipo_cache:
        return _equipo_cache[n]
    for k, eid in _equipo_cache.items():
        if n in k or k in n:
            return eid
    close = difflib.get_close_matches(n, _equipo_keys, n=1, cutoff=0.70)
    if close:
        log.debug("    difflib '%s' -> '%s'", n, close[0])
        return _equipo_cache[close[0]]
    log.warning("    Equipo no resuelto: '%s'", nombre)
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


def load_partidos() -> int:
    log.info("[6] Descargando schedule Serie A (FBref)...")
    try:
        fbref = sd.FBref(leagues=LEAGUE_STR, seasons=TEMPORADA)
        df    = fbref.read_schedule().reset_index()
        log.info("    %d partidos en calendario.", len(df))
    except Exception as e:
        log.error("    Error: %s", e)
        return 0

    _load_equipo_cache()
    rows       = []
    sin_equipo = []
    sin_score  = 0

    for _, row in df.iterrows():
        home_nombre = str(row.get("home_team") or "")
        away_nombre = str(row.get("away_team") or "")
        score       = row.get("score")
        jornada     = row.get("week")
        fecha_raw   = row.get("date")

        home_id = _resolve_equipo(home_nombre)
        away_id = _resolve_equipo(away_nombre)
        if home_id is None:
            sin_equipo.append(f"local: '{home_nombre}'")
        if away_id is None:
            sin_equipo.append(f"visit: '{away_nombre}'")

        goles_l, goles_v = _parse_score(str(score) if pd.notna(score) else "")
        if goles_l is None:
            sin_score += 1

        fecha_iso = None
        if pd.notna(fecha_raw):
            try:
                fecha_iso = pd.Timestamp(fecha_raw).isoformat()
            except Exception:
                pass

        rows.append({
            "liga_id":          LIGA_ID,
            "temporada":        TEMPORADA,
            "jornada":          int(jornada) if pd.notna(jornada) else None,
            "fecha":            fecha_iso,
            "equipo_local":     home_id,
            "equipo_visitante": away_id,
            "goles_local":      goles_l,
            "goles_visitante":  goles_v,
            "xg_local":         None,
            "xg_visitante":     None,
            "estado":           "finalizado" if goles_l is not None else "programado",
        })

    if sin_equipo:
        log.warning("    Equipos no resueltos: %s", sorted(set(sin_equipo)))

    log.info("    Con resultado: %d | Pendientes: %d", len(rows) - sin_score, sin_score)

    validos     = [r for r in rows if r["equipo_local"] and r["equipo_visitante"]]
    descartados = len(rows) - len(validos)
    if descartados:
        log.warning("    %d partidos descartados (equipos NULL).", descartados)

    total = 0
    BATCH = 50
    for i in range(0, len(validos), BATCH):
        res = (
            supabase.table("partidos")
            .upsert(
                validos[i:i + BATCH],
                on_conflict="liga_id,temporada,equipo_local,equipo_visitante,jornada",
            )
            .execute()
        )
        total += len(res.data)

    log.info("    %d partidos guardados.", total)
    return total


# --- Verificacion -------------------------------------------------------------

def verify():
    log.info("")
    log.info("[VERIFY] Jugadores clave Serie A:")
    for name in ("Vlahovic", "Lautaro", "Donnarumma", "Barella", "Osimhen"):
        res = (
            supabase.table("jugadores").select("id, nombre")
            .ilike("nombre", f"%{name}%").limit(1).execute()
        )
        if not res.data:
            log.info("  %-25s -> no en DB", name)
            continue
        jid = res.data[0]["id"]
        nom = res.data[0]["nombre"]
        est = (
            supabase.table("estadisticas_jugador")
            .select("goles, asistencias, minutos, xg, xa, "
                    "portero_paradas, portero_goles_encajados, portero_paradas_pct, "
                    "recuperaciones, intercepciones, entradas")
            .eq("jugador_id", jid).eq("temporada", TEMPORADA).eq("liga_id", LIGA_ID)
            .execute()
        )
        if est.data:
            d = est.data[0]
            if d.get("portero_paradas") is not None:
                log.info("  %-28s  paradas=%-4s  GA=%-3s  sv%%=%-5s  min=%s",
                         nom, d["portero_paradas"], d["portero_goles_encajados"],
                         d["portero_paradas_pct"], d.get("minutos"))
            else:
                log.info("  %-28s  gls=%-3s  ast=%-3s  min=%-5s  xG=%-5s  xA=%-5s  rec=%s",
                         nom, d.get("goles"), d.get("asistencias"), d.get("minutos"),
                         d.get("xg"), d.get("xa"), d.get("recuperaciones"))
        else:
            log.info("  %-28s -> sin stats (jid=%d)", nom, jid)


# --- Entrypoint ---------------------------------------------------------------

def run():
    log.info("=" * 66)
    log.info(" Serie A Scraper  (liga_id=%d, temporada=%s)", LIGA_ID, TEMPORADA)
    log.info(" Fases: standard -> keeper -> shooting -> misc -> Understat -> partidos")
    log.info("=" * 66)

    df_std = load_standard()
    if df_std.empty:
        log.error("Sin datos standard. Abortando.")
        return

    equipo_map                   = upsert_equipos(df_std)
    full_map, name_map, last_map = upsert_jugadores(df_std, equipo_map)

    rows_std = build_standard_rows(df_std, full_map, name_map, last_map)
    n_std    = insert_estadisticas(rows_std)

    log.info("Esperando %ds...", PAGE_DELAY); time.sleep(PAGE_DELAY)
    rows_keep  = extract_keepers()
    ok_k, nm_k = update_supabase(rows_keep, full_map, name_map, last_map, "keeper")

    log.info("Esperando %ds...", PAGE_DELAY); time.sleep(PAGE_DELAY)
    rows_shot  = extract_shooting()
    ok_s, nm_s = update_supabase(rows_shot, full_map, name_map, last_map, "shooting/xG")

    log.info("Esperando %ds...", PAGE_DELAY); time.sleep(PAGE_DELAY)
    rows_misc  = extract_misc()
    ok_m, nm_m = update_supabase(rows_misc, full_map, name_map, last_map, "misc")

    log.info("Esperando %ds...", PAGE_DELAY); time.sleep(PAGE_DELAY)
    rows_us    = extract_understat()
    ok_u, nm_u = update_supabase(rows_us, full_map, name_map, last_map, "Understat xG/xA")

    log.info("Esperando %ds...", PAGE_DELAY); time.sleep(PAGE_DELAY)
    n_partidos = load_partidos()

    verify()

    log.info("")
    log.info("=" * 66)
    log.info(" RESUMEN")
    log.info("  Equipos upsertados    : %d", len(equipo_map))
    log.info("  Jugadores en mapa     : %d", len(name_map))
    log.info("  Stats standard        : %d insertadas", n_std)
    log.info("  Keeper                : %d OK, %d sin match", ok_k, nm_k)
    log.info("  Shooting (xG inicial) : %d OK, %d sin match", ok_s, nm_s)
    log.info("  Misc (recuperaciones) : %d OK, %d sin match", ok_m, nm_m)
    log.info("  Understat (xG/xA)     : %d OK, %d sin match", ok_u, nm_u)
    log.info("  Partidos              : %d guardados", n_partidos)
    log.info("=" * 66)


if __name__ == "__main__":
    run()
