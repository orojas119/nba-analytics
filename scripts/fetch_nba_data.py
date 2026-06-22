"""
Fetch 2024-25 NBA player stats from stats.nba.com.
Falls back to a built-in sample dataset when the API is unreachable
(stats.nba.com blocks non-browser clients on many networks).
"""
import os
import sys
import time
import pandas as pd

SEASON = "2024-25"
COLUMNS = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ABBREVIATION", "GP", "PTS", "AST", "REB", "FG_PCT", "FT_PCT"]
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "player_stats_raw.csv")

# stats.nba.com requires browser-like headers
HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Referer": "https://stats.nba.com/",
    "Connection": "keep-alive",
}

# Realistic 2024-25 season totals — all player_ids are unique
# (GP, PTS, AST, REB are season totals, not per-game)
SAMPLE_DATA = [
    (1629029, "Shai Gilgeous-Alexander", "OKC", 75, 2453, 480, 413, 0.534, 0.873),
    (203999,  "Nikola Jokic",            "DEN", 79, 2338, 806, 1027, 0.582, 0.831),
    (203507,  "Giannis Antetokounmpo",   "MIL", 73, 2219, 445, 869, 0.612, 0.654),
    (1629627, "Luka Doncic",             "LAL", 56, 1607, 448, 487, 0.457, 0.766),
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
    (2544,    "LeBron James",            "LAL", 71, 1683, 589, 568, 0.524, 0.773),
    (1629138, "Lauri Markkanen",         "UTA", 78, 1849, 179, 640, 0.497, 0.857),
    (1627742, "Brandon Ingram",          "NOP", 58, 1340, 331, 313, 0.473, 0.793),
    (203120,  "Andre Drummond",          "CHI", 60,  636,  96, 648, 0.560, 0.541),
    (203500,  "Pascal Siakam",           "IND", 80, 1704, 304, 640, 0.481, 0.775),
    (202710,  "Jimmy Butler",            "MIA", 55, 1001, 286, 336, 0.432, 0.803),
    (1628389, "Bam Adebayo",             "MIA", 72, 1469, 274, 749, 0.533, 0.777),
    (1628967, "Saddiq Bey",              "ATL", 65,  780, 130, 416, 0.441, 0.792),
    (202331,  "Paul George",             "PHI", 58, 1050, 244, 302, 0.435, 0.863),
    (201566,  "Russell Westbrook",       "DEN", 51,  561, 399, 255, 0.413, 0.703),
    (203468,  "Tyler Herro",             "MIA", 74, 1524, 340, 296, 0.455, 0.861),
    (1630178, "Franz Wagner",            "ORL", 79, 1697, 333, 498, 0.479, 0.823),
    (1630547, "Paolo Banchero",          "ORL", 67, 1611, 301, 502, 0.456, 0.741),
    (1630224, "Jalen Green",             "HOU", 75, 1769, 266, 298, 0.451, 0.853),
    (1630586, "Jabari Smith Jr.",        "HOU", 72,  864, 115, 504, 0.426, 0.775),
    (1628973, "Mikal Bridges",           "NYK", 76, 1201, 243, 319, 0.437, 0.746),
    (1628368, "De'Aaron Fox",            "SAC", 72, 1692, 518, 288, 0.479, 0.741),
]


def try_api_fetch():
    try:
        from nba_api.stats.endpoints import LeagueDashPlayerStats
        print("Attempting live API fetch...")
        time.sleep(1)
        endpoint = LeagueDashPlayerStats(season=SEASON, timeout=15, headers=HEADERS)
        df = endpoint.get_data_frames()[0]
        df = df[COLUMNS].copy()
        df.columns = [c.lower() for c in df.columns]
        return df
    except Exception as e:
        print(f"API unavailable ({type(e).__name__}), using sample data.", file=sys.stderr)
        return None


def make_sample_df():
    cols = ["player_id", "player_name", "team_abbreviation", "gp", "pts", "ast", "reb", "fg_pct", "ft_pct"]
    return pd.DataFrame(SAMPLE_DATA, columns=cols)


def main():
    df = try_api_fetch() or make_sample_df()

    out = os.path.abspath(OUTPUT_PATH)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    df.to_csv(out, index=False)

    source = "live API" if len(df) > len(SAMPLE_DATA) else "sample data"
    print(f"Fetched {len(df)} records ({source})")
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
