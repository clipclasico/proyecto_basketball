-- 7. Jugador más valioso del draft 2018, hoy en día (temporada 2025-26)
select
    p.full_name as jugador, d.pick_overall, pss.pts, pss.ast, pss.reb, (pss.pts + pss.ast + pss.reb) as valor_total
from draft d
join player p on p.player_id = d.player_id
join player_season_stats pss on pss.player_id = d.player_id and pss.season = '2025-26'
where d.draft_year = 2018
order by valor_total desc
limit 1;

-- 8. Top 5 estados que más salarios pagaron (temporadas 2020-21 y 2021-22)
select t.state, sum(ts.salary) as salario_total
from team_salary ts
join team t on t.team_id = ts.team_id
where ts.season in ('2020-21', '2021-22')
and t.state is not null
group by t.state
order by salario_total desc
limit 5;