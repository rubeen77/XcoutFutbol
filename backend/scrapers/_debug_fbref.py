"""Debug: check what columns soccerdata FBref returns for PL standard stats."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import soccerdata as sd
import pandas as pd

fbref = sd.FBref(leagues="ENG-Premier League", seasons="2526")

print("Fetching standard stats...")
try:
    df = fbref.read_player_season_stats(stat_type="standard").reset_index()
    cols = [str(c) for c in df.columns]
    print(f"Shape: {df.shape}")
    print("All columns:")
    for c in cols:
        print(f"  {c}")
    # Find expected/xG columns
    xg_cols = [c for c in cols if 'xg' in c.lower() or 'xag' in c.lower() or 'expect' in c.lower()]
    print(f"\nxG-related columns: {xg_cols}")
    # Show sample data for a known player
    if 'player' in df.columns:
        haaland = df[df['player'].str.contains('Haaland', case=False, na=False)]
        if not haaland.empty:
            print(f"\nHaaland row:")
            print(haaland.iloc[0][xg_cols + ['player', 'team']].to_dict())
except Exception as e:
    print(f"Error standard: {e}")

print("\nFetching possession stats...")
try:
    df_poss = fbref.read_player_season_stats(stat_type="possession").reset_index()
    cols_poss = [str(c) for c in df_poss.columns]
    print(f"Shape: {df_poss.shape}")
    drib_cols = [c for c in cols_poss if 'succ' in c.lower() or 'take' in c.lower() or 'drib' in c.lower()]
    print(f"Dribble-related columns: {drib_cols}")
except Exception as e:
    print(f"Error possession: {e}")

print("\nFetching passing stats...")
try:
    df_pass = fbref.read_player_season_stats(stat_type="passing").reset_index()
    cols_pass = [str(c) for c in df_pass.columns]
    print(f"Shape: {df_pass.shape}")
    pass_cols = [c for c in cols_pass if 'cmp' in c.lower() or 'comp' in c.lower() or 'pct' in c.lower() or '%' in c]
    print(f"Pass-completion columns: {pass_cols}")
except Exception as e:
    print(f"Error passing: {e}")

print("\nDone.")
