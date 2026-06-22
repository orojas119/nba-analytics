import duckdb
import pandas as pd
import plotly.express as px
from dash import Dash, Input, Output, callback, dcc, html

DB_PATH = "/Users/orojas/projects/nba-analytics/nba_analytics.duckdb"

app = Dash(__name__)
app.title = "NBA Analytics Dashboard"
server = app.server  # expose for gunicorn


# ── Data helpers ─────────────────────────────────────────────────────────────

def _query(sql: str) -> pd.DataFrame:
    with duckdb.connect(DB_PATH, read_only=True) as con:
        return con.execute(sql).fetch_df()


def get_summary() -> pd.DataFrame:
    return _query("""
        SELECT
            COUNT(DISTINCT player_id)           AS total_players,
            ROUND(AVG(points_per_game),   2)    AS avg_ppg,
            ROUND(AVG(assists_per_game),  2)    AS avg_apg,
            ROUND(AVG(rebounds_per_game), 2)    AS avg_rpg
        FROM raw.stg_players
    """)


def get_top_scorers() -> pd.DataFrame:
    return _query("""
        SELECT player_name, team_abbreviation, points_per_game, games_played
        FROM raw.stg_players
        ORDER BY points_per_game DESC
        LIMIT 15
    """)


def get_team_efficiency() -> pd.DataFrame:
    return _query("""
        SELECT
            team_abbreviation,
            COUNT(DISTINCT player_id)           AS roster_size,
            ROUND(AVG(points_per_game),   2)    AS avg_team_ppg,
            ROUND(AVG(field_goal_pct),    3)    AS avg_fg_pct
        FROM raw.stg_players
        GROUP BY team_abbreviation
        ORDER BY avg_team_ppg DESC
    """)


# ── Styles ───────────────────────────────────────────────────────────────────

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

    # ── Header ──────────────────────────────────────────────────────────────
    html.Div([
        html.Div([
            html.Span("🏀", style={"fontSize": "2rem", "marginRight": "12px",
                                    "verticalAlign": "middle"}),
            html.Span("NBA Analytics Dashboard", style={
                "fontSize": "1.75rem", "fontWeight": "800", "color": "#111827",
                "verticalAlign": "middle",
            }),
        ]),
        html.P("2024-25 Season · powered by dbt + DuckDB + Plotly Dash", style={
            "margin": "6px 0 0", "fontSize": "0.875rem", "color": "#6B7280",
        }),
    ], style={
        "padding": "2rem 3rem",
        "background": "#ffffff",
        "borderBottom": "1px solid #E5E7EB",
    }),

    # ── KPI row (filled by callback) ─────────────────────────────────────
    html.Div(id="kpi-row", style={
        "display": "grid",
        "gridTemplateColumns": "repeat(4, 1fr)",
        "gap": "1.5rem",
        "padding": "2rem 3rem 0",
    }),

    # ── Charts ───────────────────────────────────────────────────────────
    html.Div([
        html.Div(
            dcc.Graph(id="top-scorers-chart", config={"displayModeBar": False}),
            style={**CARD, "padding": "1.25rem"},
        ),
        html.Div(
            dcc.Graph(id="team-efficiency-chart", config={"displayModeBar": False}),
            style={**CARD, "padding": "1.25rem"},
        ),
    ], style={
        "display": "grid",
        "gridTemplateColumns": "1fr 1fr",
        "gap": "1.5rem",
        "padding": "1.5rem 3rem",
    }),

    # ── Footer ───────────────────────────────────────────────────────────
    html.Div([
        html.P("Built with dbt · DuckDB · Plotly Dash",
               style={"margin": "0", "fontSize": "0.78rem", "color": "#9CA3AF"}),
        html.P("Data: NBA Stats API  |  2024-25 Regular Season",
               style={"margin": "4px 0 0", "fontSize": "0.78rem", "color": "#9CA3AF"}),
    ], style={
        "textAlign": "center",
        "padding": "2rem 3rem",
        "background": "#F9FAFB",
        "borderTop": "1px solid #E5E7EB",
        "marginTop": "0.5rem",
    }),

    # Triggers callback on page load
    dcc.Store(id="init"),

], style={"minHeight": "100vh", "background": "#F9FAFB", "fontFamily": FONT})


# ── Callbacks ────────────────────────────────────────────────────────────────

CHART_LAYOUT = dict(
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font_family=FONT,
    title_font_size=14,
    title_font_color="#111827",
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
    # ── KPIs ────────────────────────────────────────────────────────────
    s = get_summary().iloc[0]
    kpis = [
        kpi_card("Total Players", str(int(s["total_players"]))),
        kpi_card("Avg Points / Game", str(s["avg_ppg"]),  "#1D4ED8"),
        kpi_card("Avg Assists / Game", str(s["avg_apg"]), "#065F46"),
        kpi_card("Avg Rebounds / Game", str(s["avg_rpg"]), "#7C3AED"),
    ]

    # ── Top Scorers bar ─────────────────────────────────────────────────
    top = get_top_scorers()
    fig_scorers = px.bar(
        top,
        x="points_per_game", y="player_name", orientation="h",
        title="Top 15 Scorers — Points Per Game",
        labels={"points_per_game": "PPG", "player_name": ""},
        color="points_per_game",
        color_continuous_scale=[[0, "#BFDBFE"], [0.5, "#3B82F6"], [1, "#1E3A8A"]],
        custom_data=["team_abbreviation", "games_played"],
    )
    fig_scorers.update_traces(
        hovertemplate=(
            "<b>%{y}</b><br>"
            "%{customdata[0]}  |  %{x:.1f} PPG  |  %{customdata[1]} GP<extra></extra>"
        ),
        marker_line_width=0,
    )
    fig_scorers.update_layout(
        **CHART_LAYOUT,
        yaxis_categoryorder="total ascending",
        coloraxis_showscale=False,
        xaxis_title="Points Per Game",
    )

    # ── Team Efficiency scatter ──────────────────────────────────────────
    eff = get_team_efficiency()
    fig_team = px.scatter(
        eff,
        x="avg_fg_pct", y="avg_team_ppg",
        size="roster_size", text="team_abbreviation",
        title="Team Efficiency — Avg PPG vs Field Goal %",
        labels={"avg_fg_pct": "Field Goal %", "avg_team_ppg": "Avg PPG",
                "roster_size": "Roster Size"},
        color="avg_team_ppg",
        color_continuous_scale=[[0, "#A7F3D0"], [0.5, "#10B981"], [1, "#064E3B"]],
        size_max=28,
        custom_data=["team_abbreviation", "roster_size"],
    )
    fig_team.update_traces(
        textposition="top center",
        marker_line_width=0,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "PPG: %{y:.1f}  |  FG%: %{x:.3f}  |  "
            "Roster: %{customdata[1]}<extra></extra>"
        ),
    )
    fig_team.update_layout(
        **CHART_LAYOUT,
        coloraxis_showscale=False,
        xaxis_tickformat=".1%",
    )

    return kpis, fig_scorers, fig_team


if __name__ == "__main__":
    app.run(debug=True, port=8050)
