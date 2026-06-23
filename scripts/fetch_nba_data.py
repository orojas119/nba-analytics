"""
Fetch 2025-26 NBA player stats via Tank01 Fantasy Stats (RapidAPI).
One call to /getNBATeams with rosters=true pulls all 30 teams + every
player's per-game averages in a single response.

Requires RAPIDAPI_KEY in .env or environment.
Falls back to built-in sample data when the key is absent or the request fails.

Schema note: dbt staging model expects pts/ast/reb as season TOTALS and
divides by gp to produce per-game columns, so we multiply the per-game
averages returned by the API by gamesPlayed before writing to CSV.
"""
import os
import sys

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "tank01-fantasy-stats.p.rapidapi.com"
SEASON        = "2025"   # Tank01 uses start year: 2025 → 2025-26 season
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "data", "player_stats_raw.csv")

SAMPLE_DATA = [
    (1629029, "Shai Gilgeous-Alexander", "OKC", 75, 2453, 480, 413, 0.534, 0.873),
    (203999,  "Nikola Jokic",            "DEN", 65, 1800, 695, 838, 0.569, 0.831),
    (203507,  "Giannis Antetokounmpo",   "MIL", 73, 2219, 445, 869, 0.612, 0.654),
    (1629627, "Luka Doncic",             "LAL", 60, 1722, 480, 522, 0.457, 0.766),
    (1630162, "Anthony Edwards",         "MIN", 79, 2204, 434, 427, 0.465, 0.834),
    (201142,  "Kevin Durant",            "PHX", 64, 1722, 275, 448, 0.530, 0.820),
    (201939,  "Stephen Curry",           "GSW", 74, 1820, 429, 333, 0.453, 0.923),
    (1628369, "Jayson Tatum",            "BOS", 74, 2028, 377, 666, 0.452, 0.833),
    (1641705, "Victor Wembanyama",       "SAS", 71, 1803, 277, 760, 0.468, 0.832),
    (1630595, "Cade Cunningham",         "DET", 70, 1743, 693, 315, 0.434, 0.861),
    (203076,  "Damian Lillard",          "MIL", 78, 1981, 655, 343, 0.450, 0.892),
    (1626164, "Devin Booker",            "PHX", 69, 1773, 449, 317, 0.472, 0.892),
    (1628386, "Jalen Brunson",           "NYK", 77, 2048, 562, 300, 0.476, 0.843),
    (1629027, "Trae Young",              "ATL", 54, 1328, 583, 167, 0.435, 0.890),
    (1628436, "Tyrese Haliburton",       "IND", 69, 1421, 849, 324, 0.459, 0.841),
    (203954,  "Joel Embiid",             "PHI", 39,  944, 172, 367, 0.505, 0.855),
    (202681,  "Kyrie Irving",            "DAL", 68, 1657, 374, 265, 0.484, 0.893),
    (1629011, "Karl-Anthony Towns",      "NYK", 69, 1663, 242, 945, 0.536, 0.839),
    (1628760, "Darius Garland",          "CLE", 75, 1560, 480, 255, 0.458, 0.854),
    (1628378, "Donovan Mitchell",        "CLE", 68, 1748, 401, 306, 0.443, 0.853),
    (1631098, "Alperen Sengun",          "HOU", 80, 1688, 448, 752, 0.550, 0.724),
    (1630530, "Evan Mobley",             "CLE", 72, 1339, 223, 699, 0.549, 0.726),
    (1630054, "Scottie Barnes",          "TOR", 70, 1393, 427, 574, 0.489, 0.730),
    (2544,    "LeBron James",            "LAL", 65, 1528, 455, 520, 0.524, 0.773),
    (1629138, "Lauri Markkanen",         "UTA", 78, 1849, 179, 640, 0.497, 0.857),
    (1627742, "Brandon Ingram",          "NOP", 58, 1340, 331, 313, 0.473, 0.793),
    (203120,  "Andre Drummond",          "CHI", 60,  636,  96, 648, 0.560, 0.541),
    (203500,  "Pascal Siakam",           "IND", 80, 1704, 304, 640, 0.481, 0.775),
    (202710,  "Jimmy Butler",            "GSW", 55, 1001, 286, 336, 0.432, 0.803),
    (1628389, "Bam Adebayo",             "MIA", 72, 1469, 274, 749, 0.533, 0.777),
    (1628967, "Saddiq Bey",              "ATL", 65,  780, 130, 416, 0.441, 0.792),
    (202331,  "Paul George",             "PHI", 58, 1050, 244, 302, 0.435, 0.863),
    (203468,  "Tyler Herro",             "MIA", 74, 1524, 340, 296, 0.455, 0.861),
    (1630178, "Franz Wagner",            "ORL", 79, 1697, 333, 498, 0.479, 0.823),
    (1630547, "Paolo Banchero",          "ORL", 67, 1611, 301, 502, 0.456, 0.741),
    (1630224, "Jalen Green",             "HOU", 75, 1769, 266, 298, 0.451, 0.853),
    (1630586, "Jabari Smith Jr.",        "HOU", 72,  864, 115, 504, 0.426, 0.775),
    (1628973, "Mikal Bridges",           "NYK", 76, 1201, 243, 319, 0.437, 0.746),
    (1628368, "De'Aaron Fox",            "SAC", 72, 1692, 518, 288, 0.479, 0.741),
    (1641705, "Cooper Flagg",            "DAL", 70, 1540, 350, 490, 0.471, 0.821),
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
                # Use nbaComID as the canonical player_id
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
                })

        df = pd.DataFrame(rows)
        print(f"Fetched {len(df)} players across {len(teams)} teams.")
        return df

    except Exception as e:
        print(f"Tank01 error ({type(e).__name__}: {e}), using sample data.", file=sys.stderr)
        return None


def make_sample_df():
    cols = ["player_id", "player_name", "team_abbreviation",
            "gp", "pts", "ast", "reb", "fg_pct", "ft_pct"]
    return pd.DataFrame(SAMPLE_DATA, columns=cols)


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
