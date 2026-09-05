-- 5.1 Temporada con más partidos
select season, count(*) as cantidad_partidos
from game_history
group by season
order by cantidad_partidos desc
limit 10;

-- 5.2 Temporada que más se prolongó
select season, min(game_date) as primer_partido, max(game_date) as ultimo_partido, max(game_date) - min (game_date) as dias_de_duracion
from game_history
group by season
order by dias_de_duracion desc
limit 1;

-- 6. Equipo con mayor diferencia de puntos a favor en promedio por partido

select distinct on (p.season)
    p.season, t.full_name as equipo, round(p.diferencia_promedio, 2) as diferencia_promedio
from (
    select season, team_id, avg(diferencia) as diferencia_promedio
    from (
        select season, home_team_id as team_id, pts_home - pts_away as diferencia
        from game
        union all
        select season, away_team_id as team_id, pts_away - pts_home as diferencia
        from game
    ) diferencias
    where season in ('2022-23', '2023-24')
    group by season, team_id
) p
join team t on t.team_id = p.team_id
order by p.season, p.diferencia_promedio desc;