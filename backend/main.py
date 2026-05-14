"""
Xcout API — FastAPI app principal

Arrancar:
  uvicorn main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import players, teams, matches, insights, leagues, waitlist


@asynccontextmanager
async def lifespan(app: FastAPI):
    from scheduler.jobs import init_scheduler, stop_scheduler
    init_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Xcout API",
    description="API de analítica de fútbol — multi-liga 2025/26",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router, prefix="/jugadores", tags=["jugadores"])
app.include_router(teams.router,   prefix="/equipos",   tags=["equipos"])
app.include_router(matches.router,  prefix="/partidos",  tags=["partidos"])
app.include_router(insights.router, prefix="/insights",  tags=["insights"])
app.include_router(leagues.router,  prefix="/leagues",   tags=["ligas"])
app.include_router(waitlist.router, prefix="/waitlist",  tags=["waitlist"])


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/scheduler/estado", tags=["sistema"])
def scheduler_estado():
    from scheduler.jobs import scheduler
    jobs = []
    for job in scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id":           job.id,
            "proximo_run":  next_run.isoformat() if next_run else None,
            "trigger":      str(job.trigger),
        })
    return {
        "activo": scheduler.running,
        "jobs":   jobs,
    }


@app.post("/api/scheduler/forzar-actualizacion", tags=["sistema"])
def scheduler_forzar():
    import threading
    from scheduler.jobs import forzar_actualizacion
    threading.Thread(target=forzar_actualizacion, daemon=True).start()
    return {"mensaje": "Actualizacion iniciada en segundo plano."}
