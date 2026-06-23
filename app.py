import os

import duckdb
import pandas as pd
import plotly.express as px
import requests
from dash import Dash, Input, Output, callback, dcc, html
from dotenv import load_dotenv

load_dotenv()

RAPIDAPI_KEY  = os.getenv("RAPIDAPI_KEY")
RAPIDAPI_HOST = "tank01-fantasy-stats.p.rapidapi.com"

SAMPLE_DATA = [
    (1629029, "Shai Gilgeous-Alexander", "OKC", 75, 33.5, 6.6, 4.3, 0.534, 0.873),
    (203999,  "Nikola Jokic",            "DEN", 65, 27.7, 10.7, 12.9, 0.569, 0.831),
    (203507,  "Giannis Antetokounmpo",   "MIA", 73, 27.6, 5.4, 9.8, 0.612, 0.654),
    (1629627, "Luka Doncic",             "LAL", 60, 33.5, 8.3, 7.7, 0.457, 0.766),
    (1630162, "Anthony Edwards",         "MIN", 79, 28.8, 3.7, 5.0, 0.465, 0.834),
    (201142,  "Kevin Durant",            "PHX", 64, 26.9, 4.3, 7.0, 0.530, 0.820),
    (201939,  "Stephen Curry",           "GSW", 74, 24.6, 5.8, 4.5, 0.453, 0.923),
    (1628369, "Jayson Tatum",            "BOS", 74, 27.4, 5.1, 9.0, 0.452, 0.833),
    (1641705, "Victor Wembanyama",       "SAS", 71, 25.4, 3.9, 10.7, 0.468, 0.832),
    (1630595, "Cade Cunningham",         "DET", 70, 24.9, 9.9, 4.5, 0.434, 0.861),
    (203076,  "Damian Lillard",          "MIL", 78, 25.4, 8.4, 4.4, 0.450, 0.892),
    (1626164, "Devin Booker",            "PHX", 69, 25.7, 6.5, 4.6, 0.472, 0.892),
    (1628386, "Jalen Brunson",           "NYK", 77, 26.6, 7.3, 3.9, 0.476, 0.843),
    (1629027, "Trae Young",              "ATL", 54, 24.6, 10.8, 3.1, 0.435, 0.890),
    (1628436, "Tyrese Haliburton",       "IND", 69, 20.6, 12.3, 4.7, 0.459, 0.841),
    (203954,  "Joel Embiid",             "PHI", 39, 26.9, 3.9, 7.7, 0.505, 0.855),
    (202681,  "Kyrie Irving",            "DAL", 68, 24.4, 5.5, 3.9, 0.484, 0.893),
    (1629011, "Karl-Anthony Towns",      "NYK", 69, 24.1, 3.5, 13.7, 0.536, 0.839),
    (1628760, "Darius Garland",          "CLE", 75, 20.8, 6.4, 3.4, 0.458, 0.854),
    (1628378, "Donovan Mitchell",        "CLE", 68, 27.9, 5.7, 4.5, 0.443, 0.853),
]


# ── Data loading ─────────────────────────────────────────────────────────────

def _fetch_from_api():
    """Pull all 30 team rosters + per-game stats in one Tank01 call."""
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
                    "points_per_game":   round(float(stats.get("pts") or 0), 2),
                    "assists_per_game":  round(float(stats.get("ast") or 0), 2),
                    "rebounds_per_game": round(float(stats.get("reb") or 0), 2),
                    "field_goal_pct":    round(float(stats.get("fgp") or 0) / 100, 3),
                    "free_throw_pct":    round(float(stats.get("ftp") or 0) / 100, 3),
                })

        print(f"Loaded {len(rows)} players from Tank01.")
        return pd.DataFrame(rows)

    except Exception as e:
        print(f"Tank01 error: {e} — falling back to sample data.")
        return None


def _make_sample_df():
    cols = ["player_id", "player_name", "team_abbreviation", "games_played",
            "points_per_game", "assists_per_game", "rebounds_per_game",
            "field_goal_pct", "free_throw_pct"]
    return pd.DataFrame(SAMPLE_DATA, columns=cols)


# Load once at startup; each query registers this DataFrame into a fresh
# in-memory DuckDB so there are no file-path or cross-worker issues.
_df = _fetch_from_api()
if _df is None:
    _df = _make_sample_df()


def _query(sql: str) -> pd.DataFrame:
    con = duckdb.connect(":memory:")
    con.register("stg_players", _df)
    result = con.execute(sql).fetch_df()
    con.close()
    return result


# ── Query helpers ─────────────────────────────────────────────────────────────

def get_summary() -> pd.DataFrame:
    return _query("""
        SELECT
            COUNT(DISTINCT player_id)             AS total_players,
            ROUND(AVG(points_per_game),   2)      AS avg_ppg,
            ROUND(AVG(assists_per_game),  2)      AS avg_apg,
            ROUND(AVG(rebounds_per_game), 2)      AS avg_rpg
        FROM stg_players
    """)


def get_top_scorers() -> pd.DataFrame:
    return _query("""
        SELECT player_name, team_abbreviation, points_per_game, games_played
        FROM stg_players
        ORDER BY points_per_game DESC
        LIMIT 15
    """)


def get_team_efficiency() -> pd.DataFrame:
    return _query("""
        SELECT
            team_abbreviation,
            COUNT(DISTINCT player_id)             AS roster_size,
            ROUND(AVG(points_per_game),   2)      AS avg_team_ppg,
            ROUND(AVG(field_goal_pct),    3)      AS avg_fg_pct
        FROM stg_players
        GROUP BY team_abbreviation
        ORDER BY avg_team_ppg DESC
    """)


# ── App ───────────────────────────────────────────────────────────────────────

app = Dash(__name__)
app.title = "NBA Analytics Dashboard"
server = app.server  # expose for gunicorn

FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
CARD = {
    "background": "#ffffff",
    "borderRadius": "12px",
    "padding": "1.5rem",
    "boxShadow": "0 1px 3px rgba(0,0,0,.08), 0 1px 2px rgba(0,0,0,.04)",
    "border": "1px solid #E5E7EB",
}


def kpi_card(label: str, value: str, accent: str = "#111827") -> html.Div:
    return html.Div([
        html.P(label, style={
            "margin": "0", "fontSize": "0.68rem", "fontWeight": "700",
            "textTransform": "uppercase", "letterSpacing": "0.08em",
            "color": "#6B7280",
        }),
        html.P(value, style={
            "margin": "8px 0 0", "fontSize": "2.25rem",
            "fontWeight": "800", "color": accent, "lineHeight": "1",
        }),
    ], style=CARD)


# ── Layout ───────────────────────────────────────────────────────────────────

app.layout = html.Div([

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

    html.Div(id="kpi-row", style={
        "display": "grid", "gridTemplateColumns": "repeat(4, 1fr)",
        "gap": "1.5rem", "padding": "2rem 3rem 0",
    }),

    html.Div([
        html.Div(dcc.Graph(id="top-scorers-chart",    config={"displayModeBar": False}),
                 style={**CARD, "padding": "1.25rem"}),
        html.Div(dcc.Graph(id="team-efficiency-chart", config={"displayModeBar": False}),
                 style={**CARD, "padding": "1.25rem"}),
    ], style={"display": "grid", "gridTemplateColumns": "1fr 1fr",
              "gap": "1.5rem", "padding": "1.5rem 3rem"}),

    html.Div([
        html.P("Built with dbt · DuckDB · Plotly Dash",
               style={"margin": "0", "fontSize": "0.78rem", "color": "#9CA3AF"}),
        html.P("Data: Tank01 / NBA Stats API  |  2025-26 Regular Season",
               style={"margin": "4px 0 0", "fontSize": "0.78rem", "color": "#9CA3AF"}),
    ], style={"textAlign": "center", "padding": "2rem 3rem",
              "background": "#F9FAFB", "borderTop": "1px solid #E5E7EB",
              "marginTop": "0.5rem"}),

    dcc.Store(id="init"),

], style={"minHeight": "100vh", "background": "#F9FAFB", "fontFamily": FONT})


# ── Callbacks ────────────────────────────────────────────────────────────────

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    font_family=FONT, title_font_size=14, title_font_color="#111827",
    margin=dict(l=8, r=8, t=42, b=8),
    hoverlabel=dict(bgcolor="#1F2937", font_color="#F9FAFB",
                    font_family=FONT, bordercolor="#1F2937"),
)


@callback(
    Output("kpi-row", "children"),
    Output("top-scorers-chart", "figure"),
    Output("team-efficiency-chart", "figure"),
    Input("init", "data"),
)
def update_dashboard(_):
    s = get_summary().iloc[0]
    kpis = [
        kpi_card("Total Players",      str(int(s["total_players"]))),
        kpi_card("Avg Points / Game",  str(s["avg_ppg"]),  "#1D4ED8"),
        kpi_card("Avg Assists / Game", str(s["avg_apg"]), "#065F46"),
        kpi_card("Avg Rebounds / Game", str(s["avg_rpg"]), "#7C3AED"),
    ]

    top = get_top_scorers()
    fig_scorers = px.bar(
        top, x="points_per_game", y="player_name", orientation="h",
        title="Top 15 Scorers — Points Per Game",
        labels={"points_per_game": "PPG", "player_name": ""},
        color="points_per_game",
        color_continuous_scale=[[0, "#BFDBFE"], [0.5, "#3B82F6"], [1, "#1E3A8A"]],
        custom_data=["team_abbreviation", "games_played"],
    )
    fig_scorers.update_traces(
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}  |  %{x:.1f} PPG  |  %{customdata[1]} GP<extra></extra>",
        marker_line_width=0,
    )
    fig_scorers.update_layout(**CHART_LAYOUT, yaxis_categoryorder="total ascending",
                              coloraxis_showscale=False, xaxis_title="Points Per Game")

    eff = get_team_efficiency()
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
        hovertemplate="<b>%{customdata[0]}</b><br>PPG: %{y:.1f}  |  FG%: %{x:.1%}  |  Roster: %{customdata[1]}<extra></extra>",
    )
    fig_team.update_layout(**CHART_LAYOUT, coloraxis_showscale=False,
                           xaxis_tickformat=".1%")

    return kpis, fig_scorers, fig_team


if __name__ == "__main__":
    app.run(debug=True, port=8050)
