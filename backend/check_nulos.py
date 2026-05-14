import sys
sys.path.insert(0, '.')
from database.supabase_client import supabase

res = (supabase.table("partidos")
       .select("id, equipo_local, equipo_visitante, jornada")
       .eq("liga_id", 27).eq("temporada", "2526")
       .is_("goles_local", "null").execute())
rows = res.data or []
print(f"{len(rows)} partidos sin goles")
for r in sorted(rows, key=lambda x: x["jornada"] or 0):
    print(f"  J{r['jornada']}  eq_local={r['equipo_local']}  vs  eq_visitante={r['equipo_visitante']}")
