"""
Fetch 2025-26 NBA player stats via Tank01 Fantasy Stats (RapidAPI).
One call to /getNBATeams with rosters=true pulls all 30 teams + every
player's per-game averages in a single response.

Requires RAPIDAPI_KEY in .env or environment.
Falls back to built-in sample data when the key is absent or the request fails.

Schema note: dbt staging model expects pts/ast/reb as season TOTALS and
divides by gp to produce per-game columns, so we multiply the per-game
averages returned by the API by gamesPlayed before writing to CSV.

New columns added: pos (position), age (from bDay), min_pg (minutes/game).
plus_minus is not available from Tank01 per-game averages (TODO: find source).
"""
import os
import sys
from datetime import date as _date

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "tank01-fantasy-stats.p.rapidapi.com"
SEASON        = "2025"   # Tank01 uses start year: 2025 → 2025-26 season
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "player_stats_raw.csv")


def _calc_age(bday_str: str) -> int:
    """Parse Tank01 bDay format 'M/D/YYYY' into current age."""
    if not bday_str:
        return 0
    try:
        m, d, y = bday_str.split("/")
        birth = _date(int(y), int(m), int(d))
        today = _date.today()
        return today.year - birth.year - (
            (today.month, today.day) < (birth.month, birth.day)
        )
    except Exception:
        return 0

SAMPLE_DATA = [
    # (id, name, team, gp, pts_total, ast_total, reb_total, fg_pct, ft_pct, pos, age, min_pg)
    (1629029, "Shai Gilgeous-Alexander", "OKC", 68, 2278, 449, 292, 0.534, 0.873, "SG", 27, 36.0),
    (203999,  "Nikola Jokic",            "DEN", 65, 1801, 696, 839, 0.569, 0.831, "C",  31, 34.5),
    (203507,  "Giannis Antetokounmpo",   "MIA", 73, 2015, 394, 715, 0.612, 0.654, "PF", 30, 35.2),
    (1629627, "Luka Doncic",             "LAL", 60, 2010, 498, 462, 0.457, 0.766, "PG", 26, 36.1),
    (1630162, "Anthony Edwards",         "MIN", 79, 2275, 292, 395, 0.465, 0.834, "SG", 24, 35.0),
    (201142,  "Kevin Durant",            "PHX", 64, 1722, 275, 448, 0.530, 0.820, "SF", 36, 36.5),
    (201939,  "Stephen Curry",           "GSW", 74, 1820, 429, 333, 0.453, 0.923, "PG", 37, 33.0),
    (1628369, "Jayson Tatum",            "BOS", 74, 2028, 377, 666, 0.452, 0.833, "SF", 27, 36.7),
    (1641705, "Victor Wembanyama",       "SAS", 71, 1803, 277, 760, 0.468, 0.832, "C",  21, 32.0),
    (1630595, "Cade Cunningham",         "DET", 70, 1743, 693, 315, 0.434, 0.861, "PG", 23, 35.2),
    (203076,  "Damian Lillard",          "MIL", 78, 1981, 655, 343, 0.450, 0.892, "PG", 34, 35.8),
    (1626164, "Devin Booker",            "PHX", 69, 1773, 449, 317, 0.472, 0.892, "SG", 28, 36.2),
    (1628386, "Jalen Brunson",           "NYK", 77, 2048, 562, 300, 0.476, 0.843, "PG", 28, 36.5),
    (1629027, "Trae Young",              "ATL", 54, 1328, 583, 167, 0.435, 0.890, "PG", 27, 34.5),
    (1628436, "Tyrese Haliburton",       "IND", 69, 1421, 849, 324, 0.459, 0.841, "PG", 25, 33.2),
    (203954,  "Joel Embiid",             "PHI", 39,  944, 172, 367, 0.505, 0.855, "C",  31, 33.6),
    (202681,  "Kyrie Irving",            "DAL", 68, 1659, 374, 265, 0.484, 0.893, "PG", 33, 34.1),
    (1629011, "Karl-Anthony Towns",      "NYK", 69, 1663, 242, 945, 0.536, 0.839, "C",  29, 34.2),
    (1628760, "Darius Garland",          "CLE", 75, 1560, 480, 255, 0.458, 0.854, "PG", 25, 34.7),
    (1628378, "Donovan Mitchell",        "CLE", 68, 1897, 388, 306, 0.443, 0.853, "SG", 28, 35.2),
]


def try_api_fetch():
    if not RAPIDAPI_KEY or RAPIDAPI_KEY == "your_key_here":
        print("RAPIDAPI_KEY not set — add it to .env", file=sys.stderr)
        return None

    try:
        print("Fetching 2025-26 NBA rosters + stats from Tank01...")
        resp = requests.get(
            f"https://{RAPIDAPI_HOST}/getNBATeams",
            headers={
                "X-RapidAPI-Key":  RAPIDAPI_KEY,
                "X-RapidAPI-Host": RAPIDAPI_HOST,
            },
            params={
                "rosters":     "true",
                "statsToGet":  "averages",
                "season":      SEASON,
            },
            timeout=30,
        )
        resp.raise_for_status()
        teams = resp.json().get("body", [])

        rows = []
        seen_ids = set()

        for team in teams:
            team_abv = team.get("teamAbv", "")
            roster   = team.get("Roster", {})

            for player in roster.values():
                raw_id = player.get("nbaComID") or player.get("playerID", "")
                if not raw_id or raw_id in seen_ids:
                    continue

                stats = player.get("stats") or {}
                gp    = int(stats.get("gamesPlayed") or 0)
                if gp == 0:
                    continue

                ppg = float(stats.get("pts")  or 0)
                apg = float(stats.get("ast")  or 0)
                rpg = float(stats.get("reb")  or 0)
                fgp = float(stats.get("fgp")  or 0) / 100   # 56.9 → 0.569
                ftp = float(stats.get("ftp")  or 0) / 100   # 83.1 → 0.831
                mpg = float(stats.get("mins") or 0)

                seen_ids.add(raw_id)
                rows.append({
                    "player_id":         int(raw_id),
                    "player_name":       player.get("longName") or player.get("espnName", ""),
                    "team_abbreviation": team_abv,
                    "gp":                gp,
                    "pts":               round(ppg * gp),   # totals for dbt schema
                    "ast":               round(apg * gp),
                    "reb":               round(rpg * gp),
                    "fg_pct":            round(fgp, 3),
                    "ft_pct":            round(ftp, 3),
                    "pos":               player.get("pos", ""),
                    "age":               _calc_age(player.get("bDay", "")),
                    "min_pg":            round(mpg, 1),
                    # TODO: plus_minus not available from Tank01 per-game endpoint
                    "plus_minus":        0.0,
                })

        df = pd.DataFrame(rows)
        print(f"Fetched {len(df)} players across {len(teams)} teams.")
        return df

    except Exception as e:
        print(f"Tank01 error ({type(e).__name__}: {e}), using sample data.", file=sys.stderr)
        return None


def make_sample_df():
    cols = [
        "player_id", "player_name", "team_abbreviation",
        "gp", "pts", "ast", "reb", "fg_pct", "ft_pct",
        "pos", "age", "min_pg",
    ]
    df = pd.DataFrame(SAMPLE_DATA, columns=cols)
    df["plus_minus"] = 0.0
    return df


def main():
    df = try_api_fetch()
    if df is None:
        df = make_sample_df()

    out = os.path.abspath(OUTPUT_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out, index=False)

    source = "Tank01 API" if len(df) != len(SAMPLE_DATA) else "sample data"
    print(f"Saved {len(df)} records ({source}) → {out}")


if __name__ == "__main__":
    main()
