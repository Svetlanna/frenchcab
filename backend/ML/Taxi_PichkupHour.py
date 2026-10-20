
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

import mlflow
import mlflow.sklearn


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB = BASE_DIR / "data" / "frenchcab.db"
CHEMIN_MODELE = BASE_DIR  /"modeles"/ "modele_v2_duree_trajet.joblib"

TABLE_ZONES = "localisations"
TABLE_TRAJETS = "trajets"
GRAINE = 42  # random_state mêmes résultats à chaque exécution


NOMS_ZONES = ["locationID", "quartier", "zone", "zone_service"]



def charger_donnees(db_path: Path, echantillon: int) -> pd.DataFrame:

    if not db_path.exists():
        raise FileNotFoundError(f"Base introuvable : {db_path}")

    with sqlite3.connect(db_path) as conn:

        total = conn.execute(f"SELECT COUNT(*) FROM {TABLE_TRAJETS}").fetchone()[0]

        pas = max(1, total // echantillon) if echantillon else 1

        print(
            f"{total:,} trajets dans la base "
            f"-> on en garde 1 sur {pas}"
        )

        # Données nécessaires à l'entraînement
        trajets = pd.read_sql_query(f"""
            SELECT
                trip_duration_min,
                trip_distance,
                tpep_pickup_datetime,
                pickup_hour,
                pickup_weekday,
                pu_locationID,
                do_locationID
            FROM {TABLE_TRAJETS}
            WHERE uid_trajet % {pas} = 0
        """, conn)

        # Informations géographiques
        lieux = pd.read_sql_query(f"SELECT * FROM {TABLE_ZONES}",conn)

    lieux.columns = NOMS_ZONES

    lieux = lieux[["locationID","quartier","zone","zone_service"]]

    # Informations du lieu de départ
    df = trajets.merge(
        lieux.add_suffix("_dep"),
        how="left",
        left_on="pu_locationID",
        right_on="locationID_dep"
    )

    # Informations du lieu d'arrivée
    df = df.merge(
        lieux.add_suffix("_arr"),
        how="left",
        left_on="do_locationID",
        right_on="locationID_arr"
    )

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
VARIABLES_NUMERIQUES = ["trip_distance", "heure", "pickup_weekday", "est_weekend", "mois"]
VARIABLES_CATEGORIELLES = ["quartier_dep", "quartier_arr", "zone_service_dep", "zone_service_arr"]
VARIABLES_LOCATIONS = ["pu_locationID", "do_locationID", "trajet_zones"]


def construire_variables(df: pd.DataFrame) -> pd.DataFrame:

    # -----------------------------
    # Date / heure
    # -----------------------------

    df["heure"] = (
        df["pickup_hour"]
        .astype(str)
        .str.slice(0, 2)
        .astype(int)
    )

    # Jour de la semaine : 0 = lundi  ... 5 = samedi 6 = dimanche
    df["est_weekend"] = (df["pickup_weekday"] >= 5).astype(int)

    # Mois récupéré depuis la date de départ
    df["tpep_pickup_datetime"] = pd.to_datetime(df["tpep_pickup_datetime"])

    df["mois"] = df["tpep_pickup_datetime"].dt.month


    # -----------------------------
    # Localisations
    # -----------------------------

    df["pu_locationID"] = (
        df["pu_locationID"]
        .fillna(-1)
        .astype(int)
        .astype(str)
    )

    df["do_locationID"] = (
        df["do_locationID"]
        .fillna(-1)
        .astype(int)
        .astype(str)
    )

    # Couple départ -> arrivée
    df["trajet_zones"] = (df["pu_locationID"] + "_"+ df["do_locationID"])


    # -----------------------------
    # Variables catégorielles
    # -----------------------------

    variables_categorielles = [
        "pu_locationID",
        "do_locationID",
        "trajet_zones",
        "quartier_dep",
        "quartier_arr",
        "zone_service_dep",
        "zone_service_arr",
    ]

    for col in variables_categorielles:
        df[col] = (
            df[col]
            .fillna("inconnu")
            .astype(str)
        )


    # -----------------------------
    # Distance
    # -----------------------------

    # À l'entraînement :
    # -> vraie distance du trajet
    #
    # À la prédiction :
    # -> distance moyenne historique
    #    départ -> arrivée

    df["trip_distance"] = pd.to_numeric(df["trip_distance"], errors="coerce")

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


def fmt_min_sec(minutes: float) -> str:
    total_sec = round(minutes * 60)
    m, s = divmod(total_sec, 60)
    return f"{m:2d} min {s:02d} s"


def evaluer(nom: str, y_vrai, y_pred) -> dict:
    mae = mean_absolute_error(y_vrai, y_pred)
    rmse = root_mean_squared_error(y_vrai, y_pred)
    r2 = r2_score(y_vrai, y_pred)

    print(
        f"  {nom:<36} mae = {fmt_min_sec(mae)} | "
        f"rmse = {fmt_min_sec(rmse)} | r2 = {r2:5.3f}"
    )
    return {"mae": mae, "rmse": rmse, "r2": r2}




def evaluer2(nom: str, y_vrai, y_pred) -> dict:
    mae = mean_absolute_error(y_vrai, y_pred)
    rmse = root_mean_squared_error(y_vrai, y_pred)
    r2 = r2_score(y_vrai, y_pred)
    print(f"  {nom:<36} mae = {mae:5.2f} $ | rmse = {rmse:5.2f} $ | r2 = {r2:5.3f}")
    return {"mae": mae, "rmse": rmse, "r2": r2}


def main() -> None:
    p = argparse.ArgumentParser(description="modèle de durée de trajet")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("echantillon",nargs="?", type=int, default=1_000_000, help="nombre approximatif de courses à utiliser (0=toutes)")
    # >>> NOUVEAU (1/3) : où enregistrer le modèle entraîné.
    # Par défaut, le même fichier qu'avant (comportement inchangé).
    # Le pipeline l'utilise pour écrire un modèle "candidat" SANS écraser
    # le modèle en production.
    p.add_argument("--sortie", type=Path, default=CHEMIN_MODELE,
                   help="fichier .joblib à écrire (défaut : modèle en production)")

    a = p.parse_args()
    
    # Configuration MLflow
    mlflow.set_tracking_uri("http://mlflow:5000")
    mlflow.set_experiment("FrenchCab - prediction duree v2")
    
    t0 = time.time()

    df = charger_donnees(a.db, a.echantillon)
    df = nettoyer(df)
    df = construire_variables(df)

    numeriques = VARIABLES_NUMERIQUES

    colonnes = (numeriques + VARIABLES_CATEGORIELLES + VARIABLES_LOCATIONS)

    X = df[colonnes]
    y = df["trip_duration_min"]

    print(
    f"durée moyenne = {fmt_min_sec(y.mean())} | "
    f"médiane = {fmt_min_sec(y.median())}"
)

    # train / test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=GRAINE)

    print(
        f"train : {len(X_train):,} | "
        f"test : {len(X_test):,}"
    )

    # # -------------------------
    # # Baselines
    # # -------------------------

    # print("baselines")
    # naif = DummyRegressor(strategy="median").fit(X_train, y_train)
    # evaluer("baseline toujours la médiane", y_test, naif.predict(X_test))

    # # Médiane historique par paire départ -> arrivée
    # mediane_paire = y_train.groupby(X_train["trajet_zones"]).median()

    # pred_paire = (
    #     X_test["trajet_zones"]
    #     .map(mediane_paire)
    #     .fillna(y_train.median())
    # )
    # evaluer("baseline médiane par paire de zones", y_test, pred_paire)

    # # Baseline distance
    # lineaire = LinearRegression().fit(X_train[["trip_distance"]], y_train)
    # evaluer("baseline régression / distance", y_test, lineaire.predict(X_test[["trip_distance"]]))

    # # -------------------------
    # # Modèle
    # # -------------------------

    # print("entrainement du gradient boosting")
    # pipeline = creer_pipeline(numeriques).fit(X_train, y_train)

    # # -------------------------
    # # Evaluation
    # # -------------------------

    # print("evaluation")
    # evaluer("gradient boosting, train", y_train, pipeline.predict(X_train))
    # metriques_test = evaluer("gradient boosting, test", y_test, pipeline.predict(X_test))

    # # -------------------------
    # # Importance des variables
    # # -------------------------

    # ech = X_test.sample(min(5000, len(X_test)), random_state=GRAINE)

    # imp = permutation_importance(pipeline, ech, y_test.loc[ech.index], n_repeats=5, random_state=GRAINE, scoring="neg_mean_absolute_error")

    # print("importance ""(hausse de l'erreur quand on mélange la variable)")

    # for nom, val in sorted(
    #     zip(X.columns, imp.importances_mean),
    #     key=lambda t: -t[1]
    # ):
    #     print(
    #         f"  {nom:<18} "
    #         f"{val:+5.2f} min"
    #     )

    # # -------------------------
    # # Sauvegarde
    # # -------------------------

    # joblib.dump(pipeline, CHEMIN_MODELE)

    # # identification du modèle : date d'entraînement + MAE sur le jeu de test
    # from datetime import datetime
    # from modele_info import ecrire_meta
    # ecrire_meta(
    #     CHEMIN_MODELE,
    #     date_entrainement=datetime.now().isoformat(timespec="seconds"),
    #     date_entrainement_source="entrainement",
    #     mae_test_minutes=round(float(metriques_test["mae"]), 3),
    #     lignes_entrainement=int(len(X_train)),
    # )

    # print(
    #     f"Modèle sauvegardé : {CHEMIN_MODELE} "
    #     f"({time.time() - t0:.0f}s)"
    # )


    # -------------------------
    # Expérience MLflow
    # -------------------------

    with mlflow.start_run(run_name="gradient-boosting-duree"):

        # Paramètres généraux
        mlflow.log_params({
            "echantillon_demande": a.echantillon,
            "graine": GRAINE,
            "test_size": 0.2,
            "modele": "HistGradientBoostingRegressor",
            "max_iter": 300,
            "learning_rate": 0.1,
            "max_leaf_nodes": 31,
            "early_stopping": True,
            "nombre_lignes_train": len(X_train),
            "nombre_lignes_test": len(X_test),
        })

        # -------------------------
        # Baselines
        # -------------------------

        print("baselines")
        resultats = {}

        naif = DummyRegressor(strategy="median").fit(X_train, y_train)
        resultats["baseline_mediane"] = evaluer(
            "baseline toujours la médiane",
            y_test,
            naif.predict(X_test)
        )

        mediane_paire = y_train.groupby(
            X_train["trajet_zones"]
        ).median()

        pred_paire = (
            X_test["trajet_zones"]
            .map(mediane_paire)
            .fillna(y_train.median())
        )

        resultats["baseline_paire_zones"] = evaluer(
            "baseline médiane par paire de zones",
            y_test,
            pred_paire
        )

        lineaire = LinearRegression().fit(
            X_train[["trip_distance"]], y_train
        )

        resultats["baseline_distance"] = evaluer(
            "baseline régression / distance",
            y_test,
            lineaire.predict(X_test[["trip_distance"]])
        )

        # Enregistrer les métriques des baselines
        for nom, metriques in resultats.items():
            mlflow.log_metrics({
                f"{nom}_{metrique}": float(valeur)
                for metrique, valeur in metriques.items()
            })

        # -------------------------
        # Entraînement du modèle
        # -------------------------

        print("entrainement du gradient boosting")

        pipeline = creer_pipeline(numeriques).fit(
            X_train, y_train
        )

        # -------------------------
        # Évaluation
        # -------------------------

        print("evaluation")

        metriques_train = evaluer(
            "gradient boosting, train",
            y_train,
            pipeline.predict(X_train)
        )

        metriques_test = evaluer(
            "gradient boosting, test",
            y_test,
            pipeline.predict(X_test)
        )

        mlflow.log_metrics({
            f"train_{nom}": float(valeur)
            for nom, valeur in metriques_train.items()
        })

        mlflow.log_metrics({
            f"test_{nom}": float(valeur)
            for nom, valeur in metriques_test.items()
        })

        # -------------------------
        # Importance des variables
        # -------------------------

        ech = X_test.sample(
            min(5000, len(X_test)),
            random_state=GRAINE
        )

        imp = permutation_importance(
            pipeline,
            ech,
            y_test.loc[ech.index],
            n_repeats=5,
            random_state=GRAINE,
            scoring="neg_mean_absolute_error"
        )

        importance_df = pd.DataFrame({
            "variable": X.columns,
            "importance": imp.importances_mean
        }).sort_values("importance", ascending=False)

        print("importance (hausse de l'erreur quand on mélange la variable)")

        for _, ligne in importance_df.iterrows():
            print(
                f"  {ligne['variable']:<18} "
                f"{ligne['importance']:+5.2f} min"
            )

        # CSV consultable dans les artefacts MLflow
        mlflow.log_text(
            importance_df.to_csv(index=False),
            "importance_variables.csv"
        )

        # -------------------------
        # Sauvegarde du modèle
        # -------------------------

        joblib.dump(pipeline, CHEMIN_MODELE)

        from datetime import datetime
        from modele_info import ecrire_meta

        ecrire_meta(
            CHEMIN_MODELE,
            date_entrainement=datetime.now().isoformat(timespec="seconds"),
            date_entrainement_source="entrainement",
            mae_test_minutes=round(
                float(metriques_test["mae"]), 3
            ),
            lignes_entrainement=int(len(X_train)),
        )

        # Enregistrer le modèle et sa version joblib dans MLflow
        mlflow.sklearn.log_model(
        sk_model=pipeline,
        name="modele",
        skops_trusted_types=[
            "sklearn.ensemble._hist_gradient_boosting.predictor.TreePredictor"
        ],
    )

        mlflow.log_artifact(str(CHEMIN_MODELE))

        # Informations utiles pour comparer les entraînements
        mlflow.set_tag("projet", "FrenchCab")
        mlflow.set_tag("type", "entrainement")
        mlflow.set_tag("cible", "trip_duration_min")

        print(f"Run MLflow : {mlflow.active_run().info.run_id}")

        print(
            f"Modèle sauvegardé : {CHEMIN_MODELE} "
            f"({time.time() - t0:.0f}s)"
        )


if __name__ == "__main__":
    main()