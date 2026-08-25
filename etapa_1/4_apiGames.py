import time
import pandas as pd
from sqlalchemy import create_engine
from nba_api.stats.endpoints import leaguegamelog

DB_URL = "postgresql+psycopg2://usuario:contraseña@localhost:5432/proyecto_01"
SEASONS = ["2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
SEASON_TYPE = "Regular Season"
PAUSE = 1.2

engine = create_engine(DB_URL)


def season_to_season_id(season: str) -> int:
    """'2021-22' -> 22021 (mismo formato que ya usamos en el resto del ETL)"""
    year_inicio = season.split("-")[0]
    return int(f"2{year_inicio}")


def get_season_games(season):
    resp = leaguegamelog.LeagueGameLog(
        season=season,
        season_type_all_star=SEASON_TYPE,
        player_or_team_abbreviation="T",
    )
    return resp.get_data_frames()[0]


def build_game_rows(raw, season):
    """Convierte 2 filas por partido (una por equipo) en 1 fila home/away,
    igual que el schema de la tabla game."""
    rows = []
    for game_id, group in raw.groupby("GAME_ID"):
        if len(group) != 2:
            continue
        home = group[group["MATCHUP"].str.contains("vs.", regex=False)]
        away = group[group["MATCHUP"].str.contains("@", regex=False)]
        if len(home) != 1 or len(away) != 1:
            continue
        home, away = home.iloc[0], away.iloc[0]

        rows.append({
            "game_id": int(game_id),
            "season_id": season_to_season_id(season),
            "season": season,
            "game_date": home["GAME_DATE"],
            "home_team_id": home["TEAM_ID"],
            "away_team_id": away["TEAM_ID"],
            "wl_home": home["WL"],
            "wl_away": away["WL"],
            "min_home": home["MIN"],
            "min_away": away["MIN"],
            "fgm_home": home["FGM"], "fga_home": home["FGA"], "fg_pct_home": home["FG_PCT"],
            "fg3m_home": home["FG3M"], "fg3a_home": home["FG3A"], "fg3_pct_home": home["FG3_PCT"],
            "ftm_home": home["FTM"], "fta_home": home["FTA"], "ft_pct_home": home["FT_PCT"],
            "oreb_home": home["OREB"], "dreb_home": home["DREB"], "reb_home": home["REB"],
            "ast_home": home["AST"], "stl_home": home["STL"], "blk_home": home["BLK"],
            "tov_home": home["TOV"], "pf_home": home["PF"], "pts_home": home["PTS"],
            "plus_minus_home": home["PLUS_MINUS"],
            "fgm_away": away["FGM"], "fga_away": away["FGA"], "fg_pct_away": away["FG_PCT"],
            "fg3m_away": away["FG3M"], "fg3a_away": away["FG3A"], "fg3_pct_away": away["FG3_PCT"],
            "ftm_away": away["FTM"], "fta_away": away["FTA"], "ft_pct_away": away["FT_PCT"],
            "oreb_away": away["OREB"], "dreb_away": away["DREB"], "reb_away": away["REB"],
            "ast_away": away["AST"], "stl_away": away["STL"], "blk_away": away["BLK"],
            "tov_away": away["TOV"], "pf_away": away["PF"], "pts_away": away["PTS"],
            "plus_minus_away": away["PLUS_MINUS"],
        })
    return pd.DataFrame(rows)


def main():
    valid_team_ids = set(pd.read_sql("SELECT team_id FROM team", engine)["team_id"])
    already_loaded = set(pd.read_sql("SELECT game_id FROM game", engine)["game_id"])

    all_frames = []
    for season in SEASONS:
        print(f"Descargando temporada {season}...")
        raw = get_season_games(season)
        built = build_game_rows(raw, season)
        print(f"  -> {len(built)} partidos construidos")
        all_frames.append(built)
        time.sleep(PAUSE)

    out = pd.concat(all_frames, ignore_index=True)

    before = len(out)
    out = out[~out["game_id"].isin(already_loaded)]
    print(f"\n{before} partidos totales, {len(out)} nuevos (no estaban ya en game)")

    bad_teams = ~out["home_team_id"].isin(valid_team_ids) | ~out["away_team_id"].isin(valid_team_ids)
    if bad_teams.sum() > 0:
        print(f"  [!] {bad_teams.sum()} partidos con team_id inválido, se descartan")
        out = out[~bad_teams]

    out.to_sql("game", engine, if_exists="append", index=False)
    print(f"\n game: {len(out)} filas nuevas cargadas.")
    print("Nota: quedan en NULL las columnas de detalle por cuarto/OT, stats")
    print("avanzados, attendance y game_time -- eso lo llena la PARTE B.")


if __name__ == "__main__":
    main()