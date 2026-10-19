from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import joblib
import pandas as pd
from datetime import date, time, datetime
from pathlib import Path


from Taxi_PichkupHour import (CHEMIN_MODELE, DEFAULT_DB, NOMS_ZONES, TABLE_TRAJETS, TABLE_ZONES, construire_variables)

def charger_modele(chemin: Path) -> object:
    if not chemin.exists():
        raise FileNotFoundError(f"modèle introuvable {chemin} "
                                f"(lancer modele_duree_trajet.py avant)")
    return joblib.load(chemin)



def nom_colonne(conn: sqlite3.Connection, table: str, cible: str) -> str:
    """Nom réel d'une colonne, quelle que soit la convention de la base
    (pu_locationID, PULocationID, PUlocationID...). La comparaison ignore
    la casse et les underscores."""
    norm = cible.replace("_", "").lower()
    for _, nom, *_ in conn.execute(f"PRAGMA table_info({table})"):
        if nom.replace("_", "").lower() == norm:
            return nom
    raise ValueError(f"colonne {cible} introuvable dans la table {table}")


def construire_course_prediction(db_path: Path, zone_depart: int, zone_arrivee: int, date_depart: date, heure_depart: time) -> pd.DataFrame:

    if not db_path.exists():
        raise FileNotFoundError(f"Base introuvable : {db_path}")

    with sqlite3.connect(db_path) as conn:

        depart = pd.read_sql_query(
            """
            SELECT
                locationID,
                quartier,
                zone,
                zone_service
            FROM localisations
            WHERE locationID = ?
            """,
            conn,
            params=(zone_depart,)
        )

        arrivee = pd.read_sql_query(
            """
            SELECT
                locationID,
                quartier,
                zone,
                zone_service
            FROM localisations
            WHERE locationID = ?
            """,
            conn,params=(zone_arrivee,)
        )

        if depart.empty:
            raise ValueError(f"Zone de départ inconnue : {zone_depart}")

        if arrivee.empty:
            raise ValueError(f"Zone d'arrivée inconnue : {zone_arrivee}")

        dep = depart.iloc[0]
        arr = arrivee.iloc[0]

        col_pu = nom_colonne(conn, "trajets", "pu_locationID")
        col_do = nom_colonne(conn, "trajets", "do_locationID")

        distance = pd.read_sql_query(
            f"""
            SELECT AVG(trip_distance) AS distance_moyenne
            FROM trajets
            WHERE {col_pu} = ?
              AND {col_do} = ?
              AND trip_distance > 0
            """,
            conn,
            params=(
                int(dep["locationID"]),
                int(arr["locationID"])
            )
        )

    distance_moyenne = distance.iloc[0]["distance_moyenne"]

    if pd.isna(distance_moyenne):
        raise ValueError(
            f"Aucune distance historique disponible pour "
            f"{zone_depart} vers {zone_arrivee}"
        )

    datetime_depart = datetime.combine(date_depart, heure_depart)

    df = pd.DataFrame([{
        "tpep_pickup_datetime": datetime_depart,
        "pickup_hour": heure_depart.hour,
        "pickup_weekday": date_depart.weekday(),

        "trip_distance": float(distance_moyenne),

        "pu_locationID": int(dep["locationID"]),
        "do_locationID": int(arr["locationID"]),

        "quartier_dep": dep["quartier"],
        "zone_dep": dep["zone"],
        "zone_service_dep": dep["zone_service"],

        "quartier_arr": arr["quartier"],
        "zone_arr": arr["zone"],
        "zone_service_arr": arr["zone_service"],
    }])

    return df


def predire(modele, df: pd.DataFrame) -> pd.DataFrame:
    # mêmes transformations que pendant l'entraînement
    X = construire_variables(df.copy())
    # le modèle se souvient des colonnes qu'il a vues pendant l'entraînement
    X = X[list(modele.feature_names_in_)]
    df["duree_predite"] = modele.predict(X)
    return df


def afficher(df: pd.DataFrame) -> None:
    for _, c in df.iterrows():
        depart = pd.to_datetime(c["tpep_pickup_datetime"])

        print(
            f"Course prévue le {depart:%Y-%m-%d} "
            f"à {depart:%H:%M} "
            f"de {c['quartier_dep']}/{c['zone_dep']}/{c['zone_service_dep']} "
            f"vers {c['quartier_arr']}/{c['zone_arr']}/{c['zone_service_arr']} "
            f"- durée prédite : {c['duree_predite']:.0f} min"
        )


def prediction(zone_depart: int, zone_arrivee: int, date_depart: date , heure_depart:time, db_path: Path = DEFAULT_DB) -> float:
    # prédit la durée de la course id_trajet et affiche le résultat
    modele = charger_modele(CHEMIN_MODELE)
    df = construire_course_prediction(db_path, zone_depart, zone_arrivee, date_depart, heure_depart)
    df = predire(modele, df)
    afficher(df)
    return float(df["duree_predite"].iloc[0])


if __name__ == "__main__":

    prediction(
        zone_depart=3,
        zone_arrivee=13,
        date_depart=date(2027, 3, 15),
        heure_depart=time(10, 0)
    )