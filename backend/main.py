"""
Xcout API — FastAPI app principal

Arrancar:
  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import players, teams, matches

app = FastAPI(
    title="Xcout API",
    description="API de analítica de fútbol español — LaLiga 2025/26",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router, prefix="/jugadores", tags=["jugadores"])
app.include_router(teams.router,   prefix="/equipos",   tags=["equipos"])
app.include_router(matches.router, prefix="/partidos",  tags=["partidos"])


@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok", "version": "1.0.0"}
