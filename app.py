import os
import re
import unicodedata
from datetime import date as _date

import duckdb
import pandas as pd
import plotly.express as px
import requests
from dash import Dash, Input, Output, callback, dash_table, dcc, html
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "tank01-fantasy-stats.p.rapidapi.com"

PORTFOLIO_URL = (
    "https://oscarrojas-portfolio-e1imgiphw-orojas119s-projects.vercel.app"
)

SAMPLE_DATA = [
    (1629029, "Shai Gilgeous-Alexander", "OKC", 68, 33.5, 6.6, 4.3, 0.534, 0.873, "SG", 27, 36.0),
    (203999,  "Nikola Jokic",            "DEN", 65, 27.7, 10.7, 12.9, 0.569, 0.831, "C",  31, 34.5),
    (203507,  "Giannis Antetokounmpo",   "MIA", 73, 27.6, 5.4, 9.8, 0.612, 0.654, "PF", 30, 35.2),
    (1629627, "Luka Doncic",             "LAL", 60, 33.5, 8.3, 7.7, 0.457, 0.766, "PG", 26, 36.1),
    (1630162, "Anthony Edwards",         "MIN", 79, 28.8, 3.7, 5.0, 0.465, 0.834, "SG", 24, 35.0),
    (201142,  "Kevin Durant",            "PHX", 64, 26.9, 4.3, 7.0, 0.530, 0.820, "SF", 36, 36.5),
    (201939,  "Stephen Curry",           "GSW", 74, 24.6, 5.8, 4.5, 0.453, 0.923, "PG", 37, 33.0),
    (1628369, "Jayson Tatum",            "BOS", 74, 27.4, 5.1, 9.0, 0.452, 0.833, "SF", 27, 36.7),
    (1641705, "Victor Wembanyama",       "SAS", 71, 25.4, 3.9, 10.7, 0.468, 0.832, "C",  21, 32.0),
    (1630595, "Cade Cunningham",         "DET", 70, 24.9, 9.9, 4.5, 0.434, 0.861, "PG", 23, 35.2),
    (203076,  "Damian Lillard",          "MIL", 78, 25.4, 8.4, 4.4, 0.450, 0.892, "PG", 34, 35.8),
    (1626164, "Devin Booker",            "PHX", 69, 25.7, 6.5, 4.6, 0.472, 0.892, "SG", 28, 36.2),
    (1628386, "Jalen Brunson",           "NYK", 77, 26.6, 7.3, 3.9, 0.476, 0.843, "PG", 28, 36.5),
    (1629027, "Trae Young",              "ATL", 54, 24.6, 10.8, 3.1, 0.435, 0.890, "PG", 27, 34.5),
    (1628436, "Tyrese Haliburton",       "IND", 69, 20.6, 12.3, 4.7, 0.459, 0.841, "PG", 25, 33.2),
    (203954,  "Joel Embiid",             "PHI", 39, 26.9, 3.9, 7.7, 0.505, 0.855, "C",  31, 33.6),
    (202681,  "Kyrie Irving",            "DAL", 68, 24.4, 5.5, 3.9, 0.484, 0.893, "PG", 33, 34.1),
    (1629011, "Karl-Anthony Towns",      "NYK", 69, 24.1, 3.5, 13.7, 0.536, 0.839, "C",  29, 34.2),
    (1628760, "Darius Garland",          "CLE", 75, 20.8, 6.4, 3.4, 0.458, 0.854, "PG", 25, 34.7),
    (1628378, "Donovan Mitchell",        "CLE", 68, 27.9, 5.7, 4.5, 0.443, 0.853, "SG", 28, 35.2),
]


# ── Data loading ──────────────────────────────────────────────────────────────

def _calc_age(bday_str: str) -> int:
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


def _fetch_from_api():
    if not RAPIDAPI_KEY:
        return None
    try:
        print("Fetching 2025-26 NBA stats from Tank01...")
        resp = requests.get(
            f"https://{RAPIDAPI_HOST}/getNBATeams",
            headers={"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": RAPIDAPI_HOST},
            params={"rosters": "true", "statsToGet": "averages", "season": "2025"},
            timeout=30,
        )
        resp.raise_for_status()
        teams = resp.json().get("body", [])
        rows, seen = [], set()
        for team in teams:
            for player in team.get("Roster", {}).values():
                pid = player.get("nbaComID") or player.get("playerID", "")
                if not pid or pid in seen:
                    continue
                stats = player.get("stats") or {}
                gp = int(stats.get("gamesPlayed") or 0)
                if gp == 0:
                    continue
                seen.add(pid)
                rows.append({
                    "player_id":         int(pid),
                    "player_name":       player.get("longName") or player.get("espnName", ""),
                    "team_abbreviation": team.get("teamAbv", ""),
                    "games_played":      gp,
                    "points_per_game":   round(float(stats.get("pts")  or 0), 2),
                    "assists_per_game":  round(float(stats.get("ast")  or 0), 2),
                    "rebounds_per_game": round(float(stats.get("reb")  or 0), 2),
                    "field_goal_pct":    round(float(stats.get("fgp")  or 0) / 100, 3),
                    "free_throw_pct":    round(float(stats.get("ftp")  or 0) / 100, 3),
                    "position":          player.get("pos", ""),
                    "age":               _calc_age(player.get("bDay", "")),
                    "min_per_game":      round(float(stats.get("mins") or 0), 1),
                    # TODO: plus_minus not available from Tank01 per-game averages
                    "plus_minus":        0.0,
                })
        print(f"Loaded {len(rows)} players from Tank01.")
        return pd.DataFrame(rows)
    except Exception as e:
        print(f"Tank01 error: {e} — falling back to sample data.")
        return None


def _make_sample_df() -> pd.DataFrame:
    cols = [
        "player_id", "player_name", "team_abbreviation", "games_played",
        "points_per_game", "assists_per_game", "rebounds_per_game",
        "field_goal_pct", "free_throw_pct", "position", "age", "min_per_game",
    ]
    df = pd.DataFrame(SAMPLE_DATA, columns=cols)
    df["plus_minus"] = 0.0
    return df


_PM_PATH = os.path.join(os.path.dirname(__file__), "data", "plus_minus_2526.csv")


def _normalize_name(name: str) -> str:
    """Strip accents, lowercase, remove Jr/Sr/II/III, collapse whitespace."""
    name = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"\b(jr\.?|sr\.?|ii|iii|iv)\b", "", name)
    name = re.sub(r"[^\w\s]", "", name)
    return " ".join(name.split())


def _merge_bpm(df: pd.DataFrame) -> pd.DataFrame:
    """Left-join BPM from the pre-fetched bball-ref CSV into df."""
    if not os.path.exists(_PM_PATH):
        print("BPM CSV not found — plus_minus will be 0.0 for all players.")
        return df
    bpm = pd.read_csv(_PM_PATH)
    bpm = bpm.drop_duplicates("player_name_norm", keep="first")  # safety guard
    df = df.copy()
    df["_name_norm"] = df["player_name"].apply(_normalize_name)
    merged = df.merge(bpm[["player_name_norm", "bpm"]], left_on="_name_norm",
                      right_on="player_name_norm", how="left")
    df["plus_minus"] = merged["bpm"].fillna(0.0).values
    df.drop(columns=["_name_norm"], inplace=True)
    matched = (merged["bpm"].notna()).sum()
    print(f"BPM merged: {matched}/{len(df)} players matched to bball-ref data.")
    return df


_df = _fetch_from_api()
if _df is None:
    _df = _make_sample_df()

_df = _merge_bpm(_df)

_teams = sorted(_df["team_abbreviation"].dropna().unique().tolist())
_team_options = (
    [{"label": "All Teams", "value": "All Teams"}] +
    [{"label": t, "value": t} for t in _teams]
)
_gp_max = int(_df["games_played"].max())


# ── Query helpers ─────────────────────────────────────────────────────────────

def _build_where(mpg, positions, age_range, team, gp_range=None) -> str:
    conditions = []

    if mpg is not None:
        conditions.append(f"min_per_game >= {float(mpg)}")

    if positions:
        quoted = ", ".join(f"'{p}'" for p in positions)
        conditions.append(f"position IN ({quoted})")

    if age_range and age_range != "All Ages":
        if age_range == "37+":
            conditions.append("age >= 37")
        else:
            lo, hi = age_range.split("-")
            conditions.append(f"age BETWEEN {lo} AND {hi}")

    if team and team != "All Teams":
        conditions.append(f"team_abbreviation = '{team}'")

    if gp_range and len(gp_range) == 2:
        conditions.append(f"games_played BETWEEN {gp_range[0]} AND {gp_range[1]}")

    return ("WHERE " + " AND ".join(conditions)) if conditions else ""


def _query(sql: str) -> pd.DataFrame:
    con = duckdb.connect(":memory:")
    con.register("stg_players", _df)
    result = con.execute(sql).fetch_df()
    con.close()
    return result


def get_summary(where: str = "") -> pd.DataFrame:
    return _query(f"""
        SELECT
            COUNT(DISTINCT player_id)             AS total_players,
            ROUND(AVG(points_per_game),   2)      AS avg_ppg,
            ROUND(AVG(assists_per_game),  2)      AS avg_apg,
            ROUND(AVG(rebounds_per_game), 2)      AS avg_rpg
        FROM stg_players {where}
    """)


def get_top_scorers(where: str = "") -> pd.DataFrame:
    return _query(f"""
        SELECT player_name, team_abbreviation, points_per_game, games_played
        FROM stg_players {where}
        ORDER BY points_per_game DESC
        LIMIT 15
    """)


def get_team_efficiency(where: str = "") -> pd.DataFrame:
    return _query(f"""
        SELECT
            team_abbreviation,
            COUNT(DISTINCT player_id)             AS roster_size,
            ROUND(AVG(points_per_game),   2)      AS avg_team_ppg,
            ROUND(AVG(field_goal_pct),    3)      AS avg_fg_pct
        FROM stg_players {where}
        GROUP BY team_abbreviation
        ORDER BY avg_team_ppg DESC
    """)


def get_leaderboard(where: str = "") -> pd.DataFrame:
    return _query(f"""
        SELECT
            player_name,
            team_abbreviation                                         AS team,
            ROUND(points_per_game,   1)                              AS ppg,
            ROUND(assists_per_game,  1)                              AS apg,
            ROUND(rebounds_per_game, 1)                              AS rpg,
            ROUND(plus_minus,        1)                              AS plus_minus,
            ROUND(
                points_per_game   * 0.4 +
                assists_per_game  * 0.3 +
                rebounds_per_game * 0.2 +
                plus_minus        * 0.1,
            2)                                                        AS impact_score
        FROM stg_players {where}
        ORDER BY impact_score DESC
        LIMIT 10
    """)


# ── Styles & constants ────────────────────────────────────────────────────────

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
CARD = {
    "background": "#ffffff",
    "borderRadius": "12px",
    "padding": "1.5rem",
    "boxShadow": "0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04)",
    "border": "1px solid #E5E7EB",
}
LABEL_STYLE = {
    "fontSize": "0.7rem", "fontWeight": "700", "textTransform": "uppercase",
    "letterSpacing": "0.06em", "color": "#6B7280",
    "marginBottom": "6px", "display": "block",
}
CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font_family=FONT, title_font_size=14, title_font_color="#111827",
    margin=dict(l=8, r=8, t=42, b=8),
    hoverlabel=dict(bgcolor="#1F2937", font_color="#F9FAFB",
                    font_family=FONT, bordercolor="#1F2937"),
)
LEADERBOARD_COLS = [
    {"name": "#",            "id": "rank",         "type": "numeric"},
    {"name": "Player",       "id": "player_name"},
    {"name": "Team",         "id": "team"},
    {"name": "PPG",          "id": "ppg",          "type": "numeric"},
    {"name": "APG",          "id": "apg",          "type": "numeric"},
    {"name": "RPG",          "id": "rpg",          "type": "numeric"},
    {"name": "BPM",          "id": "plus_minus",   "type": "numeric"},
    {"name": "Impact Score", "id": "impact_score", "type": "numeric"},
]


# ── Layout helpers ────────────────────────────────────────────────────────────

def kpi_card(label: str, value: str, accent: str = "#111827") -> html.Div:
    return html.Div([
        html.P(label, style={
            "margin": "0", "fontSize": "0.68rem", "fontWeight": "700",
            "textTransform": "uppercase", "letterSpacing": "0.08em", "color": "#6B7280",
        }),
        html.P(value, style={
            "margin": "8px 0 0", "fontSize": "2.25rem",
            "fontWeight": "800", "color": accent, "lineHeight": "1",
        }),
    ], style=CARD)


def _filter_item(label: str, component, flex: str = "1") -> html.Div:
    return html.Div([
        html.Label(label, style=LABEL_STYLE),
        component,
    ], style={"flex": flex, "minWidth": "130px"})


# ── Dashboard layout ──────────────────────────────────────────────────────────

def _dashboard_layout() -> html.Div:
    return html.Div([

        # Header
        html.Div([
            html.Div([
                html.Span("🏀", style={"fontSize": "2rem", "marginRight": "12px",
                                        "verticalAlign": "middle"}),
                html.Span("NBA Analytics Dashboard", style={
                    "fontSize": "1.75rem", "fontWeight": "800", "color": "#111827",
                    "verticalAlign": "middle",
                }),
            ]),
            html.P("2025-26 Season · powered by dbt + DuckDB + Plotly Dash", style={
                "margin": "6px 0 0", "fontSize": "0.875rem", "color": "#6B7280",
            }),
        ], style={"padding": "2rem 3rem", "background": "#ffffff",
                  "borderBottom": "1px solid #E5E7EB"}),

        # KPI row
        html.Div(id="kpi-row", style={
            "display": "grid", "gridTemplateColumns": "repeat(4, 1fr)",
            "gap": "1.5rem", "padding": "2rem 3rem 0",
        }),

        # Filter bar
        html.Div([
            _filter_item("Min / Game", dcc.Dropdown(
                id="filter-mpg",
                options=[{"label": f"{v}+ min", "value": v}
                         for v in [5, 10, 15, 20, 25, 30, 35]],
                value=15,
                clearable=False,
            )),
            _filter_item("Position", dcc.Dropdown(
                id="filter-position",
                options=[{"label": p, "value": p} for p in ["PG", "SG", "SF", "PF", "C"]],
                value=None,
                multi=True,
                placeholder="All Positions",
            )),
            _filter_item("Age Group", dcc.Dropdown(
                id="filter-age",
                options=[
                    {"label": "All Ages", "value": "All Ages"},
                    {"label": "18–24",    "value": "18-24"},
                    {"label": "25–28",    "value": "25-28"},
                    {"label": "29–32",    "value": "29-32"},
                    {"label": "33–36",    "value": "33-36"},
                    {"label": "37+",      "value": "37+"},
                ],
                value="All Ages",
                clearable=False,
            )),
            _filter_item("Team", dcc.Dropdown(
                id="filter-team",
                options=_team_options,
                value="All Teams",
                clearable=False,
            )),
            # GP slider gets more width since sliders need horizontal room
            _filter_item("Games Played", html.Div([
                dcc.RangeSlider(
                    id="filter-gp",
                    min=1,
                    max=82,
                    step=1,
                    value=[20, 82],
                    marks={1: "1", 10: "10", 20: "20", 40: "40", 60: "60", 82: "82"},
                    tooltip={"placement": "bottom", "always_visible": False},
                ),
            ], style={"paddingTop": "4px"}), flex="2"),
        ], style={
            "display": "flex", "gap": "1.5rem", "alignItems": "flex-start",
            "flexWrap": "wrap",
            "background": "#F3F4F6", "padding": "1.25rem 3rem",
            "borderTop": "1px solid #E5E7EB", "borderBottom": "1px solid #E5E7EB",
            "marginTop": "1.5rem",
        }),

        # Charts row
        html.Div([
            html.Div(dcc.Graph(id="top-scorers-chart",
                               config={"displayModeBar": False}),
                     style={**CARD, "padding": "1.25rem"}),
            html.Div(dcc.Graph(id="team-efficiency-chart",
                               config={"displayModeBar": False}),
                     style={**CARD, "padding": "1.25rem"}),
        ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
                  "gap": "1.5rem", "padding": "1.5rem 3rem"}),

        # Impact Score leaderboard
        html.Div([
            html.Div([
                html.H3("Top 10 Players — Impact Score", style={
                    "margin": "0 0 1rem", "fontSize": "0.95rem", "fontWeight": "700",
                    "color": "#111827",
                }),
                dash_table.DataTable(
                    id="leaderboard-table",
                    columns=LEADERBOARD_COLS,
                    data=[],
                    sort_action="native",
                    style_as_list_view=True,
                    style_table={"borderRadius": "8px", "overflow": "hidden"},
                    style_header={
                        "backgroundColor": "#1F2937", "color": "#F9FAFB",
                        "fontWeight": "700", "fontSize": "0.72rem",
                        "textTransform": "uppercase", "letterSpacing": "0.06em",
                        "padding": "12px 16px", "border": "none",
                    },
                    style_cell={
                        "fontFamily": FONT, "fontSize": "0.875rem",
                        "padding": "10px 16px", "textAlign": "left",
                        "border": "none", "borderBottom": "1px solid #F3F4F6",
                        "color": "#374151",
                    },
                    style_cell_conditional=[
                        {"if": {"column_id": c}, "textAlign": "center"}
                        for c in ["rank", "ppg", "apg", "rpg", "plus_minus", "impact_score"]
                    ],
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "#F9FAFB"},
                        {"if": {"row_index": 0},
                         "backgroundColor": "#FFFBEB", "borderLeft": "4px solid #F59E0B"},
                        {"if": {"column_id": "impact_score"},
                         "color": "#1D4ED8", "fontWeight": "700"},
                    ],
                    page_action="none",
                ),
                html.P(
                    "Impact Score = PPG × 0.4 + APG × 0.3 + RPG × 0.2 + BPM × 0.1  "
                    "· BPM (Box Plus Minus) from Basketball Reference — "
                    "estimates per-100-possession impact, controlling for team quality.",
                    style={"margin": "12px 0 0", "fontSize": "0.72rem",
                           "color": "#9CA3AF", "fontStyle": "italic"},
                ),
            ], style={**CARD, "padding": "1.5rem"}),
        ], style={"padding": "0 3rem 1.5rem"}),

        # Footer
        html.Div([
            html.P("Built with dbt · DuckDB · Plotly Dash",
                   style={"margin": "0", "fontSize": "0.78rem", "color": "#9CA3AF"}),
            html.P("Data: Tank01 / NBA Stats API  |  2025-26 Regular Season",
                   style={"margin": "4px 0 0", "fontSize": "0.78rem", "color": "#9CA3AF"}),
            html.P([
                html.A("About this project", href="/about",
                       style={"color": "#9CA3AF", "textDecoration": "none"}),
                "  ·  Built by  ",
                html.A("Oscar Rojas", href=PORTFOLIO_URL, target="_blank",
                       style={"color": "#9CA3AF", "textDecoration": "none"}),
            ], style={"margin": "8px 0 0", "fontSize": "0.75rem", "color": "#9CA3AF"}),
        ], style={"textAlign": "center", "padding": "2rem 3rem",
                  "background": "#F9FAFB", "borderTop": "1px solid #E5E7EB"}),

        dcc.Store(id="init"),

    ], style={"minHeight": "100vh", "background": "#F9FAFB"})


# ── About page layout ─────────────────────────────────────────────────────────

def _arch_box(title: str, subtitle: str, bg: str, border: str) -> html.Div:
    return html.Div([
        html.Div(title, style={
            "fontWeight": "700", "fontSize": "0.78rem", "color": border,
        }),
        html.Div(subtitle, style={
            "fontSize": "0.62rem", "color": "#6B7280", "marginTop": "3px",
        }),
    ], style={
        "background": bg, "border": f"1px solid {border}",
        "borderRadius": "8px", "padding": "10px 14px",
        "textAlign": "center", "flex": "1", "minWidth": "80px",
    })


def _etl_card(icon: str, title: str, body: str) -> html.Div:
    return html.Div([
        html.Div(icon, style={"fontSize": "1.75rem", "marginBottom": "0.75rem"}),
        html.H3(title, style={
            "margin": "0 0 0.75rem", "fontSize": "1rem",
            "fontWeight": "700", "color": "#1a2e4a",
        }),
        html.P(body, style={
            "margin": "0", "fontSize": "0.875rem",
            "color": "#4B5563", "lineHeight": "1.6",
        }),
    ], style={**CARD, "textAlign": "center", "padding": "1.75rem 1.5rem"})


def _section_heading(text: str) -> html.H2:
    return html.H2(text, style={
        "margin": "2.5rem 0 1rem", "fontSize": "1.25rem",
        "fontWeight": "800", "color": "#1a2e4a",
        "borderBottom": "2px solid #E5E7EB", "paddingBottom": "0.5rem",
    })


def _about_layout() -> html.Div:
    arrow = html.Span("→", style={
        "color": "#9CA3AF", "fontSize": "1.1rem",
        "alignSelf": "center", "flexShrink": "0",
    })

    arch_diagram = html.Div([
        _arch_box("NBA Stats API",  "Tank01 / RapidAPI",    "#DBEAFE", "#3B82F6"),
        arrow,
        _arch_box("Python Fetch",   "fetch_nba_data.py",    "#D1FAE5", "#10B981"),
        arrow,
        _arch_box("Raw CSV",        "dbt seeds/",           "#FEF3C7", "#F59E0B"),
        arrow,
        _arch_box("dbt Models",     "stg_players",          "#EDE9FE", "#8B5CF6"),
        arrow,
        _arch_box("DuckDB",         "In-memory analytics",  "#FCE7F3", "#EC4899"),
        arrow,
        _arch_box("Plotly Dash",    "app.py",               "#DBEAFE", "#1D4ED8"),
        arrow,
        _arch_box("Render",         "Live web app",         "#D1FAE5", "#059669"),
    ], style={
        "display": "flex", "alignItems": "stretch", "gap": "6px",
        "flexWrap": "wrap", "padding": "1.5rem",
        "background": "#F9FAFB", "borderRadius": "12px",
        "border": "1px solid #E5E7EB",
    })

    tech_pill_style = {
        "display": "inline-block",
        "background": "#EEF2FF", "color": "#3730A3",
        "borderRadius": "999px", "padding": "4px 14px",
        "fontSize": "0.8rem", "fontWeight": "600",
        "margin": "4px",
    }

    btn_primary = {
        "background": "#111827", "color": "#ffffff",
        "padding": "12px 24px", "borderRadius": "8px",
        "textDecoration": "none", "fontWeight": "600",
        "fontSize": "0.875rem", "display": "inline-block",
    }
    btn_secondary = {
        "background": "#ffffff", "color": "#111827",
        "padding": "12px 24px", "borderRadius": "8px",
        "textDecoration": "none", "fontWeight": "600",
        "fontSize": "0.875rem", "border": "1px solid #E5E7EB",
        "display": "inline-block",
    }

    return html.Div([

        # Back link
        html.Div(
            html.A("← Back to Dashboard", href="/", style={
                "color": "#6B7280", "textDecoration": "none",
                "fontSize": "0.875rem", "fontWeight": "600",
            }),
            style={"marginBottom": "2rem"},
        ),

        # Page title
        html.Div([
            html.H1("NBA Analytics Pipeline", style={
                "margin": "0", "fontSize": "2rem",
                "fontWeight": "800", "color": "#111827",
            }),
            html.P("Technical Architecture & Implementation", style={
                "margin": "6px 0 0", "fontSize": "1rem", "color": "#6B7280",
            }),
        ], style={
            "paddingBottom": "1.5rem",
            "borderBottom": "2px solid #E5E7EB",
        }),

        # Section 1 — Overview
        _section_heading("Overview"),
        html.P(
            "This NBA Analytics Pipeline is a full end-to-end data engineering project "
            "built with Python, dbt, DuckDB, and Plotly Dash. It pulls 500+ player "
            "records from the 2025-26 NBA season via the Tank01 Fantasy Stats API and "
            "merges BPM (Box Plus Minus) from Basketball Reference — two complementary "
            "sources that together cover per-game production and individual impact. "
            "Data is transformed through a dbt pipeline and served as an interactive "
            "dashboard deployed on Render.",
            style={"color": "#374151", "lineHeight": "1.7", "marginBottom": "1rem"},
        ),
        html.P(
            "The project demonstrates a lightweight but production-ready analytics stack: "
            "raw data flows through dbt's staging layer, business logic lives in "
            "version-controlled SQL models, and the Plotly Dash app reads directly from "
            "in-memory DuckDB — no server-side database process required.",
            style={"color": "#374151", "lineHeight": "1.7", "marginBottom": "1rem"},
        ),
        html.P(
            "Key design goals: zero-dependency deployment (no PostgreSQL, no Redis), "
            "graceful fallback when the NBA API is unavailable, sub-second dashboard "
            "loads for a ~500-row dataset, and fully reproducible builds via pinned "
            "dependencies and a Render auto-deploy pipeline.",
            style={"color": "#374151", "lineHeight": "1.7", "marginBottom": "1rem"},
        ),
        html.Div([
            html.Span(t, style=tech_pill_style)
            for t in ["Python", "dbt", "DuckDB", "Plotly Dash", "Render", "GitHub",
                      "Tank01 API", "Basketball Reference"]
        ], style={"marginTop": "0.5rem"}),

        # Section 2 — Architecture
        _section_heading("Architecture — Data Flow"),
        arch_diagram,

        # Section 3 — ETL cards
        _section_heading("Data Pipeline"),
        html.Div([
            _etl_card(
                "📥", "Extract",
                "Two complementary sources: Tank01 Fantasy Stats API (RapidAPI) "
                "returns all 30 team rosters with per-game averages — PPG, APG, RPG, "
                "FG%, position, age, minutes — in a single request. BPM (Box Plus Minus) "
                "is scraped from Basketball Reference advanced stats and committed as a "
                "static CSV, bypassing cloud IP blocks. Falls back to a built-in sample "
                "dataset if the API is unavailable.",
            ),
            _etl_card(
                "⚙️", "Transform",
                "dbt project transforms raw seeds through a staging layer: cleans "
                "column names, filters zero-game players, and derives PPG, APG, RPG. "
                "At startup, app.py merges the BPM CSV into the in-memory dataset via "
                "normalized name matching (98.5% hit rate). Impact Score = "
                "PPG×0.4 + APG×0.3 + RPG×0.2 + BPM×0.1. DuckDB runs in-process.",
            ),
            _etl_card(
                "📊", "Visualize",
                "Plotly Dash app reads directly from in-memory DuckDB at startup. "
                "5 interactive filters (minutes, position, age, team, games played), "
                "2 Plotly charts, 4 KPI cards, and an Impact Score leaderboard — "
                "all wired to a single callback. Deployed on Render with "
                "auto-deploy from GitHub main branch.",
            ),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(240px, 1fr))",
            "gap": "1.5rem",
        }),

        # Section 4 — Engineering Decisions
        _section_heading("Key Engineering Decisions"),
        html.Ol([
            html.Li([
                html.Strong("DuckDB over PostgreSQL — "),
                "Zero-config, in-process, and fast for analytical queries at this "
                "scale. No connection pooling, no server to manage, deploys as a "
                "Python package.",
            ], style={"marginBottom": "0.75rem", "color": "#374151", "lineHeight": "1.6"}),
            html.Li([
                html.Strong("dbt for transformations — "),
                "Version-controlled SQL with clear lineage, built-in testing, and "
                "readable model definitions. Makes the business logic auditable and "
                "easy to extend.",
            ], style={"marginBottom": "0.75rem", "color": "#374151", "lineHeight": "1.6"}),
            html.Li([
                html.Strong("Graceful API fallback — "),
                "stats.nba.com and Basketball Reference both block cloud server IPs. "
                "Tank01 via RapidAPI provides live per-game stats; BPM is scraped "
                "locally from bball-ref and committed as a static CSV so Render never "
                "makes that blocked request. A built-in sample dataset ensures the "
                "dashboard always renders even without a Tank01 key.",
            ], style={"marginBottom": "0.75rem", "color": "#374151", "lineHeight": "1.6"}),
            html.Li([
                html.Strong("BPM over raw +/- — "),
                "Raw on-court +/- is team-dependent — a star on a bad team gets "
                "punished even when playing well. Box Plus Minus (Basketball Reference) "
                "controls for team quality and estimates individual per-100-possession "
                "impact, making the Impact Score leaderboard far more meaningful.",
            ], style={"marginBottom": "0.75rem", "color": "#374151", "lineHeight": "1.6"}),
            html.Li([
                html.Strong("In-memory DuckDB at startup — "),
                "Eliminates the file-path dependency that caused Render deployments "
                "to crash. Data is fetched fresh from the API on every deploy, "
                "registered into :memory:, and queried per request.",
            ], style={"marginBottom": "0.75rem", "color": "#374151", "lineHeight": "1.6"}),
            html.Li([
                html.Strong("Pinned dependencies — "),
                "protobuf==4.25.9 and Python 3.11 prevent breakage from upstream "
                "changes. dbt 1.7 is incompatible with protobuf 5.x.",
            ], style={"color": "#374151", "lineHeight": "1.6"}),
        ], style={"paddingLeft": "1.5rem"}),

        # Section 5 — dbt Lineage
        _section_heading("dbt Model Lineage"),
        html.Pre(
            "  Tank01 API  ──────────────────────────────────────────────────────────┐\n"
            "  (per-game stats: PPG/APG/RPG/FG%/pos/age/min)                        │\n"
            "         ↓                                                               │\n"
            "  raw.player_stats_raw  ← dbt seed CSV (committed)                     │\n"
            "         ↓                                                               │\n"
            "  staging.stg_players   ← cleans columns, filters GP > 0               │\n"
            "    · renames:  gp→games_played, pts/ast/reb→season totals             │\n"
            "    · derives:  points_per_game, assists_per_game, rebounds_per_game   │\n"
            "    · adds:     position, age, min_per_game                            │\n"
            "         ↓                                                               │\n"
            "  in-memory DuckDB  ←──────────────────────────────────────────────────┘\n"
            "    + BPM merge  ← data/plus_minus_2526.csv (scraped from bball-ref,\n"
            "                    committed; impact_score = PPG×0.4 + APG×0.3 +\n"
            "                    RPG×0.2 + BPM×0.1, 521/529 players matched)\n"
            "         ↓\n"
            "  Plotly Dash dashboard  (Render)",
            style={
                "background": "#1F2937", "color": "#D1FAE5",
                "padding": "1.5rem", "borderRadius": "8px",
                "fontSize": "0.82rem",
                "fontFamily": "ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace",
                "overflowX": "auto", "margin": "0", "lineHeight": "1.8",
                "whiteSpace": "pre",
            },
        ),

        # Section 6 — CTAs
        _section_heading("GitHub & Live Demo"),
        html.Div([
            html.A("View Source on GitHub",
                   href="https://github.com/orojas119/nba-analytics",
                   target="_blank",
                   style=btn_primary),
            html.A("← Back to Dashboard",
                   href="/",
                   style=btn_secondary),
        ], style={"display": "flex", "gap": "1rem", "flexWrap": "wrap",
                  "marginBottom": "3rem"}),

        # Footer
        html.Div([
            html.P([
                "Built by  ",
                html.A("Oscar Rojas", href=PORTFOLIO_URL, target="_blank",
                       style={"color": "#6B7280"}),
                "  ·  Miami, FL",
            ], style={"margin": "0", "fontSize": "0.8rem", "color": "#9CA3AF"}),
        ], style={
            "borderTop": "1px solid #E5E7EB", "paddingTop": "2rem",
            "textAlign": "center",
        }),

    ], style={
        "maxWidth": "900px", "margin": "0 auto",
        "padding": "3rem 2rem", "fontFamily": FONT,
    })


# ── App & routing ─────────────────────────────────────────────────────────────

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "NBA Analytics Dashboard"
server = app.server  # expose for gunicorn

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(id="page-content"),
], style={"fontFamily": FONT, "background": "#F9FAFB", "minHeight": "100vh"})


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/about":
        return _about_layout()
    return _dashboard_layout()


# ── Dashboard data callback ───────────────────────────────────────────────────

@callback(
    Output("kpi-row",               "children"),
    Output("top-scorers-chart",     "figure"),
    Output("team-efficiency-chart", "figure"),
    Output("leaderboard-table",     "data"),
    Input("init",            "data"),
    Input("filter-mpg",      "value"),
    Input("filter-position", "value"),
    Input("filter-age",      "value"),
    Input("filter-team",     "value"),
    Input("filter-gp",       "value"),
)
def update_dashboard(_, mpg, positions, age_range, team, gp_range):
    where = _build_where(mpg, positions, age_range, team, gp_range)

    # KPIs
    s = get_summary(where).iloc[0]
    kpis = [
        kpi_card("Total Players",       str(int(s["total_players"]))),
        kpi_card("Avg Points / Game",   str(s["avg_ppg"]),  "#1D4ED8"),
        kpi_card("Avg Assists / Game",  str(s["avg_apg"]), "#065F46"),
        kpi_card("Avg Rebounds / Game", str(s["avg_rpg"]), "#7C3AED"),
    ]

    # Top Scorers bar
    top = get_top_scorers(where)
    fig_scorers = px.bar(
        top, x="points_per_game", y="player_name", orientation="h",
        title="Top 15 Scorers — Points Per Game",
        labels={"points_per_game": "PPG", "player_name": ""},
        color="points_per_game",
        color_continuous_scale=[[0, "#BFDBFE"], [0.5, "#3B82F6"], [1, "#1E3A8A"]],
        custom_data=["team_abbreviation", "games_played"],
    )
    fig_scorers.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>%{customdata[0]}  |  %{x:.1f} PPG  "
            "|  %{customdata[1]} GP<extra></extra>"
        ),
        marker_line_width=0,
    )
    fig_scorers.update_layout(
        **CHART_LAYOUT,
        yaxis_categoryorder="total ascending",
        coloraxis_showscale=False,
        xaxis_title="Points Per Game",
    )

    # Team Efficiency scatter
    eff = get_team_efficiency(where)
    fig_team = px.scatter(
        eff, x="avg_fg_pct", y="avg_team_ppg",
        size="roster_size", text="team_abbreviation",
        title="Team Efficiency — Avg PPG vs Field Goal %",
        labels={"avg_fg_pct": "Field Goal %", "avg_team_ppg": "Avg PPG",
                "roster_size": "Roster Size"},
        color="avg_team_ppg",
        color_continuous_scale=[[0, "#A7F3D0"], [0.5, "#10B981"], [1, "#064E3B"]],
        size_max=28, custom_data=["team_abbreviation", "roster_size"],
    )
    fig_team.update_traces(
        textposition="top center", marker_line_width=0,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "PPG: %{y:.1f}  |  FG%: %{x:.1%}  |  "
            "Roster: %{customdata[1]}<extra></extra>"
        ),
    )
    fig_team.update_layout(
        **CHART_LAYOUT, coloraxis_showscale=False, xaxis_tickformat=".1%",
    )

    # Leaderboard
    lb = get_leaderboard(where).reset_index(drop=True)
    lb.insert(0, "rank", range(1, len(lb) + 1))

    return kpis, fig_scorers, fig_team, lb.to_dict("records")


if __name__ == "__main__":
    app.run(debug=True, port=8050)
