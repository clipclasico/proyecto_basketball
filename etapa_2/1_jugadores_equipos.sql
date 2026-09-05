-- 1. Jugador más alto y más bajo actualmente

-- Corrección de formato de height encontrada durante el análisis
update player
set height = (split_part(height, '-', 1)::numeric * 12 + split_part(height, '-', 2)::numeric)::varchar
where height like '%-%';


-- 1a. Jugador activo más alto
select full_name, height
from player
where height is not null
and is_active = True
order by height::numeric desc
limit 1;


-- 1b. Jugador activo más bajo
select full_name, height
from player
where height is not null
and is_active = True
order by height::numeric asc
limit 1;

-- 2. ¿Cuál fue el promedio de puntos anotados y recibidos por
-- cada equipo en cada una de las temporadas relevantes?
select t.full_name as equipo, tp.season as temporada, round(avg(tp.puntos_anotados), 2) as promedio_pts_anotados, round(avg(tp.puntos_recibidos), 2) as promedio_pts_recibidos
from (
	select season, home_team_id as team_id, pts_home as puntos_anotados, pts_away as puntos_recibidos from game 
	union all
	select season, away_team_id as team_id, pts_away as puntos_anotados, pts_home as puntos_recibidos from game
) tp 
join team t on t.team_id = tp.team_id 
group by t.full_name, tp.season 
order by tp.season, t.full_name;