"""
FBref Bundesliga Extra — regates y pases_completados (liga_id=25, temporada=2526)

Descarga directa de FBref con cloudscraper + BeautifulSoup:
  - Possession -> regates (Take-Ons Succ)
      https://fbref.com/en/comps/20/possession/Bundesliga-Stats
  - Passing    -> pases_completados (Total Cmp%)
      https://fbref.com/en/comps/20/passing/Bundesliga-Stats

FBref esconde las tablas de stats dentro de comentarios HTML (<!-- -->),
por lo que el parseo busca primero ahi antes de intentar el DOM directo.

NOTA: Si FBref renderiza los valores de las celdas via JavaScript (como
ocurre con PL), todos los valores saldran NULL y el log lo indicara.
En ese caso, revisar sofascore_bundesliga_scraper.py como alternativa
(misma estrategia que sofascore_pl_scraper.py pero con tournament/season
id de la Bundesliga en Sofascore).

Uso (desde backend/):
  conda activate xcout
  python scrapers/fbref_bundesliga_extra.py
"""

import io
import sys
import math
import time
import logging
import unicodedata
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import cloudscraper
from bs4 import BeautifulSoup, Comment
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.supabase_client import supabase

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  %(levelname)s  %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

TEMPORADA  = '2526'
LIGA_ID    = 25
FBREF_BASE = 'https://fbref.com'
PAGE_DELAY = 8  # segundos entre peticiones a FBref

PAGES = {
    'possession': '/en/comps/20/possession/Bundesliga-Stats',
    'passing':    '/en/comps/20/passing/Bundesliga-Stats',
}

_scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)


# --- Helpers ------------------------------------------------------------------

def _norm(text: str) -> str:
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(text))
    return ' '.join(nfkd.encode('ascii', 'ignore').decode().lower().split())


def _safe_int(v) -> 'int | None':
    if v is None or str(v).strip() in ('', '-', 'nan'):
        return None
    try:
        f = float(str(v).replace(',', ''))
        return None if (math.isnan(f) or math.isinf(f)) else int(round(f))
    except Exception:
        return None


def _safe_float(v, dec: int = 1) -> 'float | None':
    if v is None or str(v).strip() in ('', '-', 'nan'):
        return None
    try:
        f = float(str(v).replace(',', ''))
        return None if (math.isnan(f) or math.isinf(f)) else round(f, dec)
    except Exception:
        return None


def _find_col(df: pd.DataFrame, *keywords, reject=None) -> 'str | None':
    reject = [r.lower() for r in (reject or [])]
    for col in df.columns:
        cl = col.lower()
        if all(k.lower() in cl for k in keywords) and not any(r in cl for r in reject):
            return col
    return None


# --- Fetch + parse ------------------------------------------------------------

def _fetch_table(path: str, table_id: str) -> pd.DataFrame:
    """
    Descarga la pagina de FBref y extrae la tabla con id=table_id.
    Busca primero en comentarios HTML (<!-- -->) donde FBref la esconde,
    y hace fallback al DOM directo si no la encuentra ahi.
    """
    url = FBREF_BASE + path
    log.info('  GET %s', url)

    try:
        r = _scraper.get(url, timeout=30)
        log.info('  HTTP %d | %.1f KB', r.status_code, len(r.content) / 1024)
        if r.status_code != 200:
            log.warning('  Status %d — no se pudo descargar %s', r.status_code, url)
            return pd.DataFrame()
    except Exception as e:
        log.error('  Error de red: %s', e)
        return pd.DataFrame()

    soup = BeautifulSoup(r.content, 'lxml')
    table_html = None

    # 1. Buscar en comentarios HTML (FBref envuelve la tabla en <!-- -->)
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        if table_id in comment:
            comment_soup = BeautifulSoup(comment, 'lxml')
            tbl = comment_soup.find('table', {'id': table_id})
            if tbl:
                table_html = str(tbl)
                log.info('  Tabla "%s" hallada en comentario HTML.', table_id)
                break

    # 2. Fallback: tabla directa en el DOM
    if not table_html:
        tbl = soup.find('table', {'id': table_id})
        if tbl:
            table_html = str(tbl)
            log.info('  Tabla "%s" hallada en DOM directo.', table_id)

    if not table_html:
        log.warning('  Tabla "%s" no encontrada en %s', table_id, url)
        return pd.DataFrame()

    try:
        dfs = pd.read_html(io.StringIO(table_html))
    except Exception as e:
        log.error('  Error parseando HTML a DataFrame: %s', e)
        return pd.DataFrame()

    if not dfs:
        return pd.DataFrame()

    df = dfs[0]

    # Aplanar MultiIndex de columnas → "Grupo__Subcol"
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for parts in df.columns:
            parts = [str(p).strip() for p in parts]
            valid = [p for p in parts
                     if p and not p.startswith('Unnamed') and p.lower() != 'nan']
            new_cols.append('__'.join(valid) if len(valid) > 1 else (valid[0] if valid else ''))
        df.columns = new_cols

    # Eliminar filas de cabecera repetidas ("Player", "Rk") y filas sin jugador
    player_col = next((c for c in df.columns if c.lower() == 'player'), None)
    if player_col:
        df = df[df[player_col].notna() & ~df[player_col].isin(['Player', 'Rk'])].copy()

    log.info('  shape=%s', df.shape)
    log.info('  cols=%s', list(df.columns))
    return df.reset_index(drop=True)


# --- Extractores --------------------------------------------------------------

def extract_possession(df: pd.DataFrame) -> list[dict]:
    """Extrae regates (Take-Ons Succ) de la tabla de possession."""
    if df.empty:
        return []

    player_col = next((c for c in df.columns if c.lower() == 'player'), None)
    squad_col  = next((c for c in df.columns if c.lower() in ('squad', 'team')), None)

    # "Succ" dentro de la seccion Take-Ons / Dribbles, evitar columnas de %
    col_reg = (
        _find_col(df, 'succ',  reject=['%', 'att', '/90', 'per']) or
        _find_col(df, 'take',  reject=['%', '/90', 'per']) or
        _find_col(df, 'drib',  reject=['%', '/90', 'per'])
    )
    log.info('  regates <- col="%s"', col_reg)

    rows = []
    non_null = 0
    for _, r in df.iterrows():
        player = _norm(str(r.get(player_col) or '')) if player_col else ''
        squad  = _norm(str(r.get(squad_col)  or '')) if squad_col  else ''
        if not player or player == 'player':
            continue
        val = _safe_int(r.get(col_reg)) if col_reg else None
        if val is not None:
            non_null += 1
        rows.append({'player_norm': player, 'squad_norm': squad, 'regates': val})

    log.info('  %d jugadores | %d con valor != NULL', len(rows), non_null)
    if non_null == 0 and rows:
        log.warning('  AVISO: todos los regates son NULL — probable JS-rendering de FBref.')
        log.warning('  Considera usar Sofascore como fuente alternativa.')
    return rows


def extract_passing(df: pd.DataFrame) -> list[dict]:
    """Extrae pases_completados (Total Cmp%) de la tabla de passing."""
    if df.empty:
        return []

    player_col = next((c for c in df.columns if c.lower() == 'player'), None)
    squad_col  = next((c for c in df.columns if c.lower() in ('squad', 'team')), None)

    # "Total Cmp%" — porcentaje de pases completados
    col_pas = _find_col(df, 'total', 'cmp%') or _find_col(df, 'cmp%')
    log.info('  pases_completados <- col="%s"', col_pas)

    rows = []
    non_null = 0
    for _, r in df.iterrows():
        player = _norm(str(r.get(player_col) or '')) if player_col else ''
        squad  = _norm(str(r.get(squad_col)  or '')) if squad_col  else ''
        if not player or player == 'player':
            continue
        val = _safe_float(r.get(col_pas), dec=1) if col_pas else None
        if val is not None:
            non_null += 1
        rows.append({'player_norm': player, 'squad_norm': squad, 'pases_completados': val})

    log.info('  %d jugadores | %d con valor != NULL', len(rows), non_null)
    if non_null == 0 and rows:
        log.warning('  AVISO: todos los pases_completados son NULL — probable JS-rendering de FBref.')
        log.warning('  Considera usar Sofascore como fuente alternativa.')
    return rows


# --- Supabase -----------------------------------------------------------------

def load_jugadores() -> 'tuple[dict, dict, dict]':
    log.info('[DB] Cargando jugadores Bundesliga (liga_id=%d, temporada=%s)...',
             LIGA_ID, TEMPORADA)

    eq_res = (
        supabase.table('equipos').select('id, nombre')
        .eq('liga_id', LIGA_ID).eq('temporada', TEMPORADA).execute()
    )
    eq_ids   = [e['id'] for e in (eq_res.data or [])]
    eq_names = {e['id']: e['nombre'] for e in (eq_res.data or [])}
    log.info('    %d equipos Bundesliga.', len(eq_ids))

    all_jug = []
    for i in range(0, len(eq_ids), 50):
        res = (
            supabase.table('jugadores').select('id, nombre, equipo_id')
            .in_('equipo_id', eq_ids[i:i+50]).execute()
        )
        all_jug.extend(res.data or [])

    full_map: dict = {}
    name_map: dict = {}
    last_map: dict = {}
    for r in all_jug:
        jid  = r['id']
        name = _norm(r.get('nombre') or '')
        team = _norm(eq_names.get(r.get('equipo_id'), ''))
        if not name:
            continue
        full_map[(name, team)] = jid
        if name not in name_map:
            name_map[name] = jid
        last = name.split()[-1]
        if last and last not in last_map:
            last_map[last] = jid

    log.info('    %d jugadores cargados.', len(name_map))
    return full_map, name_map, last_map


def _resolve(pnorm, snorm, full_map, name_map, last_map):
    return (
        full_map.get((pnorm, snorm)) or
        name_map.get(pnorm) or
        (last_map.get(pnorm.split()[-1]) if pnorm else None)
    )


def update_supabase(rows, full_map, name_map, last_map, label) -> tuple:
    ok = sin_match = sin_valor = 0
    fallos = []
    for row in rows:
        pnorm = row['player_norm']
        snorm = row['squad_norm']
        jid   = _resolve(pnorm, snorm, full_map, name_map, last_map)
        if not jid:
            sin_match += 1
            fallos.append(f'{pnorm} ({snorm})')
            continue
        data = {k: v for k, v in row.items()
                if k not in ('player_norm', 'squad_norm') and v is not None}
        if not data:
            sin_valor += 1
            continue
        try:
            supabase.table('estadisticas_jugador') \
                .update(data) \
                .eq('jugador_id', jid) \
                .eq('temporada', TEMPORADA) \
                .eq('liga_id', LIGA_ID) \
                .execute()
            ok += 1
        except Exception as e:
            log.warning('  Error %s jid=%d: %s', label, jid, e)

    log.info('  [%-16s] OK=%3d | sin_match=%3d | sin_valor=%3d',
             label, ok, sin_match, sin_valor)
    if fallos:
        log.info('    Fallos muestra: %s', ', '.join(fallos[:8]))
    return ok, sin_match


# --- Verificacion -------------------------------------------------------------

def verify():
    log.info('')
    log.info('[VERIFY] Kane y Kimmich:')
    for name in ('Kane', 'Kimmich'):
        res = (
            supabase.table('jugadores').select('id, nombre')
            .ilike('nombre', f'%{name}%').limit(1).execute()
        )
        if not res.data:
            log.info('  %-20s -> no en DB', name)
            continue
        jid = res.data[0]['id']
        nom = res.data[0]['nombre']
        est = (
            supabase.table('estadisticas_jugador')
            .select('regates, pases_completados, goles, asistencias, minutos')
            .eq('jugador_id', jid).eq('temporada', TEMPORADA).eq('liga_id', LIGA_ID)
            .execute()
        )
        if est.data:
            d = est.data[0]
            log.info('  %-28s  regates=%-5s  pases%%=%-6s  goles=%s  ast=%s  min=%s',
                     nom,
                     d.get('regates'),
                     d.get('pases_completados'),
                     d.get('goles'),
                     d.get('asistencias'),
                     d.get('minutos'))
        else:
            log.info('  %-28s -> sin fila en estadisticas_jugador (jid=%d)', nom, jid)


# --- Entrypoint ---------------------------------------------------------------

def run():
    log.info('=' * 66)
    log.info(' FBref Bundesliga Extra — regates + pases_completados')
    log.info(' liga_id=%d  temporada=%s', LIGA_ID, TEMPORADA)
    log.info('=' * 66)

    full_map, name_map, last_map = load_jugadores()
    if not name_map:
        log.error('Sin jugadores Bundesliga en DB. Lanza fbref_bundesliga.py primero.')
        return

    # ── 1. Possession → regates ───────────────────────────────────────────────
    log.info('')
    log.info('[1] Possession (regates)...')
    df_poss   = _fetch_table(PAGES['possession'], 'stats_possession')
    rows_poss = extract_possession(df_poss)
    ok_p, nm_p = update_supabase(rows_poss, full_map, name_map, last_map, 'possession')

    log.info('Esperando %ds...', PAGE_DELAY)
    time.sleep(PAGE_DELAY)

    # ── 2. Passing → pases_completados ────────────────────────────────────────
    log.info('')
    log.info('[2] Passing (pases_completados)...')
    df_pass   = _fetch_table(PAGES['passing'], 'stats_passing')
    rows_pass = extract_passing(df_pass)
    ok_a, nm_a = update_supabase(rows_pass, full_map, name_map, last_map, 'passing')

    verify()

    log.info('')
    log.info('=' * 66)
    log.info(' RESUMEN')
    log.info('  Possession (regates)   : %d OK, %d sin match', ok_p, nm_p)
    log.info('  Passing (pases%%)      : %d OK, %d sin match', ok_a, nm_a)
    log.info('=' * 66)


if __name__ == '__main__':
    run()
