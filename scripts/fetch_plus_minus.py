"""
Fetch 2025-26 BPM (Box Plus Minus) from Basketball Reference advanced stats.

BPM is a better metric than raw +/- for our Impact Score:
- Raw +/- is heavily team-dependent (a star on a bad team gets punished)
- BPM estimates per-100-possession individual impact, controlling for team quality

Run this locally and commit the output — bball-ref blocks cloud server IPs.
The dashboard merges this CSV with Tank01 data at startup on Render.

Usage:
    python3 scripts/fetch_plus_minus.py

Output:
    data/plus_minus_2526.csv  —  player_name_norm, bpm, vorp
"""
import os
import re
import unicodedata
from io import StringIO

import pandas as pd
import requests

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "plus_minus_2526.csv")

BREF_URL = "https://www.basketball-reference.com/leagues/NBA_2026_advanced.html"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def normalize_name(name: str) -> str:
    """Lowercase, strip accents, drop Jr/Sr/II/III, collapse spaces."""
    name = unicodedata.normalize("NFKD", str(name))
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"\b(jr\.?|sr\.?|ii|iii|iv)\b", "", name)
    name = re.sub(r"[^\w\s]", "", name)
    return " ".join(name.split())


def main():
    print(f"Fetching advanced stats from {BREF_URL} ...")
    resp = requests.get(BREF_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # Force UTF-8 so accented characters (Jokić, Dončić) decode correctly
    html = resp.content.decode("utf-8", errors="replace")

    tables = pd.read_html(StringIO(html))
    df = tables[0]

    # Drop repeated header rows bball-ref inserts mid-table
    df = df[df["Player"] != "Player"].copy()

    # Numeric coercion
    for col in ["G", "BPM", "VORP"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["BPM"])

    # For traded players bball-ref has one row per team + a "TOT" row.
    # Keep only TOT for those players so each player appears once.
    multi_team = df[df["Team"] == "TOT"]["Player"].unique()
    df = df[~((df["Player"].isin(multi_team)) & (df["Team"] != "TOT"))]

    df["player_name_norm"] = df["Player"].apply(normalize_name)
    df["bpm"]  = df["BPM"].round(1)
    df["vorp"] = df["VORP"].round(1)

    # Pass 1: for players who played on multiple teams, bball-ref adds a "TOT"
    # row with season totals — keep that and drop the per-team rows.
    multi_team = df[df["Team"] == "TOT"]["player_name_norm"].unique()
    df = df[~(df["player_name_norm"].isin(multi_team) & (df["Team"] != "TOT"))]

    # Pass 2: any player still appearing more than once (traded 3+ times, no TOT
    # row) — keep the row with the most games played as the season-best estimate.
    df = df.sort_values("G", ascending=False).drop_duplicates("player_name_norm", keep="first")

    out_df = df[["player_name_norm", "bpm", "vorp"]].reset_index(drop=True)

    out = os.path.abspath(OUTPUT)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    out_df.to_csv(out, index=False)

    print(f"Saved {len(out_df)} rows → {out}")
    print()
    print("Top 10 by BPM:")
    print(out_df.nlargest(10, "bpm").to_string(index=False))


if __name__ == "__main__":
    main()
