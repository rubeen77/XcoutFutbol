"""
Cron jobs de Xcout con APScheduler.

Arranque: integrado en el lifespan de FastAPI (main.py).
Schedules:
  - Lunes 10:00 AM  -> generar analisis de jornada para cada liga activa
  - Martes 04:00 AM -> actualizar stats, clasificacion y partidos (FBref)
"""

import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

LIGAS_ACTIVAS = [1, 24, 25, 26, 27]   # LaLiga, Premier, Bundesliga, Serie A, Ligue 1
TEMPORADA     = "2526"

LEAGUE_MAP = {
    1:  {"module": "scrapers.fbref_scraper",    "fbref_str": "ESP-La Liga"},
    24: {"module": "scrapers.fbref_premier",    "fbref_str": "ENG-Premier League"},
    25: {"module": "scrapers.fbref_bundesliga", "fbref_str": "GER-Bundesliga"},
    26: {"module": "scrapers.fbref_seriea",     "fbref_str": "ITA-Serie A"},
}

scheduler = BackgroundScheduler(timezone="Europe/Madrid")


# --- Analisis IA (ya existente) ----------------------------------------------

def _analisis_jornadas():
    """Genera el analisis de la ultima jornada finalizada de cada liga activa."""
    from ai.insights_generator import generar_analisis_jornada, ultima_jornada_finalizada

    for liga_id in LIGAS_ACTIVAS:
        try:
            jornada = ultima_jornada_finalizada(liga_id, TEMPORADA)
            if jornada is None:
                log.info("[cron] liga %d: sin jornadas finalizadas, omitiendo.", liga_id)
                continue
            resultado = generar_analisis_jornada(liga_id, jornada, TEMPORADA)
            log.info("[cron] liga %d jornada %d: '%s'", liga_id, jornada, resultado.get("titulo", "-"))
        except Exception:
            log.exception("[cron] Error generando analisis liga %d", liga_id)


# --- Actualizacion semanal de datos ------------------------------------------

def _actualizar_estadisticas_liga(liga_id: int):
    """Ejecuta el scraper FBref completo para una liga (stats + partidos)."""
    import importlib
    info = LEAGUE_MAP[liga_id]
    mod  = importlib.import_module(info["module"])
    log.info("[cron][%d] Iniciando scraper %s...", liga_id, info["module"])
    mod.run()
    log.info("[cron][%d] Scraper completado.", liga_id)


def _standings_from_schedule(df):
    """Deriva standings (pts, posicion) contando V=3, E=1, D=0 desde el schedule de FBref."""
    import pandas as pd

    col_home  = next((c for c in df.columns if "home" in str(c).lower() and "team" in str(c).lower()), None)
    col_away  = next((c for c in df.columns if "away" in str(c).lower() and "team" in str(c).lower()), None)
    col_score = next((c for c in df.columns if "score" in str(c).lower()), None)

    if not all([col_home, col_away, col_score]):
        log.warning("[cron] standings: columnas no encontradas (home=%s away=%s score=%s)",
                    col_home, col_away, col_score)
        return pd.DataFrame(), None, None, None

    pts: dict[str, int] = {}
    for _, row in df.iterrows():
        # Fix 2: usar pd.notna para evitar TypeError con valores NA de pandas
        score = str(row[col_score]) if pd.notna(row[col_score]) else ""
        home  = str(row[col_home])  if pd.notna(row[col_home])  else ""
        away  = str(row[col_away])  if pd.notna(row[col_away])  else ""
        home  = home.strip()
        away  = away.strip()

        if not home or not away:
            continue

        sep_found = None
        for sep in ["–", "-", "−"]:   # en-dash, hyphen, minus
            if sep in score:
                sep_found = sep
                break
        if sep_found is None:
            continue

        parts = score.split(sep_found)
        try:
            gh, ga = int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            continue

        pts.setdefault(home, 0)
        pts.setdefault(away, 0)
        if gh > ga:
            pts[home] += 3
        elif gh == ga:
            pts[home] += 1
            pts[away] += 1
        else:
            pts[away] += 3

    if not pts:
        return pd.DataFrame(), None, None, None

    rows   = sorted(pts.items(), key=lambda x: -x[1])
    result = pd.DataFrame(rows, columns=["team", "pts"])
    result.insert(0, "rank", range(1, len(result) + 1))
    return result, "team", "pts", "rank"


def _actualizar_clasificacion_liga(liga_id: int):
    """Calcula clasificacion desde read_schedule() y actualiza posicion+puntos en equipos."""
    import unicodedata
    import soccerdata as sd
    from database.supabase_client import supabase

    def _norm(t):
        nfkd = unicodedata.normalize("NFKD", str(t))
        return " ".join(nfkd.encode("ascii", "ignore").decode().lower().split())

    info = LEAGUE_MAP[liga_id]
    log.info("[cron][%d] Calculando clasificacion desde schedule FBref (%s)...",
             liga_id, info["fbref_str"])

    fbref = sd.FBref(leagues=info["fbref_str"], seasons=TEMPORADA)
    df    = fbref.read_schedule().reset_index()
    log.info("[cron][%d] Schedule: %d partidos.", liga_id, len(df))

    df, col_team, col_pts, col_rank = _standings_from_schedule(df)

    if col_team is None:
        log.warning("[cron][%d] Clasificacion no calculada, saltando.", liga_id)
        return

    eq_res = (
        supabase.table("equipos").select("id, nombre")
        .eq("liga_id", liga_id).eq("temporada", TEMPORADA).execute()
    )
    eq_map = {_norm(r["nombre"]): r["id"] for r in (eq_res.data or [])}

    actualizados = 0
    for _, row in df.iterrows():
        team_n = _norm(str(row[col_team]))
        rank   = int(row[col_rank])
        pts    = int(row[col_pts])

        eq_id = eq_map.get(team_n)
        if not eq_id:
            eq_id = next((v for k, v in eq_map.items()
                          if team_n in k or k in team_n), None)
        if not eq_id:
            log.debug("[cron][%d] Equipo no resuelto: '%s'", liga_id, row[col_team])
            continue

        supabase.table("equipos") \
            .update({"posicion_clasificacion": rank, "puntos": pts}) \
            .eq("id", eq_id).execute()
        actualizados += 1

    log.info("[cron][%d] Clasificacion actualizada: %d equipos.", liga_id, actualizados)


def _actualizar_semanal():
    """
    Job principal del martes 04:00 AM.
    Por liga: 1) stats+partidos via scraper, 2) clasificacion via schedule.
    Continua con la siguiente liga si una falla.
    """
    log.info("[cron] === ACTUALIZACION SEMANAL INICIADA ===")
    resultados = {}

    for liga_id in LIGAS_ACTIVAS:
        log.info("[cron] -- Liga %d --", liga_id)

        try:
            _actualizar_estadisticas_liga(liga_id)
            resultados[liga_id] = {"stats": "ok"}
        except Exception:
            log.exception("[cron][%d] Error en estadisticas", liga_id)
            resultados[liga_id] = {"stats": "error"}

        try:
            _actualizar_clasificacion_liga(liga_id)
            resultados[liga_id]["clasificacion"] = "ok"
        except Exception:
            log.exception("[cron][%d] Error en clasificacion", liga_id)
            resultados[liga_id]["clasificacion"] = "error"

    log.info("[cron] === ACTUALIZACION SEMANAL COMPLETADA ===")
    for liga_id, res in resultados.items():
        log.info("[cron]   liga %d -> %s", liga_id, res)

    return resultados


def forzar_actualizacion():
    """Funcion sincrona para lanzar la actualizacion semanal desde el endpoint REST."""
    return _actualizar_semanal()


# --- Clasificaciones desde Sofascore -----------------------------------------

def _actualizar_clasificaciones_sofascore():
    """Descarga standings de Sofascore y actualiza posicion+puntos en equipos."""
    from scrapers.clasificacion_scraper import run as clasificacion_run
    log.info("[cron] Iniciando actualización de clasificaciones (Sofascore)...")
    total = clasificacion_run()
    log.info("[cron] Clasificaciones Sofascore completadas: %d equipos.", total)
    return total


def forzar_clasificaciones():
    """Lanzar clasificaciones manualmente desde el endpoint REST."""
    return _actualizar_clasificaciones_sofascore()


# --- Arranque y parada del scheduler -----------------------------------------

def init_scheduler():
    """Registra los jobs y arranca el scheduler. Llamar desde el lifespan de FastAPI."""
    scheduler.add_job(
        _analisis_jornadas,
        trigger=CronTrigger(day_of_week="mon", hour=10, minute=0),
        id="analisis_jornadas_semanal",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _actualizar_clasificaciones_sofascore,
        trigger=CronTrigger(day_of_week="mon", hour=11, minute=0),
        id="clasificaciones_sofascore_semanal",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _actualizar_semanal,
        trigger=CronTrigger(day_of_week="tue", hour=4, minute=0),
        id="actualizacion_datos_semanal",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info("Scheduler iniciado.")
    log.info("  - Analisis jornada        : lunes 10:00 AM (Europe/Madrid)")
    log.info("  - Clasificaciones Sofascore: lunes 11:00 AM (Europe/Madrid)")
    log.info("  - Actualizacion datos      : martes 04:00 AM (Europe/Madrid)")


def stop_scheduler():
    """Para el scheduler limpiamente al apagar la app."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("Scheduler detenido.")
