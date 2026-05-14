import sys; sys.path.insert(0, '.')
from database.supabase_client import supabase
from collections import Counter

res = supabase.table('partidos').select('estado').eq('temporada', '2526').limit(500).execute()
c = Counter(r['estado'] for r in res.data)
print("Valores de estado en partidos 2526:")
for k, v in c.most_common():
    print(f"  '{k}': {v} filas")
