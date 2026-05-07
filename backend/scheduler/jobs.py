"""
Cron jobs de Xcout con APScheduler.

Arranque: integrado en el lifespan de FastAPI (main.py).
Schedules:
  - Lunes 10:00 AM → generar análisis de jornada para cada liga activa
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)

LIGAS_ACTIVAS = [1, 24, 25]   # LaLiga, Premier, Bundesliga
TEMPORADA     = "2526"

scheduler = AsyncIOScheduler(timezone="Europe/Madrid")


def _analisis_jornadas():
    """Genera el análisis de la última jornada finalizada de cada liga activa."""
    from ai.insights_generator import generar_analisis_jornada, ultima_jornada_finalizada

    for liga_id in LIGAS_ACTIVAS:
        try:
            jornada = ultima_jornada_finalizada(liga_id, TEMPORADA)
            if jornada is None:
                log.info("[cron] liga %d: sin jornadas finalizadas, omitiendo.", liga_id)
                continue
            resultado = generar_analisis_jornada(liga_id, jornada, TEMPORADA)
            log.info("[cron] liga %d jornada %d: '%s'", liga_id, jornada, resultado.get("titulo", "—"))
        except Exception:
            log.exception("[cron] Error generando análisis liga %d", liga_id)


def init_scheduler():
    """Registra los jobs y arranca el scheduler. Llamar desde el lifespan de FastAPI."""
    scheduler.add_job(
        _analisis_jornadas,
        trigger=CronTrigger(day_of_week="mon", hour=10, minute=0),
        id="analisis_jornadas_semanal",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info("Scheduler iniciado — análisis de jornada: lunes 10:00 AM (Europe/Madrid)")


def stop_scheduler():
    """Para el scheduler limpiamente al apagar la app."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("Scheduler detenido.")
