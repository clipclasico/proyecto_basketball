### Configura las variables de entorno DB_URL y DATA_DIR antes de ejecutar.

import os
import pandas as pd
from sqlalchemy import create_engine

DATA_DIR = r"C:\ruta\a\la\carpeta\con\los\CSVs"
DB_URL = "postgresql+psycopg2://usuario:contraseña@localhost:5432/proyecto_01"

RELEVANT_SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]
SEASON_STRINGS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]

engine = create_engine(DB_URL)

def path(filename):
    return os.path.join(DATA_DIR, filename)

def to_bool(series):
    mapping = {
        1: True, 0: False, "1": True, "0": False,
        "Y": True, "N": False, "y": True, "n": False,
        "True": True, "False": False, True: True, False: False,
    }
    return series.map(mapping).astype("boolean")

# 1. TEAM  (team.csv + team_attributes.csv)
def load_team():
    team = pd.read_csv(path("team.csv"))
    attrs = pd.read_csv(path("team_attributes.csv"))

    merged = team.merge(attrs, left_on="id", right_on="ID", how="left", suffixes=("", "_attr"))

    out = pd.DataFrame({
        "team_id": merged["id"],
        "full_name": merged["full_name"],
        "abbreviation": merged["abbreviation"],
        "nickname": merged["nickname"],
        "city": merged["city"],
        "state": merged["state"],
        "year_founded": merged["year_founded"],
        "arena": merged["ARENA"],
        "arena_capacity": merged["ARENACAPACITY"],
        "owner": merged["OWNER"],
        "general_manager": merged["GENERALMANAGER"],
        "head_coach": merged["HEADCOACH"],
        "dleague_affiliation": merged["DLEAGUEAFFILIATION"],
        "facebook_website_link": merged["FACEBOOK_WEBSITE_LINK"],
        "instagram_website_link": merged["INSTAGRAM_WEBSITE_LINK"],
        "twitter_website_link": merged["TWITTER_WEBSITE_LINK"],
    })

    assert out["team_id"].is_unique, "team_id no es único, revisar team.csv"
    out.to_sql("team", engine, if_exists="append", index=False)
    print(f"  team: {len(out)} filas cargadas")

# 2. PLAYER  (player.csv + player_attributes.csv)
def load_player():
    player = pd.read_csv(path("player.csv"))
    attrs = pd.read_csv(path("player_attributes.csv"))

    merged = player.merge(attrs, left_on="id", right_on="ID", how="left", suffixes=("", "_attr"))

    out = pd.DataFrame({
        "player_id": merged["id"],
        "first_name": merged["first_name"],
        "last_name": merged["last_name"],
        "full_name": merged["full_name"],
        "is_active": to_bool(merged["is_active"]),
        "birthdate": pd.to_datetime(merged["BIRTHDATE"], errors="coerce"),
        "school": merged["SCHOOL"],
        "country": merged["COUNTRY"],
        "last_affiliation": merged["LAST_AFFILIATION"],
        "height": merged["HEIGHT"],
        "weight": pd.to_numeric(merged["WEIGHT"], errors="coerce"),
        "season_exp": pd.to_numeric(merged["SEASON_EXP"], errors="coerce"),
        "jersey": merged["JERSEY"],
        "position": merged["POSITION"],
        "roster_status": merged["ROSTERSTATUS"],
        "from_year": pd.to_numeric(merged["FROM_YEAR"], errors="coerce"),
        "to_year": pd.to_numeric(merged["TO_YEAR"], errors="coerce"),
        "dleague_flag": to_bool(merged["DLEAGUE_FLAG"]),
        "nba_flag": to_bool(merged["NBA_FLAG"]),
        "games_played_flag": to_bool(merged["GAMES_PLAYED_CURRENT_SEASON_FLAG"]),
        "all_star_appearances": pd.to_numeric(merged["ALL_STAR_APPEARANCES"], errors="coerce"),
        "team_id": pd.to_numeric(merged["TEAM_ID"], errors="coerce"),
    })

    assert out["player_id"].is_unique, "player_id no es único, revisar player.csv"

    valid_team_ids = set(pd.read_sql("SELECT team_id FROM team", engine)["team_id"])
    invalid_mask = out["team_id"].notna() & ~out["team_id"].isin(valid_team_ids)
    n_invalid = invalid_mask.sum()
    if n_invalid > 0:
        invalid_ids = sorted(out.loc[invalid_mask, "team_id"].unique())
        print(f"  [!] {n_invalid} jugadores con team_id que no existe en 'team' "
              f"(franquicias históricas/D-League). Se ponen en NULL: {invalid_ids}")
        out.loc[invalid_mask, "team_id"] = pd.NA

    out.to_sql("player", engine, if_exists="append", index=False)
    print(f"  player: {len(out)} filas cargadas")

# 3. TEAM_HISTORY
def load_team_history():
    df = pd.read_csv(path("team_history.csv"))
    out = pd.DataFrame({
        "team_id": df["ID"],
        "city": df["CITY"],
        "nickname": df["NICKNAME"],
        "year_founded": df["YEARFOUNDED"],
        "year_active_till": df["YEARACTIVETILL"],
    })
    out.to_sql("team_history", engine, if_exists="append", index=False)
    print(f"  team_history: {len(out)} filas cargadas")

# 4. TEAM_SALARY
def load_team_salary():
    df = pd.read_csv(path("team_salary.csv"))
    team_ref = pd.read_sql("SELECT team_id, full_name, abbreviation FROM team", engine)

    season_cols = [c for c in df.columns if c.startswith("X20")]
    long_df = df.melt(
        id_vars=["nameTeam", "slugTeam", "urlTeamSalaryHoopsHype"],
        value_vars=season_cols,
        var_name="season_raw",
        value_name="salary",
    )
    long_df["season"] = long_df["season_raw"].str.replace("X", "", regex=False)

    long_df = long_df.merge(
        team_ref[["team_id", "full_name"]],
        left_on="nameTeam", right_on="full_name", how="left"
    )

    no_match = long_df[long_df["team_id"].isna()]
    if len(no_match) > 0:
        print(f"  [!] {no_match['nameTeam'].nunique()} equipos de team_salary no calzaron por nombre:")
        print(no_match["nameTeam"].unique())
        print("      Revisa manualmente y ajusta el match (ej. usando abbreviation/slugTeam).")

    out = long_df.dropna(subset=["team_id"])[["team_id", "season", "salary"]].copy()
    out["team_id"] = out["team_id"].astype(int)
    out["source_url"] = long_df["urlTeamSalaryHoopsHype"]

    out.to_sql("team_salary", engine, if_exists="append", index=False)
    print(f"  team_salary: {len(out)} filas cargadas (de {len(long_df)} posibles)")

# 5. GAME
def load_game():
    df = pd.read_csv(path("game.csv"), low_memory=False)
    before_filter = len(df)
    df = df[df["SEASON"].isin(RELEVANT_SEASONS)].copy()
    print(f"  [filter] game.csv: {before_filter} filas totales -> {len(df)} "
          f"filas en temporadas {RELEVANT_SEASONS}")

    mismatch_home = (df["TEAM_ID_HOME"] != df["HOME_TEAM_ID"]).sum()
    mismatch_away = (df["TEAM_ID_AWAY"] != df["VISITOR_TEAM_ID"]).sum()
    print(f"  [check] filas donde TEAM_ID_HOME != HOME_TEAM_ID: {mismatch_home} "
          f"(se usa TEAM_ID_HOME, verificado como correcto vs TEAM_NAME_HOME)")
    print(f"  [check] filas donde TEAM_ID_AWAY != VISITOR_TEAM_ID: {mismatch_away}")

    dup_mask = df.duplicated(subset="GAME_ID", keep=False)
    if dup_mask.any():
        n_ids = df.loc[dup_mask, "GAME_ID"].nunique()
        non_identical = []
        for gid, group in df[dup_mask].groupby("GAME_ID"):
            if group.drop_duplicates().shape[0] > 1:
                non_identical.append(gid)
        if non_identical:
            print(f"  [!] {len(non_identical)} GAME_ID duplicados con datos DISTINTOS "
                  f"entre copias (revisar manualmente): {non_identical}")
        else:
            print(f"  [check] {n_ids} GAME_ID duplicados, copias idénticas en todo -> "
                  f"se descarta la copia repetida")
        df = df.drop_duplicates(subset="GAME_ID", keep="first")

    out = pd.DataFrame({
        "game_id": df["GAME_ID"],
        "season_id": pd.to_numeric(df["SEASON_ID"], errors="coerce"),
        "season": df["SEASON"],
        "game_date": pd.to_datetime(df["GAME_DATE"], errors="coerce"),
        "home_team_id": df["TEAM_ID_HOME"],
        "away_team_id": df["TEAM_ID_AWAY"],
        "game_status_id": pd.to_numeric(df["GAME_STATUS_ID"], errors="coerce"),
        "game_status_text": df["GAME_STATUS_TEXT"],
        "game_code": df["GAMECODE"],
        "wl_home": df["WL_HOME"],
        "wl_away": df["WL_AWAY"],
        "min_home": pd.to_numeric(df["MIN_HOME"], errors="coerce"),
        "min_away": pd.to_numeric(df["MIN_AWAY"], errors="coerce"),
        "fgm_home": df["FGM_HOME"], "fga_home": df["FGA_HOME"], "fg_pct_home": df["FG_PCT_HOME"],
        "fg3m_home": df["FG3M_HOME"], "fg3a_home": df["FG3A_HOME"], "fg3_pct_home": df["FG3_PCT_HOME"],
        "ftm_home": df["FTM_HOME"], "fta_home": df["FTA_HOME"], "ft_pct_home": df["FT_PCT_HOME"],
        "oreb_home": df["OREB_HOME"], "dreb_home": df["DREB_HOME"], "reb_home": df["REB_HOME"],
        "ast_home": df["AST_HOME"], "stl_home": df["STL_HOME"], "blk_home": df["BLK_HOME"],
        "tov_home": df["TOV_HOME"], "pf_home": df["PF_HOME"], "pts_home": df["PTS_HOME"],
        "plus_minus_home": df["PLUS_MINUS_HOME"],
        "fgm_away": df["FGM_AWAY"], "fga_away": df["FGA_AWAY"], "fg_pct_away": df["FG_PCT_AWAY"],
        "fg3m_away": df["FG3M_AWAY"], "fg3a_away": df["FG3A_AWAY"], "fg3_pct_away": df["FG3_PCT_AWAY"],
        "ftm_away": df["FTM_AWAY"], "fta_away": df["FTA_AWAY"], "ft_pct_away": df["FT_PCT_AWAY"],
        "oreb_away": df["OREB_AWAY"], "dreb_away": df["DREB_AWAY"], "reb_away": df["REB_AWAY"],
        "ast_away": df["AST_AWAY"], "stl_away": df["STL_AWAY"], "blk_away": df["BLK_AWAY"],
        "tov_away": df["TOV_AWAY"], "pf_away": df["PF_AWAY"], "pts_away": df["PTS_AWAY"],
        "plus_minus_away": df["PLUS_MINUS_AWAY"],
        "pts_paint_home": df["PTS_PAINT_HOME"], "pts_2nd_chance_home": df["PTS_2ND_CHANCE_HOME"],
        "pts_fast_break_home": df["PTS_FB_HOME"], "largest_lead_home": df["LARGEST_LEAD_HOME"],
        "lead_changes_home": df["LEAD_CHANGES_HOME"], "times_tied_home": df["TIMES_TIED_HOME"],
        "team_turnovers_home": df["TEAM_TURNOVERS_HOME"], "total_turnovers_home": df["TOTAL_TURNOVERS_HOME"],
        "team_rebounds_home": df["TEAM_REBOUNDS_HOME"], "pts_off_turnovers_home": df["PTS_OFF_TO_HOME"],
        "pts_paint_away": df["PTS_PAINT_AWAY"], "pts_2nd_chance_away": df["PTS_2ND_CHANCE_AWAY"],
        "pts_fast_break_away": df["PTS_FB_AWAY"], "largest_lead_away": df["LARGEST_LEAD_AWAY"],
        "lead_changes_away": df["LEAD_CHANGES_AWAY"], "times_tied_away": df["TIMES_TIED_AWAY"],
        "team_turnovers_away": df["TEAM_TURNOVERS_AWAY"], "total_turnovers_away": df["TOTAL_TURNOVERS_AWAY"],
        "team_rebounds_away": df["TEAM_REBOUNDS_AWAY"], "pts_off_turnovers_away": df["PTS_OFF_TO_AWAY"],
        "pts_qtr1_home": df["PTS_QTR1_HOME"], "pts_qtr2_home": df["PTS_QTR2_HOME"],
        "pts_qtr3_home": df["PTS_QTR3_HOME"], "pts_qtr4_home": df["PTS_QTR4_HOME"],
        "pts_ot1_home": df["PTS_OT1_HOME"], "pts_ot2_home": df["PTS_OT2_HOME"],
        "pts_ot3_home": df["PTS_OT3_HOME"], "pts_ot4_home": df["PTS_OT4_HOME"],
        "pts_ot5_home": df["PTS_OT5_HOME"], "pts_ot6_home": df["PTS_OT6_HOME"],
        "pts_ot7_home": df["PTS_OT7_HOME"], "pts_ot8_home": df["PTS_OT8_HOME"],
        "pts_ot9_home": df["PTS_OT9_HOME"], "pts_ot10_home": df["PTS_OT10_HOME"],
        "pts_qtr1_away": df["PTS_QTR1_AWAY"], "pts_qtr2_away": df["PTS_QTR2_AWAY"],
        "pts_qtr3_away": df["PTS_QTR3_AWAY"], "pts_qtr4_away": df["PTS_QTR4_AWAY"],
        "pts_ot1_away": df["PTS_OT1_AWAY"], "pts_ot2_away": df["PTS_OT2_AWAY"],
        "pts_ot3_away": df["PTS_OT3_AWAY"], "pts_ot4_away": df["PTS_OT4_AWAY"],
        "pts_ot5_away": df["PTS_OT5_AWAY"], "pts_ot6_away": df["PTS_OT6_AWAY"],
        "pts_ot7_away": df["PTS_OT7_AWAY"], "pts_ot8_away": df["PTS_OT8_AWAY"],
        "pts_ot9_away": df["PTS_OT9_AWAY"], "pts_ot10_away": df["PTS_OT10_AWAY"],
        "attendance": pd.to_numeric(df["ATTENDANCE"], errors="coerce"),
        "game_time": df["GAME_TIME"],
    })

    assert out["game_id"].is_unique, "game_id no es único, revisar game.csv"

    valid_team_ids = set(pd.read_sql("SELECT team_id FROM team", engine)["team_id"])
    bad_mask = ~out["home_team_id"].isin(valid_team_ids) | ~out["away_team_id"].isin(valid_team_ids)
    if bad_mask.sum() > 0:
        print(f"  [!] {bad_mask.sum()} partidos con team_id inválido incluso dentro de la "
              f"ventana filtrada. Se descartan: {out.loc[bad_mask, 'game_id'].tolist()}")
        out = out[~bad_mask]

    out.to_sql("game", engine, if_exists="append", index=False)
    print(f"  game: {len(out)} filas cargadas")

# 6. PLAYER_SALARY
def load_player_salary():
    df = pd.read_csv(path("player_salary.csv"))

    before_filter = len(df)
    df = df[df["slugSeason"].isin(SEASON_STRINGS)].copy()
    print(f"  [filter] player_salary.csv: {before_filter} filas totales -> "
          f"{len(df)} filas en temporadas {SEASON_STRINGS}")

    player_ref = pd.read_sql("SELECT player_id, full_name FROM player", engine)
    team_ref = pd.read_sql("SELECT team_id, full_name AS team_full_name FROM team", engine)

    merged = df.merge(player_ref, left_on="namePlayer", right_on="full_name", how="left")
    merged = merged.merge(team_ref, left_on="nameTeam", right_on="team_full_name", how="left")

    unmatched_players = merged[merged["player_id"].isna()]["namePlayer"].unique()
    unmatched_teams = merged[merged["team_id"].isna()]["nameTeam"].unique()
    if len(unmatched_players) > 0:
        print(f"  [!] {len(unmatched_players)} jugadores no calzaron por nombre (revisar manual/fuzzy match):")
        print(unmatched_players[:20], "..." if len(unmatched_players) > 20 else "")
    if len(unmatched_teams) > 0:
        print(f"  [!] {len(unmatched_teams)} equipos no calzaron por nombre:")
        print(unmatched_teams)

    out = pd.DataFrame({
        "player_id": merged["player_id"],
        "team_id": merged["team_id"],
        "season": merged["slugSeason"],
        "salary": pd.to_numeric(merged["value"], errors="coerce"),
        "status": merged["statusPlayer"],
        "contract_detail": merged["typeContractDetail"],
        "is_final_season": to_bool(merged["isFinalSeason"]),
        "is_waived": to_bool(merged["isWaived"]),
        "is_on_roster": to_bool(merged["isOnRoster"]),
        "is_non_guaranteed": to_bool(merged["isNonGuaranteed"]),
        "is_team_option": to_bool(merged["isTeamOption"]),
        "is_player_option": to_bool(merged["isPlayerOption"]),
    })

    before = len(out)
    out = out.dropna(subset=["player_id"])
    out["player_id"] = out["player_id"].astype(int)
    print(f"  player_salary: {len(out)}/{before} filas con player_id resuelto, cargando...")

    out.to_sql("player_salary", engine, if_exists="append", index=False)
    print(f"  player_salary: {len(out)} filas cargadas")

# 7. DRAFT
def load_draft():
    df = pd.read_csv(path("draft.csv"))

    out = pd.DataFrame({
        "draft_year": df["yearDraft"],
        "pick_overall": df["numberPickOverall"],
        "round_number": df["numberRound"],
        "round_pick": df["numberRoundPick"],
        "player_id": pd.to_numeric(df["idPlayer"], errors="coerce"),
        "team_id": pd.to_numeric(df["idTeam"], errors="coerce"),
        "organization_from": df["nameOrganizationFrom"],
        "organization_type": df["typeOrganizationFrom"],
        "organization_type_slug": df["slugOrganizationTypeFrom"],
        "organization_location": df["locationOrganizationFrom"],
    })

    dup = out.duplicated(subset=["draft_year", "pick_overall"]).sum()
    if dup > 0:
        print(f"  [!] {dup} filas duplicadas en (draft_year, pick_overall), se eliminan antes de insertar")
        out = out.drop_duplicates(subset=["draft_year", "pick_overall"])

    valid_player_ids = set(pd.read_sql("SELECT player_id FROM player", engine)["player_id"])
    invalid_mask = out["player_id"].notna() & ~out["player_id"].isin(valid_player_ids)
    n_invalid = invalid_mask.sum()
    if n_invalid > 0:
        print(f"  [!] {n_invalid} picks de draft con player_id que no existe en 'player' "
              f"(nunca jugaron en la NBA). Se ponen en NULL.")
        out.loc[invalid_mask, "player_id"] = pd.NA

    valid_team_ids = set(pd.read_sql("SELECT team_id FROM team", engine)["team_id"])
    invalid_team_mask = out["team_id"].notna() & ~out["team_id"].isin(valid_team_ids)
    n_invalid_team = invalid_team_mask.sum()
    if n_invalid_team > 0:
        print(f"  [!] {n_invalid_team} picks de draft con team_id de franquicia histórica "
              f"que no existe en 'team'. Se ponen en NULL.")
        out.loc[invalid_team_mask, "team_id"] = pd.NA

    out.to_sql("draft", engine, if_exists="append", index=False)
    print(f"  draft: {len(out)} filas cargadas")

# 8. GAME_INACTIVE_PLAYER
def load_game_inactive_player():
    df = pd.read_csv(path("game_inactive_players.csv"), low_memory=False)

    valid_game_ids = set(pd.read_sql("SELECT game_id FROM game", engine)["game_id"])
    before_filter = len(df)
    df = df[df["GAME_ID"].isin(valid_game_ids)].copy()
    print(f"  [filter] game_inactive_players.csv: {before_filter} filas totales -> "
          f"{len(df)} filas dentro de la ventana de temporadas cargada")

    valid_player_ids = set(pd.read_sql("SELECT player_id FROM player", engine)["player_id"])
    before_player_filter = len(df)
    df = df[df["PLAYER_ID"].isin(valid_player_ids)].copy()
    dropped = before_player_filter - len(df)
    if dropped > 0:
        print(f"  [!] {dropped} filas descartadas: player_id sin carrera real en 'player'")

    out = pd.DataFrame({
        "game_id": df["GAME_ID"],
        "player_id": df["PLAYER_ID"],
        "team_id": df["TEAM_ID"],
        "jersey_num": df["JERSEY_NUM"],
    })
    out = out.drop_duplicates(subset=["game_id", "player_id"])
    out.to_sql("game_inactive_player", engine, if_exists="append", index=False)
    print(f"  game_inactive_player: {len(out)} filas cargadas")

# 9 y 10. OFFICIAL + GAME_OFFICIAL
def load_officials():
    df = pd.read_csv(path("game_officials.csv"))

    valid_game_ids = set(pd.read_sql("SELECT game_id FROM game", engine)["game_id"])
    before_filter = len(df)
    df = df[df["GAME_ID"].isin(valid_game_ids)].copy()
    print(f"  [filter] game_officials.csv: {before_filter} filas totales -> "
          f"{len(df)} filas dentro de la ventana de temporadas cargada")

    officials = df[["OFFICIAL_ID", "FIRST_NAME", "LAST_NAME", "JERSEY_NUM"]].drop_duplicates(
        subset=["OFFICIAL_ID"]
    )
    officials_out = pd.DataFrame({
        "official_id": officials["OFFICIAL_ID"],
        "first_name": officials["FIRST_NAME"],
        "last_name": officials["LAST_NAME"],
        "jersey_num": officials["JERSEY_NUM"],
    })
    officials_out.to_sql("official", engine, if_exists="append", index=False)
    print(f"  official: {len(officials_out)} filas cargadas")

    game_official_out = df[["GAME_ID", "OFFICIAL_ID"]].drop_duplicates().rename(
        columns={"GAME_ID": "game_id", "OFFICIAL_ID": "official_id"}
    )
    game_official_out.to_sql("game_official", engine, if_exists="append", index=False)
    print(f"  game_official: {len(game_official_out)} filas cargadas")

def main():
    print("1) team..."); load_team()
    print("2) player..."); load_player()
    print("3) team_history..."); load_team_history()
    print("4) team_salary..."); load_team_salary()
    print("5) game..."); load_game()
    print("6) player_salary..."); load_player_salary()
    print("7) draft..."); load_draft()
    print("8) game_inactive_player..."); load_game_inactive_player()
    print("9-10) official + game_official..."); load_officials()
    print("\nCarga completa. player_season_stats queda pendiente: se llena con el")
    print("   script de nba_api que ya armamos (extraer_temporada_2025_26.py),")
    print("   ajustando las temporadas a las 6 relevantes de tu proyecto.")


if __name__ == "__main__":
    main()