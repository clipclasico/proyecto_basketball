-- 3. Top 5 árbitros en cuyos juegos pitados el equipo visitante pierde
select o.official_id as id, o.first_name as nombre, o.last_name as apellido, count(*) as juegos_visitante_pierde
from game_official g_o
join official o on o.official_id = g_o.official_id
join game g on g.game_id = g_o.game_id
where g.wl_away = 'L'
group by o.official_id, o.first_name, o.last_name
order by juegos_visitante_pierde desc
limit 5;


-- 4a. Equipo con la nómina más alta en la temporada actual (2025-26)
select t.full_name as equipo, ts.salary as nomina_total
from team_salary ts
join team t on t.team_id = ts.team_id
where ts.season = '2025-26'
order by ts.salary desc
limit 1;

-- 4b. Comparar nómina vs. "valor" de jugadores por equipo (2025-26)
select t.full_name AS equipo, ts.salary AS nomina, v.valor_total
from team_salary ts
join team t on t.team_id = ts.team_id
join (
    select team_id, round(sum(pts + ast + reb), 2) as valor_total
    from player_season_stats
    where season = '2025-26'
    and team_id is not null
    group by team_id
) v on v.team_id = ts.team_id
where ts.season = '2025-26'
order by ts.salary desc;