"""Debug: verificar columnas y valores reales de possession/passing/defense para PL."""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import soccerdata as sd
import pandas as pd
from lxml import html as lhtml, etree
from io import StringIO
from pathlib import Path

FBREF_BASE = "https://fbref.com"
fbref = sd.FBref(leagues="ENG-Premier League", seasons="2526")

def flatten_and_clean(df):
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for parts in df.columns:
            parts = [str(p).strip() for p in parts]
            valid = [p for p in parts
                     if p and not p.startswith("Unnamed") and p.lower() != "nan"]
            new_cols.append("__".join(valid) if len(valid) > 1 else (valid[0] if valid else ""))
        df.columns = new_cols
    for col in ("Player", "Squad"):
        if col in df.columns:
            df = df[df[col].notna() & (df[col] != col)].copy()
            break
    return df.reset_index(drop=True)

def fetch_and_flatten(page_path, table_id):
    url = FBREF_BASE + page_path
    filepath = fbref.data_dir / f"pl_{table_id}.html"
    print(f"Fetching {url} ...")
    reader = fbref.get(url, filepath)
    tree = lhtml.parse(reader)
    parser = etree.HTMLParser(recover=True)
    comments = tree.xpath(f"//comment()[contains(.,'div_{table_id}')]")
    if comments:
        tables = etree.fromstring(comments[0].text, parser).xpath(
            f"//table[contains(@id, '{table_id}')]"
        )
        if tables:
            raw = etree.tostring(tables[0], encoding="unicode")
            dfs = pd.read_html(StringIO(raw))
            df = flatten_and_clean(dfs[0]) if dfs else pd.DataFrame()
            return df
    print(f"  NOT FOUND")
    return pd.DataFrame()

def show(df, extra_cols, label):
    print(f"\n--- {label} ---")
    print(f"Shape: {df.shape}")
    print(f"All cols: {list(df.columns)}")
    # Find Salah and Haaland
    for name in ("Salah", "Haaland", "Bruno Fernandes"):
        hits = df[df["Player"].astype(str).str.contains(name, case=False, na=False)] if "Player" in df.columns else pd.DataFrame()
        if not hits.empty:
            row = hits.iloc[0]
            vals = {c: row.get(c) for c in extra_cols if c in df.columns}
            print(f"  {name}: {vals}")
        else:
            print(f"  {name}: not found in table")

# POSSESSION
df_poss = fetch_and_flatten("/en/comps/9/possession/Premier-League-Stats", "stats_possession")
succ_cols = [c for c in df_poss.columns if "succ" in c.lower()]
take_cols  = [c for c in df_poss.columns if "take" in c.lower() or "drib" in c.lower()]
print("Succ cols:", succ_cols)
print("Take/Drib cols:", take_cols)
show(df_poss, succ_cols + take_cols, "POSSESSION")

# PASSING
df_pass = fetch_and_flatten("/en/comps/9/passing/Premier-League-Stats", "stats_passing")
cmp_cols = [c for c in df_pass.columns if "cmp" in c.lower()]
print("Cmp cols:", cmp_cols)
show(df_pass, cmp_cols, "PASSING")

# DEFENSE
df_def = fetch_and_flatten("/en/comps/9/defense/Premier-League-Stats", "stats_defense")
tkl_cols = [c for c in df_def.columns if "tkl" in c.lower()]
int_cols  = [c for c in df_def.columns if c.lower() == "int"]
print("Tkl cols:", tkl_cols)
print("Int cols:", int_cols)
show(df_def, tkl_cols + int_cols, "DEFENSE")
