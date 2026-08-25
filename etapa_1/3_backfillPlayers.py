import time
import pandas as pd
from sqlalchemy import create_engine, text
from nba_api.stats.endpoints import leaguedashplayerstats, commonplayerinfo

DB_URL = "postgresql+psycopg2://usuario:contraseña@localhost:5432/proyecto_01"
SEASONS = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
SEASON_TYPE = "Regular Season"
PAUSE = 1.0
BIO_PAUSE = 0.7
MAX_RETRIES = 3

engine = create_engine(DB_URL)


def to_bool(series):
    mapping = {
        1: True, 0: False, "1": True, "0": False,
        "Y": True, "N": False, "y": True, "n": False,
        "True": True, "False": False, True: True, False: False,
    }
    return series.map(mapping).astype("boolean")


def get_all_season_stats():
    frames = []
    for season in SEASONS:
        print(f"  Jalando {season}...")
        resp = leaguedashplayerstats.LeagueDashPlayerStats(
            season=season, season_type_all_star=SEASON_TYPE, per_mode_detailed="PerGame"
        )
        df = resp.get_data_frames()[0]
        df["SEASON"] = season
        frames.append(df)
        time.sleep(PAUSE)
    return pd.concat(frames, ignore_index=True)


def fetch_player_bio(player_id):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
            df = info.get_data_frames()[0]
            if len(df) == 0:
                return None
            return df.iloc[0]
        except Exception as e:
            if attempt == MAX_RETRIES:
                print(f"    [X] player_id {player_id} falló tras {MAX_RETRIES} intentos: {e}")
                return None
            time.sleep(2 * attempt)


def main():
    print("1) Detectando jugadores faltantes en 'player'...")
    valid_player_ids = set(pd.read_sql("SELECT player_id FROM player", engine)["player_id"])
    raw = get_all_season_stats()
    missing_ids = sorted(set(raw["PLAYER_ID"]) - valid_player_ids)
    print(f"   {len(missing_ids)} jugadores nuevos a rellenar (debuts recientes, drafts post-2021)\n")

    if missing_ids:
        print("2) Trayendo bio completa de cada uno (commonplayerinfo)...")
        new_players = []
        for i, pid in enumerate(missing_ids, start=1):
            bio = fetch_player_bio(pid)
            if bio is not None:
                new_players.append(bio)
            if i % 25 == 0:
                print(f"   ...{i}/{len(missing_ids)}")
            time.sleep(BIO_PAUSE)

        bios_df = pd.DataFrame(new_players)
        print(f"   {len(bios_df)}/{len(missing_ids)} bios obtenidas exitosamente\n")

        out = pd.DataFrame({
            "player_id": bios_df["PERSON_ID"],
            "first_name": bios_df["FIRST_NAME"],
            "last_name": bios_df["LAST_NAME"],
            "full_name": bios_df["DISPLAY_FIRST_LAST"],
            "is_active": bios_df["ROSTERSTATUS"].map(lambda x: x == "Active"),
            "birthdate": pd.to_datetime(bios_df["BIRTHDATE"], errors="coerce"),
            "school": bios_df["SCHOOL"],
            "country": bios_df["COUNTRY"],
            "last_affiliation": bios_df["LAST_AFFILIATION"],
            "height": bios_df["HEIGHT"],
            "weight": pd.to_numeric(bios_df["WEIGHT"], errors="coerce"),
            "season_exp": pd.to_numeric(bios_df["SEASON_EXP"], errors="coerce"),
            "jersey": bios_df["JERSEY"],
            "position": bios_df["POSITION"],
            "roster_status": bios_df["ROSTERSTATUS"],
            "from_year": pd.to_numeric(bios_df["FROM_YEAR"], errors="coerce"),
            "to_year": pd.to_numeric(bios_df["TO_YEAR"], errors="coerce"),
            "dleague_flag": to_bool(bios_df["DLEAGUE_FLAG"]),
            "nba_flag": to_bool(bios_df["NBA_FLAG"]),
            "games_played_flag": to_bool(bios_df["GAMES_PLAYED_FLAG"]),
            "all_star_appearances": 0,  # commonplayerinfo no trae este dato; default 0
            "team_id": pd.to_numeric(bios_df["TEAM_ID"], errors="coerce").replace(0, pd.NA),
        })

        out = out[~out["player_id"].isin(valid_player_ids)].drop_duplicates(subset="player_id")

        out.to_sql("player", engine, if_exists="append", index=False)
        print(f"3) {len(out)} jugadores nuevos insertados en 'player'\n")
    else:
        print("2-3) No hay jugadores faltantes, se salta el backfill.\n")

    print("4) Recargando player_season_stats desde cero (ya no debería perder filas)...")
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE player_season_stats RESTART IDENTITY"))

    valid_player_ids_updated = set(pd.read_sql("SELECT player_id FROM player", engine)["player_id"])
    valid_team_ids = set(pd.read_sql("SELECT team_id FROM team", engine)["team_id"])

    out_stats = pd.DataFrame({
        "player_id": raw["PLAYER_ID"],
        "team_id": raw["TEAM_ID"],
        "season": raw["SEASON"],
        "gp": raw["GP"],
        "min": raw["MIN"],
        "pts": raw["PTS"],
        "ast": raw["AST"],
        "reb": raw["REB"],
        "stl": raw["STL"],
        "blk": raw["BLK"],
        "fg_pct": raw["FG_PCT"],
        "fg3_pct": raw["FG3_PCT"],
        "ft_pct": raw["FT_PCT"],
        "plus_minus": raw["PLUS_MINUS"],
    })

    still_missing = ~out_stats["player_id"].isin(valid_player_ids_updated)
    if still_missing.sum() > 0:
        print(f"   [!] {still_missing.sum()} filas todavía sin player_id válido "
              f"(bios que fallaron en el paso 2). Se descartan.")
        out_stats = out_stats[~still_missing]

    bad_team = out_stats["team_id"].notna() & ~out_stats["team_id"].isin(valid_team_ids)
    if bad_team.sum() > 0:
        out_stats.loc[bad_team, "team_id"] = pd.NA

    out_stats.to_sql("player_season_stats", engine, if_exists="append", index=False)
    print(f"\nplayer_season_stats: {len(out_stats)} filas cargadas (antes eran 1852).")


if __name__ == "__main__":
    main()