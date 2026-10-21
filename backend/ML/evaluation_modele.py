"""Évaluation du modèle de durée de trajet existant (sans réentraînement).

Le modèle est chargé tel quel, puis ses prédictions sont comparées aux durées
réelles d'un jeu de courses TLC *distinct* des données d'entraînement (le modèle
est entraîné sur 2023, le jeu d'évaluation fourni est janvier 2026).

Le jeu de données est un CSV ou un parquet au format TLC "yellow taxi" avec au
minimum : tpep_pickup_datetime, tpep_dropoff_datetime, trip_distance,
PULocationID, DOLocationID.

Exemples :
    python evaluation_modele.py
    python evaluation_modele.py --donnees yellow_tripdata_2026-01.parquet --sortie rapport.json
    python evaluation_modele.py --maj-metadonnees      # enregistre la MAE dans le .meta.json
"""
from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

from modele_info import date_fichier, ecrire_meta, lire_infos
from Taxi_PickupHour import CHEMIN_MODELE, NOMS_ZONES, construire_variables, nettoyer

DOSSIER_EVAL = Path(__file__).resolve().parent.parent / "eval"
DONNEES_PAR_DEFAUT = DOSSIER_EVAL / "tlc_eval_2026-01.csv"
ZONES_PAR_DEFAUT = DOSSIER_EVAL / "taxi_zone_lookup.csv"

COLONNES_TLC = [
    "tpep_pickup_datetime", "tpep_dropoff_datetime", "trip_distance",
    "PULocationID", "DOLocationID",
]


def lire_donnees(chemin: Path) -> pd.DataFrame:
    if not chemin.exists():
        raise FileNotFoundError(f"Jeu d'évaluation introuvable : {chemin}")
    if chemin.suffix.lower() == ".parquet":
        df = pd.read_parquet(chemin, columns=COLONNES_TLC)
    else:
        df = pd.read_csv(chemin, usecols=COLONNES_TLC, parse_dates=[
            "tpep_pickup_datetime", "tpep_dropoff_datetime"])
    return df


def preparer(df: pd.DataFrame, zones_csv: Path) -> pd.DataFrame:
    """Met les courses TLC au même format que les données d'entraînement."""
    pickup = pd.to_datetime(df["tpep_pickup_datetime"])
    dropoff = pd.to_datetime(df["tpep_dropoff_datetime"])

    out = pd.DataFrame({
        "trip_duration_min": ((dropoff - pickup).dt.total_seconds() / 60).round(2),
        "trip_distance": df["trip_distance"],
        "tpep_pickup_datetime": pickup,
        # même format que la base : "HH:MM:00"
        "pickup_hour": pickup.dt.floor("min").dt.strftime("%H:%M:%S"),
        "pickup_weekday": pickup.dt.dayofweek,
        "pu_locationID": df["PULocationID"],
        "do_locationID": df["DOLocationID"],
    })

    lieux = pd.read_csv(zones_csv)
    lieux.columns = NOMS_ZONES  # locationID, quartier, zone, zone_service
    out = out.merge(lieux.add_suffix("_dep"), how="left",
                    left_on="pu_locationID", right_on="locationID_dep")
    out = out.merge(lieux.add_suffix("_arr"), how="left",
                    left_on="do_locationID", right_on="locationID_arr")
    return out


def evaluer_modele(modele_path: Path, donnees: Path, zones: Path,
                   echantillon: int = 0, graine: int = 42) -> dict:
    """Retourne le rapport d'évaluation (dict sérialisable en JSON)."""
    import joblib

    if not Path(modele_path).exists():
        raise FileNotFoundError(f"Modèle introuvable : {modele_path}")
    modele = joblib.load(modele_path)

    brut = lire_donnees(donnees)
    lignes_lues = len(brut)
    if echantillon and lignes_lues > echantillon:
        brut = brut.sample(echantillon, random_state=graine)

    df = preparer(brut, zones)
    # nettoyer() affiche ses compteurs : on les envoie sur stderr pour garder stdout propre
    with contextlib.redirect_stdout(sys.stderr):
        df = nettoyer(df)
    if df.empty:
        raise ValueError("Aucune course exploitable après nettoyage")

    X = construire_variables(df.copy())
    X = X[list(modele.feature_names_in_)]
    y_vrai = df["trip_duration_min"]
    y_pred = modele.predict(X)

    mae = float(mean_absolute_error(y_vrai, y_pred))
    mediane = float(y_vrai.median())

    return {
        "date_evaluation": datetime.now().isoformat(timespec="seconds"),
        "modele": lire_infos(Path(modele_path)),
        "jeu_evaluation": {
            "fichier": Path(donnees).name,
            "lignes_lues": int(lignes_lues),
            "lignes_evaluees": int(len(df)),
            "periode": [
                df["tpep_pickup_datetime"].min().strftime("%Y-%m-%d"),
                df["tpep_pickup_datetime"].max().strftime("%Y-%m-%d"),
            ],
        },
        "metriques": {
            "mae_minutes": round(mae, 3),
            "rmse_minutes": round(float(root_mean_squared_error(y_vrai, y_pred)), 3),
            "r2": round(float(r2_score(y_vrai, y_pred)), 4),
            # point de comparaison : prédire toujours la durée médiane
            "mae_baseline_mediane_minutes": round(
                float(mean_absolute_error(y_vrai, [mediane] * len(y_vrai))), 3),
            "duree_reelle_moyenne_minutes": round(float(y_vrai.mean()), 3),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Évalue le modèle existant (sans réentraînement)")
    p.add_argument("--modele", type=Path, default=CHEMIN_MODELE)
    p.add_argument("--donnees", type=Path, default=DONNEES_PAR_DEFAUT,
                   help="CSV ou parquet TLC distinct des données d'entraînement")
    p.add_argument("--zones", type=Path, default=ZONES_PAR_DEFAUT,
                   help="taxi_zone_lookup.csv")
    p.add_argument("--echantillon", type=int, default=0,
                   help="nombre max de courses évaluées (0 = toutes)")
    p.add_argument("--sortie", type=Path, default=None, help="écrit le rapport JSON dans ce fichier")
    p.add_argument("--maj-metadonnees", action="store_true",
                   help="enregistre la MAE dans le .meta.json du modèle")
    a = p.parse_args(argv)

    rapport = evaluer_modele(a.modele, a.donnees, a.zones, a.echantillon)

    if a.maj_metadonnees:
        meta = {
            "mae_evaluation_minutes": rapport["metriques"]["mae_minutes"],
            "jeu_evaluation": rapport["jeu_evaluation"]["fichier"],
            "date_evaluation": rapport["date_evaluation"],
        }
        # modèle livré avant l'ajout des métadonnées : à défaut, date du fichier
        if not lire_infos(a.modele)["date_entrainement"]:
            meta["date_entrainement"] = date_fichier(a.modele)
            meta["date_entrainement_source"] = "date_fichier"
        ecrire_meta(a.modele, **meta)

    texte = json.dumps(rapport, indent=2, ensure_ascii=False)
    if a.sortie:
        a.sortie.write_text(texte + "\n", encoding="utf-8")
    print(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
