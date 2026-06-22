with source_data as (
    select
        player_id,
        player_name,
        team_abbreviation,
        gp as games_played,
        pts as total_points,
        ast as total_assists,
        reb as total_rebounds,
        fg_pct as field_goal_pct,
        ft_pct as free_throw_pct
    from {{ source('nba', 'player_stats_raw') }}
)

select
    source_data.*,
    case
        when games_played > 0 then round(total_points / games_played, 2)
        else 0
    end as points_per_game,
    case
        when games_played > 0 then round(total_assists / games_played, 2)
        else 0
    end as assists_per_game,
    case
        when games_played > 0 then round(total_rebounds / games_played, 2)
        else 0
    end as rebounds_per_game
from source_data
where games_played > 0
