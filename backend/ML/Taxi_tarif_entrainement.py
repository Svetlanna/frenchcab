from __future__ import annotations

import argparse
import sqlite3
import time
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder, TargetEncoder
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "frenchcab.db"
CHEMIN_MODELE_TARIF = Path(__file__).resolve().parent.parent / "modele" / "modele_frais_trajet.joblib"

from Taxi_PickupHour import (DEFAULT_DB, GRAINE, NOMS_ZONES, TABLE_TRAJETS, TABLE_ZONES, VARIABLES_CATEGORIELLES, VARIABLES_LOCATIONS, VARIABLES_NUMERIQUES, construire_variables, creer_pipeline, evaluer2)

def charger_donnees_tarif(db_path: Path, echantillon: int) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {TABLE_TRAJETS}").fetchone()[0]
        pas = max(1, total // echantillon) if echantillon else 1

        trajets = pd.read_sql_query(f"""
            SELECT total_amount, tip_amount, payment_type, RateCodeID, trip_distance, tpep_pickup_datetime, pickup_hour, pickup_weekday, pu_locationID, do_locationID
            FROM {TABLE_TRAJETS}
            WHERE uid_trajet % {pas} = 0
        """, conn)
        lieux = pd.read_sql_query(f"SELECT * FROM {TABLE_ZONES}", conn)

    lieux.columns = NOMS_ZONES
    df = trajets.merge(lieux.add_suffix("_dep"), how="left", left_on="pu_locationID", right_on="locationID_dep")
    df = df.merge(lieux.add_suffix("_arr"), how="left", left_on="do_locationID", right_on="locationID_arr")
    return df


def nettoyer_tarif(df: pd.DataFrame) -> pd.DataFrame:
    avant = len(df)

    df["prix_hors_pourboire"] = df["total_amount"] - df["tip_amount"].fillna(0)

    df = df.dropna(subset=["prix_hors_pourboire", "trip_distance", "pickup_hour"])
    df = df[df["payment_type"].isin([1, 2])]
    df = df[df["RateCodeID"] != 5]
    df = df[df["prix_hors_pourboire"].between(3, 300)]
    df = df[df["trip_distance"].between(0.01, 100)]
    df = df[~df["pu_locationID"].isin([264, 265]) & ~df["do_locationID"].isin([264, 265])]

    print(f"nettoyage : {avant:,} -> {len(df):,} courses")
    return df.copy()


def main() -> None:
    p = argparse.ArgumentParser(description="modèle de prix de course")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("echantillon", nargs="?", type=int, default=1_000_000)
    a = p.parse_args()
    t0 = time.time()

    df = charger_donnees_tarif(a.db, a.echantillon)
    df = nettoyer_tarif(df)
    df = construire_variables(df)

    colonnes = VARIABLES_NUMERIQUES + VARIABLES_CATEGORIELLES + VARIABLES_LOCATIONS
    X = df[colonnes]
    y = df["prix_hors_pourboire"]
    print(f"prix moyen = {y.mean():.2f} $ | médiane = {y.median():.2f} $")

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=GRAINE)

    print("baselines")
    naif = DummyRegressor(strategy="median").fit(X_train, y_train)
    evaluer2("baseline toujours la médiane", y_test, naif.predict(X_test))

    mediane_paire = y_train.groupby(X_train["trajet_zones"]).median()
    pred_paire = X_test["trajet_zones"].map(mediane_paire).fillna(y_train.median())
    evaluer2("baseline médiane par paire de zones", y_test, pred_paire)

    print("entrainement du gradient boosting")
    pipeline = creer_pipeline(VARIABLES_NUMERIQUES).fit(X_train, y_train)
    evaluer2("gradient boosting, train", y_train, pipeline.predict(X_train))
    evaluer2("gradient boosting, test", y_test, pipeline.predict(X_test))

    joblib.dump(pipeline, CHEMIN_MODELE_TARIF)
    print(f"Modèle sauvegardé : {CHEMIN_MODELE_TARIF} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()