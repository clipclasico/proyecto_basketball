import os
import pandas as pd
from sqlalchemy import create_engine

DATA_DIR = r"C:\ruta\a\la\carpeta\con\los\CSVs"
DB_URL = "postgresql+psycopg2://usuario:contraseña@localhost:5432/proyecto_01"

engine = create_engine(DB_URL)

df = pd.read_csv(
    os.path.join(DATA_DIR, "game.csv"),
    low_memory=False
)

out = pd.DataFrame({
    "game_id": df["GAME_ID"],
    "season": pd.to_numeric(df["SEASON"], errors="coerce"),
    "game_date": pd.to_datetime(df["GAME_DATE"], errors="coerce")
})

out = out.dropna(subset=["game_id", "season", "game_date"])

out = out.drop_duplicates(
    subset=["game_id"],
    keep="first"
)

out["game_id"] = out["game_id"].astype("int64")
out["season"] = out["season"].astype("int64")

out.to_sql(
    "game_history",
    engine,
    if_exists="append",
    index=False
)

print(f"{len(out)} partidos históricos cargados.")