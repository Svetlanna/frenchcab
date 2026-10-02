
# charger les données
# la cible(trip_duration_min, déjà calculée)
# nettoyer(supprimer les courses absurdes)
# construire les variables
# séparer train/test
# modèles de référence (baselines)
# entraîner le vrai modèle (pipeline et gradient boosting)
# évaluer, interpréter, sauvegarder
#

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
from sklearn.preprocessing import OneHotEncoder, TargetEncoder #numéros de zone en nombres
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder



BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "frenchcab.db"
CHEMIN_MODELE = Path(__file__).resolve().parent / "modele_duree_trajet.joblib"

TABLE_ZONES = "localisations"
TABLE_TRAJETS = "trajets"
GRAINE = 42  # random_state mêmes résultats à chaque exécution


NOMS_ZONES = ["locationID", "quartier", "zone", "zone_service"]



def charger_donnees(db_path: Path, echantillon: int) -> pd.DataFrame:
    # seulement les colonnes utiles de 'trajets' (-échantillon,puis ajoute le quartier de départ et d'arrivée)

    if not db_path.exists():
        raise FileNotFoundError(f"Base introuvable  {db_path}")

    with sqlite3.connect(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM {TABLE_TRAJETS}").fetchone()[0]



        pas = max(1, total // echantillon) if echantillon else 1
        print(f" {total:,} trajets dans la base -> on en garde 1 sur {pas}")

        # on ne charge que les colonnes utiles, moins de mémoire
        # on  ne lit PAS fare_amount, tip_amount, total_amount...
        # (voir l'étape 4 : fuite de données).
        trajets = pd.read_sql_query(f"""
             SELECT trip_duration_min,
                    trip_distance,
                    pickup_hour,
                    pickup_weekday,
                    passenger_count,
                    RateCodeID,
                    vendorID,
                    pu_locationID,
                    do_locationID
             FROM {TABLE_TRAJETS}
             WHERE uid_trajet % {pas} = 0
         """, conn)

        lieux = pd.read_sql_query(f"SELECT * FROM {TABLE_ZONES}", conn)

    lieux.columns = NOMS_ZONES
    lieux = lieux[["locationID", "quartier", "zone_service"]]

    # JOINTURE (= LEFT JOIN en SQL), deux fois : départ puis arrivée.
    df = trajets.merge(lieux.add_suffix("_dep"), how="left",
                       left_on="pu_locationID", right_on="locationID_dep")
    df = df.merge(lieux.add_suffix("_arr"), how="left",
                  left_on="do_locationID", right_on="locationID_arr")

    return df


def nettoyer(df: pd.DataFrame) -> pd.DataFrame:
    avant = len(df)
    df = df.dropna(subset=["trip_duration_min", "trip_distance", "pickup_hour"])
    df = df[df["trip_duration_min"].between(1, 180)]  # 1 min à 3 h
    df = df[df["trip_distance"].between(0.01, 100)]  # en miles, > 0


    # 264 et 265 = "Unknown"
    df = df[~df["pu_locationID"].isin([264, 265]) & ~df["do_locationID"].isin([264, 265])]
    print(f"nettoyage : {avant:,} -> {len(df):,} courses")


    # vitesse moyenne en mph  > 80 en ville = erreur de compteur
    vitesse = df["trip_distance"] / (df["trip_duration_min"] / 60)
    df = df[vitesse <= 80].copy()

    return df


#features)

#seulement ce qu'on connait au moment du depart
# fare_amount, tip_amount, total_amount, tpep_dropoff_datetime
# sont connus apres la course -> les utiliser = fuite de données
VARIABLES_NUMERIQUES = ["trip_distance", "heure", "pickup_weekday",
                        "est_weekend", "passenger_count"]
VARIABLES_CATEGORIELLES = ["quartier_dep", "quartier_arr",
                           "zone_service_dep", "zone_service_arr",
                           "RateCodeID", "vendorID"]

VARIABLES_LOCATIONS = ["pu_locationID", "do_locationID", "trajet_zones"]


def construire_variables(df: pd.DataFrame) -> pd.DataFrame:
    # pickup_hour ex "HH:MM:00" on garde l'heure 0..23
    df["heure"] = df["pickup_hour"].str.slice(0, 2).astype(int)
    df["est_weekend"] = (df["pickup_weekday"] >= 5).astype(int)  # 5 = samedi, 6=dimanche
    # RateCodeID 99 et passenger_count 0 = "inconnu" ,c'était dans etl
    # on les garde, le modèle apprendra que ce sont des cas à part
    #codes numériques -> texte ("1.0" et "1")
    for col in ["RateCodeID", "vendorID"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(-1).astype(int)
    for col in VARIABLES_CATEGORIELLES:
        df[col] = df[col].fillna("inconnu").astype(str)
    df["trajet_zones"] = df["pu_locationID"].astype(str) + "_" + df["do_locationID"].astype(str)
    for col in ["pu_locationID", "do_locationID"]:
        df[col] = df[col].astype(str)


    return df


#pipeline(prétraitement + modèle dans un objet)
def creer_pipeline(numeriques: list[str]) -> Pipeline:
    pretraitement = ColumnTransformer([
        ("num", "passthrough", numeriques),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False),
         VARIABLES_CATEGORIELLES),
        # chaque zone est remplacée par la durée moyenne

        ("loc", TargetEncoder(target_type="continuous"),
         VARIABLES_LOCATIONS),
    ])
    modele = HistGradientBoostingRegressor(
        max_iter=300,  # nombre maximum d'arbres
        learning_rate=0.1,  # chaque arbre corrige 10 % de l'erreur restante
        max_leaf_nodes=31,  # taille de chaque arbre
        early_stopping=True,  # s'arrête quand il ne progresse plus
        random_state=GRAINE,
    )
    return Pipeline([("pretraitement", pretraitement), ("modele", modele)])


def evaluer(nom: str, y_vrai, y_pred) -> dict:
    mae = mean_absolute_error(y_vrai, y_pred)
    rmse = root_mean_squared_error(y_vrai, y_pred)
    r2 = r2_score(y_vrai, y_pred)
    print(f"  {nom:<36} mae = {mae:5.2f} min | rmse = {rmse:5.2f} min | r2 = {r2:5.3f}")
    return {"mae": mae, "rmse": rmse, "r2": r2}


def main() -> None:
    p = argparse.ArgumentParser(description="modèle de durée de trajet")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("echantillon", nargs="?", type=int, default=1_000_000,
                   help="nombre approximatif de courses à utiliser (0=toutes)")
    p.add_argument("--sans-distance", action="store_true",
                   help="prédire seulement avec les locations et l'heure "
                        "(cas réel : le client choisit départ + arrivée)")
    a = p.parse_args()
    t0 = time.time()

    df = charger_donnees(a.db, a.echantillon)
    df = nettoyer(df)
    df = construire_variables(df)
    print(df)
    numeriques = [c for c in VARIABLES_NUMERIQUES
                  if not (a.sans_distance and c == "trip_distance")]
    colonnes = numeriques + VARIABLES_CATEGORIELLES + VARIABLES_LOCATIONS
    X = df[colonnes]
    y = df["trip_duration_min"]
    print(f"durée moyenne = {y.mean():.1f} min | médiane = {y.median():.1f} min")

    # train / test -----------------------------------------------
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=GRAINE)
    print(f"train : {len(X_train):,} | test : {len(X_test):,}")

    # baselines
    print("baselines")
    naif = DummyRegressor(strategy="median").fit(X_train, y_train)
    evaluer("baseline toujours la médiane", y_test, naif.predict(X_test))

    # baseline "par location" : la durée médiane de chaque paire départ->arrivée
    mediane_paire = y_train.groupby(X_train["trajet_zones"]).median()
    pred_paire = X_test["trajet_zones"].map(mediane_paire).fillna(y_train.median())
    evaluer("baseline médiane par paire de zones", y_test, pred_paire)

    if not a.sans_distance:
        lineaire = LinearRegression().fit(X_train[["trip_distance"]], y_train)
        evaluer("baseline régression / distance", y_test,
                lineaire.predict(X_test[["trip_distance"]]))

    #  modèle ------------------------------------------------
    print("entrainement du gradient boosting")
    pipeline = creer_pipeline(numeriques).fit(X_train, y_train)

    # evaluation
    print("evaluation")
    evaluer("gradient boosting, train", y_train, pipeline.predict(X_train))
    evaluer("gradient boosting, test", y_test, pipeline.predict(X_test))

    ech = X_test.sample(min(5000, len(X_test)), random_state=GRAINE)
    imp = permutation_importance(pipeline, ech, y_test.loc[ech.index], n_repeats=5,
                                 random_state=GRAINE, scoring="neg_mean_absolute_error")
    print("importance (hausse de l'erreur quand on mélange la variable)")
    for nom, val in sorted(zip(X.columns, imp.importances_mean), key=lambda t: -t[1]):
        print(f"  {nom:<18} {val:+5.2f} min")

    joblib.dump(pipeline, CHEMIN_MODELE)
    print(f"Modèle sauvegardé : {CHEMIN_MODELE}  ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()