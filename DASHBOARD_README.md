# NBA Analytics Dashboard

A live analytics dashboard built with Plotly Dash, powered by a dbt + DuckDB data pipeline.

## Features

- **Top Scorers** — horizontal bar chart ranking the top 15 scorers by PPG
- **Team Efficiency** — scatter plot of avg team PPG vs field goal %, sized by roster depth
- **League KPIs** — total players, avg PPG / APG / RPG across the league
- **Live Data** — updates nightly from NBA Stats API via GitHub Actions

## Tech Stack

| Layer | Tool |
|---|---|
| Dashboard | Plotly Dash |
| Database | DuckDB |
| Data pipeline | dbt |
| Deployment | Fly.io / Gunicorn |

## Local Development

```bash
pip install -r requirements.txt
python3 app.py
```

Visit [http://localhost:8050](http://localhost:8050)

## Deployment (Fly.io)

```bash
flyctl launch
flyctl deploy
```

## Data Pipeline

Data flows through three layers:

```
NBA Stats API
    └── scripts/fetch_nba_data.py   → data/player_stats_raw.csv
        └── dbt seed                → DuckDB raw.player_stats_raw
            └── dbt run             → DuckDB raw.stg_players  ← dashboard reads here
```

See the main [README.md](README.md) for full pipeline details.
