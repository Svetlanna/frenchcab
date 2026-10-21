from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pandas as pd

from Taxi_PickupHour import DEFAULT_DB, construire_variables
from Taxi_tarif_entrainement import CHEMIN_MODELE_TARIF
from taxi_duree_prediction import charger_modele, construire_course_prediction

def predire_tarif(modele, df: pd.DataFrame) -> pd.DataFrame:
    X = construire_variables(df.copy())
    X = X[list(modele.feature_names_in_)]
    df["tarif_predit"] = modele.predict(X)
    return df


def afficher_tarif(df: pd.DataFrame) -> None:
    for _, c in df.iterrows():
        depart = pd.to_datetime(c["tpep_pickup_datetime"])
        print(
            f"Course prévue le {depart:%Y-%m-%d} à {depart:%H:%M} "
            f"de {c['zone_dep']} vers {c['zone_arr']} "
            f"- prix estimé : {c['tarif_predit']:.2f} $ (hors pourboire)"
        )


def prediction_tarif(zone_depart: int, zone_arrivee: int, date_depart: date,
                     heure_depart: time, db_path: Path = DEFAULT_DB) -> float:
    modele = charger_modele(CHEMIN_MODELE_TARIF)
    df = construire_course_prediction(db_path, zone_depart, zone_arrivee, date_depart, heure_depart)
    df = predire_tarif(modele, df)
    afficher_tarif(df)
    return float(df["tarif_predit"].iloc[0])


if __name__ == "__main__":
    prediction_tarif(
        zone_depart=3,
        zone_arrivee=13,
        date_depart=date(2027, 3, 15),
        heure_depart=time(10, 0),
    )