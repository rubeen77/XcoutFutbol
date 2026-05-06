"""Re-ejecuta solo el bloque TM del premier_scraper (con el fix del upsert)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.premier_scraper import (
    get_tm_teams, scrape_tm_squads, apply_tm_data,
    DB_LIGA_ID, DB_TEMPORADA,
)
from database.supabase_client import supabase

res = supabase.table("equipos").select("id,nombre") \
    .eq("liga_id", DB_LIGA_ID).eq("temporada", DB_TEMPORADA).execute()
equipo_map = {r["nombre"]: r["id"] for r in res.data}
print(f"Equipos en DB: {len(equipo_map)}")

tm_teams = get_tm_teams()
if tm_teams:
    df_tm = scrape_tm_squads(tm_teams)
    apply_tm_data(df_tm, equipo_map)
    print("TM completado OK.")
else:
    print("No se obtuvieron equipos TM.")
