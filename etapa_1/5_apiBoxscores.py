import time
import pandas as pd
from sqlalchemy import create_engine, text
from nba_api.stats.endpoints import boxscoresummaryv2, boxscoresummaryv3

DB_URL = "postgresql+psycopg2://usuario:contraseña@localhost:5432/proyecto_01"
PAUSE = 0.8
MAX_RETRIES = 3
RETRY_BACKOFF = 5
FLUSH_EVERY = 50

CUTOFF_DATE = pd.Timestamp("2025-04-10")

CHECKPOINT_FILE = "checkpoint_games.txt"
FAILED_FILE = "failed_games.txt"

engine = create_engine(DB_URL)


def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, "r") as f:
            return set(int(line.strip()) for line in f if line.strip())
    except FileNotFoundError:
        return set()


def append_checkpoint(game_ids):
    with open(CHECKPOINT_FILE, "a") as f:
        for gid in game_ids:
            f.write(f"{gid}\n")


def append_failed(game_id, error_msg):
    with open(FAILED_FILE, "a") as f:
        f.write(f"{game_id}\t{error_msg}\n")


def pad_game_id(game_id):
    return str(game_id).zfill(10)

def fetch_v2(game_id):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = boxscoresummaryv2.BoxScoreSummaryV2(game_id=pad_game_id(game_id))
            return resp.get_normalized_dict()
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF * attempt)


def parse_v2(game_id, data, home_id, away_id, official_ids_seen):
    officials_rows, game_official_rows, inactive_rows = [], [], []

    for off in data.get("Officials", []):
        oid = off["OFFICIAL_ID"]
        if oid not in official_ids_seen:
            officials_rows.append({
                "official_id": oid, "first_name": off["FIRST_NAME"],
                "last_name": off["LAST_NAME"], "jersey_num": off.get("JERSEY_NUM"),
            })
            official_ids_seen.add(oid)
        game_official_rows.append({"game_id": game_id, "official_id": oid})

    for inp in data.get("InactivePlayers", []):
        inactive_rows.append({
            "game_id": game_id, "player_id": inp["PLAYER_ID"],
            "team_id": inp["TEAM_ID"], "jersey_num": inp.get("JERSEY_NUM"),
        })

    update_params = None
    line_score = data.get("LineScore", [])
    other_stats = data.get("OtherStats", [])
    if len(line_score) == 2 and len(other_stats) == 2:
        ls = {r["TEAM_ID"]: r for r in line_score}
        os_ = {r["TEAM_ID"]: r for r in other_stats}
        h_ls, a_ls = ls.get(home_id), ls.get(away_id)
        h_os, a_os = os_.get(home_id), os_.get(away_id)
        if h_ls and a_ls and h_os and a_os:
            update_params = {
                "pts_qtr1_home": h_ls.get("PTS_QTR1"), "pts_qtr2_home": h_ls.get("PTS_QTR2"),
                "pts_qtr3_home": h_ls.get("PTS_QTR3"), "pts_qtr4_home": h_ls.get("PTS_QTR4"),
                "pts_qtr1_away": a_ls.get("PTS_QTR1"), "pts_qtr2_away": a_ls.get("PTS_QTR2"),
                "pts_qtr3_away": a_ls.get("PTS_QTR3"), "pts_qtr4_away": a_ls.get("PTS_QTR4"),
                "pts_paint_home": h_os.get("PTS_PAINT"), "pts_paint_away": a_os.get("PTS_PAINT"),
                "pts_2nd_chance_home": h_os.get("PTS_2ND_CHANCE"), "pts_2nd_chance_away": a_os.get("PTS_2ND_CHANCE"),
                "pts_fast_break_home": h_os.get("PTS_FB"), "pts_fast_break_away": a_os.get("PTS_FB"),
                "largest_lead_home": h_os.get("LARGEST_LEAD"), "largest_lead_away": a_os.get("LARGEST_LEAD"),
                "lead_changes_home": h_os.get("LEAD_CHANGES"), "lead_changes_away": a_os.get("LEAD_CHANGES"),
                "times_tied_home": h_os.get("TIMES_TIED"), "times_tied_away": a_os.get("TIMES_TIED"),
                "team_turnovers_home": h_os.get("TEAM_TURNOVERS"), "team_turnovers_away": a_os.get("TEAM_TURNOVERS"),
                "total_turnovers_home": h_os.get("TOTAL_TURNOVERS"), "total_turnovers_away": a_os.get("TOTAL_TURNOVERS"),
                "team_rebounds_home": h_os.get("TEAM_REBOUNDS"), "team_rebounds_away": a_os.get("TEAM_REBOUNDS"),
                "pts_off_turnovers_home": h_os.get("PTS_OFF_TO"), "pts_off_turnovers_away": a_os.get("PTS_OFF_TO"),
            }

    return officials_rows, game_official_rows, inactive_rows, update_params

def fetch_v3(game_id):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = boxscoresummaryv3.BoxScoreSummaryV3(game_id=pad_game_id(game_id))
            return resp.get_dict()["boxScoreSummary"]
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF * attempt)


def parse_v3(game_id, summary, official_ids_seen):
    officials_rows, game_official_rows, inactive_rows = [], [], []

    for off in summary.get("officials", []):
        oid = off["personId"]
        if oid not in official_ids_seen:
            officials_rows.append({
                "official_id": oid, "first_name": off["firstName"],
                "last_name": off["familyName"], "jersey_num": (off.get("jerseyNum") or "").strip() or None,
            })
            official_ids_seen.add(oid)
        game_official_rows.append({"game_id": game_id, "official_id": oid})

    home = summary.get("homeTeam", {})
    away = summary.get("awayTeam", {})
    home_id, away_id = home.get("teamId"), away.get("teamId")

    for inp in home.get("inactives", []):
        inactive_rows.append({
            "game_id": game_id, "player_id": inp["personId"],
            "team_id": home_id, "jersey_num": (inp.get("jerseyNum") or "").strip() or None,
        })
    for inp in away.get("inactives", []):
        inactive_rows.append({
            "game_id": game_id, "player_id": inp["personId"],
            "team_id": away_id, "jersey_num": (inp.get("jerseyNum") or "").strip() or None,
        })

    update_params = {}

    def periods_to_dict(periods, prefix):
        d = {}
        for p in periods:
            period_num = p["period"]
            score = p["score"]
            if period_num <= 4:
                d[f"pts_qtr{period_num}_{prefix}"] = score
            else:
                ot_num = period_num - 4
                if ot_num <= 10:
                    d[f"pts_ot{ot_num}_{prefix}"] = score
        return d

    update_params.update(periods_to_dict(home.get("periods", []), "home"))
    update_params.update(periods_to_dict(away.get("periods", []), "away"))

    return officials_rows, game_official_rows, inactive_rows, (update_params or None)


def build_update_sql(game_id, params):
    if not params:
        return None, {}
    set_clause = ", ".join(f"{col}=:{col}" for col in params)
    sql = text(f"UPDATE game SET {set_clause} WHERE game_id=:game_id")
    params = dict(params)
    params["game_id"] = game_id
    return sql, params


def main():
    games_df = pd.read_sql(
        "SELECT game_id, home_team_id, away_team_id, game_date FROM game ORDER BY game_id", engine
    )
    games_df["game_date"] = pd.to_datetime(games_df["game_date"])
    valid_player_ids = set(pd.read_sql("SELECT player_id FROM player", engine)["player_id"])
    official_ids_seen = set(pd.read_sql("SELECT official_id FROM official", engine)["official_id"])

    already_has_officials = set(
        pd.read_sql("SELECT DISTINCT game_id FROM game_official", engine)["game_id"]
    )
    done = load_checkpoint() | already_has_officials
    pending = games_df[~games_df["game_id"].isin(done)]

    n_v2 = (pending["game_date"] < CUTOFF_DATE).sum()
    n_v3 = (pending["game_date"] >= CUTOFF_DATE).sum()
    print(f"Total partidos en game: {len(games_df)}")
    print(f"Ya con officials cargados: {len(already_has_officials)}")
    print(f"Pendientes esta corrida: {len(pending)} ({n_v2} vía V2, {n_v3} vía V3)\n")

    buf_officials, buf_game_official, buf_inactive = [], [], []
    buf_updates = []
    buf_done_ids = []

    for i, row in enumerate(pending.itertuples(), start=1):
        game_id, home_id, away_id, game_date = row.game_id, row.home_team_id, row.away_team_id, row.game_date
        use_v3 = game_date >= CUTOFF_DATE

        try:
            if use_v3:
                data = fetch_v3(game_id)
                officials_rows, game_official_rows, inactive_rows, update_params = parse_v3(
                    game_id, data, official_ids_seen
                )
            else:
                data = fetch_v2(game_id)
                officials_rows, game_official_rows, inactive_rows, update_params = parse_v2(
                    game_id, data, home_id, away_id, official_ids_seen
                )
        except Exception as e:
            print(f"  [X] {game_id} ({'V3' if use_v3 else 'V2'}) falló tras {MAX_RETRIES} intentos, se sigue")
            append_failed(game_id, f"{'V3' if use_v3 else 'V2'}: {e}")
            continue

        inactive_rows = [r for r in inactive_rows if r["player_id"] in valid_player_ids]

        buf_officials.extend(officials_rows)
        buf_game_official.extend(game_official_rows)
        buf_inactive.extend(inactive_rows)

        sql, params = build_update_sql(game_id, update_params)
        if sql is not None:
            buf_updates.append((sql, params))

        buf_done_ids.append(game_id)

        if i % FLUSH_EVERY == 0 or i == len(pending):
            with engine.begin() as conn:
                if buf_officials:
                    pd.DataFrame(buf_officials).drop_duplicates(subset="official_id").to_sql(
                        "official", conn, if_exists="append", index=False
                    )
                if buf_game_official:
                    pd.DataFrame(buf_game_official).to_sql(
                        "game_official", conn, if_exists="append", index=False
                    )
                if buf_inactive:
                    pd.DataFrame(buf_inactive).to_sql(
                        "game_inactive_player", conn, if_exists="append", index=False
                    )
                for sql, params in buf_updates:
                    conn.execute(sql, params)

            append_checkpoint(buf_done_ids)
            print(f"  [{i}/{len(pending)}] flush: +{len(buf_officials)} officials, "
                  f"+{len(buf_game_official)} game_official, +{len(buf_inactive)} inactive, "
                  f"+{len(buf_updates)} game updates -- checkpoint guardado")

            buf_officials, buf_game_official, buf_inactive = [], [], []
            buf_updates = []
            buf_done_ids = []

        time.sleep(PAUSE)

    print("\nPARTE B completa.")
    print(f"Revisa {FAILED_FILE} si hay partidos que fallaron para reintentarlos aparte.")
    print("partidos desde 10/04/2025 NO tienen stats avanzados de equipo")

if __name__ == "__main__":
    main()