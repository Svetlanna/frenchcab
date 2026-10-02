from __future__ import annotations 
 
import argparse 
import sqlite3 
import time 
from pathlib import Path 
 
import pandas as pd 
 
 
BASE_DIR = Path(__file__).resolve().parent.parent  # backend/ 
DEFAULT_DB = BASE_DIR / "data" / "frenchcab.db" 
DEFAULT_ZONES_CSV = BASE_DIR / "data" / "taxi_zone_lookup.csv" 
DEFAULT_TRAJETS_CSV = BASE_DIR / "data" / "clean" / "yellow_tripdata_2023.csv" 
 
TABLE_ZONES = "localisations" 
TABLE_TRAJETS = "trajets" 
 
# ordre des colonnes du CSV -> ordre des colonnes de la table localisations 
ZONES_CSV_COLS = ["LocationID", "Borough", "Zone", "service_zone"] 
DATE_COLS = ["tpep_pickup_datetime", "tpep_dropoff_datetime"] 
 
 
# ------ connexion 
 
def connect(db_path: Path) -> sqlite3.Connection: 
    if not db_path.exists(): 
        raise FileNotFoundError(f"Base introuvable : {db_path}") 
    conn = sqlite3.connect(db_path) 
    conn.execute("PRAGMA foreign_keys = ON") 
    return conn 
 
 
def table_columns(conn: sqlite3.Connection, table: str) -> list[str]: 
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")] 
    if not cols: 
        raise RuntimeError(f"La table '{table}' n'existe pas dans la base") 
    return cols 
 
 
def count(conn: sqlite3.Connection, table: str) -> int: 
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] 
 
 
# ------------------------------------------------------------ localisations 
 
def load_zones_csv(csv_path: Path) -> pd.DataFrame: 
    # keep_default_na=False : sinon pandas transforme "N/A" (zone 264/265) en NaN 
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False) 
    df = df[ZONES_CSV_COLS].apply(lambda s: s.str.strip()) 
    df["LocationID"] = pd.to_numeric(df["LocationID"], errors="coerce").astype("Int64") 
    df = df.dropna(subset=["LocationID"]).drop_duplicates(subset=["LocationID"]) 
    df = df.replace({"": None}) 
    return df 
 
 
def insert_zones(conn: sqlite3.Connection, csv_path: Path, replace: bool) -> None: 
    df = load_zones_csv(csv_path) 
    print(f"[{TABLE_ZONES}] {len(df)} zones lues depuis {csv_path}") 
 
    db_cols = table_columns(conn, TABLE_ZONES) 
    if len(db_cols) != len(ZONES_CSV_COLS): 
        raise RuntimeError( 
            f"{TABLE_ZONES} a {len(db_cols)} colonnes {db_cols}, " 
            f"le CSV en a {len(ZONES_CSV_COLS)}" 
        ) 
    print(f"[{TABLE_ZONES}] mapping csv -> table : {dict(zip(ZONES_CSV_COLS, db_cols))}") 
 
    cols_sql = ", ".join(db_cols) 
    placeholders = ", ".join("?" for _ in db_cols) 
    verb = "INSERT OR REPLACE" if replace else "INSERT OR IGNORE" 
    sql = f"{verb} INTO {TABLE_ZONES} ({cols_sql}) VALUES ({placeholders})" 
 
    rows = [ 
        (int(r.LocationID), r.Borough, r.Zone, r.service_zone) 
        for r in df.itertuples(index=False) 
    ] 
    with conn:  # commit auto, rollback si erreur 
        conn.executemany(sql, rows) 
 
    print(f"[{TABLE_ZONES}] {len(rows)} lignes envoyées, " 
          f"{count(conn, TABLE_ZONES)} lignes dans la table") 
 
 
def test_insert_zones(tmp_path: Path) -> None: 
    """Teste l'insertion des zones, avec et sans remplacement.""" 
    csv_path = tmp_path / "zones.csv" 
    csv_path.write_text( 
        "LocationID,Borough,Zone,service_zone\n" 
        "1,Manhattan,Nouvelle zone,Yellow\n" 
        "2,Brooklyn,Zone Brooklyn,Boro\n", 
        encoding="utf-8", 
    ) 
 
    conn = sqlite3.connect(":memory:") 
    try: 
        conn.execute( 
            "CREATE TABLE localisations " 
            "(LocationID INTEGER PRIMARY KEY, Borough TEXT, Zone TEXT, service_zone TEXT)" 
        ) 
        conn.execute( 
            "INSERT INTO localisations VALUES " 
            "(1, 'Manhattan', 'Zone existante', 'Yellow')" 
        ) 
 
        insert_zones(conn, csv_path, replace=False) 
        assert conn.execute( 
            "SELECT Zone FROM localisations WHERE LocationID = 1" 
        ).fetchone() == ("Zone existante",) 
        assert conn.execute( 
            "SELECT Zone FROM localisations WHERE LocationID = 2" 
        ).fetchone() == ("Zone Brooklyn",) 
 
        insert_zones(conn, csv_path, replace=True) 
        assert conn.execute( 
            "SELECT Zone FROM localisations WHERE LocationID = 1" 
        ).fetchone() == ("Nouvelle zone",) 
    finally: 
        conn.close() 
 
 
# ------------------------------------------------------------------ trajets 
 
def insert_trajets(conn: sqlite3.Connection, csv_path: Path, mode: str, 
                   chunksize: int) -> None: 
    if not csv_path.exists(): 
        raise FileNotFoundError(f"CSV introuvable : {csv_path} (lancer extraction.py avant)") 
 
    t0 = time.time() 
    total = 0 
    # lecture par morceaux : le CSV fait plusieurs millions de lignes 
    reader = pd.read_csv(csv_path, sep=",", encoding="utf-8-sig", 
                         chunksize=chunksize, parse_dates=DATE_COLS) 
    with conn: 
        for i, chunk in enumerate(reader, 1): 

            # Ajout clé primaire avec ID unique
            start_id = total + 1
            chunk.insert(
                  0,
                 "uid_trajet",
                 range(start_id, start_id + len(chunk))
            )

            # 1er morceau : "replace" recrée la table ; ensuite on ajoute 
            if_exists = mode if i == 1 else "append" 
            chunk.to_sql(TABLE_TRAJETS, conn, if_exists=if_exists, 
                         index=False, chunksize=10_000) 
            total += len(chunk) 
            print(f"[{TABLE_TRAJETS}] chunk {i:>4} | insérées {total:>12,} " 
                  f"| {time.time() - t0:6.0f}s", flush=True) 
 
    print(f"[{TABLE_TRAJETS}] {total:,} lignes envoyées, " 
          f"{count(conn, TABLE_TRAJETS):,} lignes dans la table") 
 
 
# --------------------------------------------------------------------- main 
 
def main() -> None: 
    p = argparse.ArgumentParser(description="csv -> frenchcab.db (localisations + trajets)") 
    p.add_argument("--db", type=Path, default=DEFAULT_DB) 
    p.add_argument("--zones-csv", type=Path, default=DEFAULT_ZONES_CSV) 
    p.add_argument("--trajets-csv", type=Path, default=DEFAULT_TRAJETS_CSV) 
    p.add_argument("--only", choices=["localisations", "trajets"], 
                   help="ne charger qu'une seule table") 
    p.add_argument("--replace-zones", action="store_true", 
                   help="écraser les zones existantes (sinon on les ignore)") 
    p.add_argument("--trajets-mode", choices=["replace", "append"], default="replace", 
                   help="replace = recrée la table trajets, append = ajoute à la fin") 
    p.add_argument("--chunksize", type=int, default=500_000) 
    a = p.parse_args() 
 
    conn = connect(a.db) 
    try: 
        if a.only in (None, "localisations"): 
            insert_zones(conn, a.zones_csv, a.replace_zones) 
        if a.only in (None, "trajets"): 
            insert_trajets(conn, a.trajets_csv, a.trajets_mode, a.chunksize) 
        print(f"Données enregistrées dans {a.db}") 
    except Exception as e: 
        print(f"Erreur : {e}") 
        raise 
    finally: 
        conn.close() 
 
 
if __name__ == "__main__": 
    main()