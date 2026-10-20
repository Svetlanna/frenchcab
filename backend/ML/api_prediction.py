import json
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

#from Taxi_PichkupHour import CHEMIN_MODELE, DEFAULT_DB, TABLE_ZONES, TABLE_TRAJETS
from Taxi_PichkupHour import DEFAULT_DB, TABLE_ZONES, TABLE_TRAJETS
from taxi_duree_prediction import construire_course_prediction, charger_modele, predire
from modele_info import lire_infos
from datetime import date, time

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG_MODELE = BACKEND_DIR / "config" / "modele_actif.json"


app = FastAPI(title="FrenchCab - prédiction durée")

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"],
                   allow_methods=["GET"], allow_headers=["*"])

# le modèle est chargé UNE seule fois, au démarrage
#modele = charger_modele(CHEMIN_MODELE)

# identification du modèle réellement chargé (version = empreinte du fichier .joblib)
#INFOS_MODELE = lire_infos(CHEMIN_MODELE)


def charger_modele_actif():
    """Charge le modèle choisi dans modele_actif.json."""

    if not CONFIG_MODELE.is_file():
        raise RuntimeError(f"Configuration introuvable : {CONFIG_MODELE}")

    with CONFIG_MODELE.open("r", encoding="utf-8") as fichier:
        config = json.load(fichier)

    version = config.get("version")
    chemin = config.get("chemin_modele")

    if not version or not chemin:
        raise RuntimeError("Configuration du modèle invalide.")

    chemin_modele = (BACKEND_DIR / chemin).resolve()

    if not chemin_modele.is_relative_to(BACKEND_DIR.resolve()):
        raise RuntimeError("Le chemin du modèle est invalide.")

    if not chemin_modele.is_file():
        raise RuntimeError(f"Modèle introuvable : {chemin_modele}")

    modele_charge = charger_modele(chemin_modele)
    infos = dict(lire_infos(chemin_modele) or {})

    infos["version"] = version
    infos["fichier"] = chemin_modele.name

    return modele_charge, infos


# Chargement au démarrage de l'API
modele, INFOS_MODELE = charger_modele_actif()

@app.get("/modele")
def informations_modele() -> dict:
    """Version, date d'entraînement et métrique (MAE en minutes) du modèle utilisé."""
    return INFOS_MODELE


@app.get("/prediction")
def prediction_par_location(zone_depart: int, zone_arrivee: int, date_depart: date, heure_depart: time) -> dict:

    try:
        df = construire_course_prediction(DEFAULT_DB, zone_depart, zone_arrivee, date_depart, heure_depart)

    except ValueError as e:
        raise HTTPException(status_code=404,detail=str(e))

    df = predire(modele, df)

    c = df.iloc[0]

    depart = pd.to_datetime(c["tpep_pickup_datetime"])

    return {
        "depart": c["zone_dep"],
        "arrivee": c["zone_arr"],
        "date": f"{depart:%Y-%m-%d}",
        "heure_depart": f"{depart:%H:%M}",
        "distance_moyenne_miles": round(float(c["trip_distance"]),2),
        "duree_predite": round(float(c["duree_predite"])),
        "modele_version": INFOS_MODELE["version"]
    }

@app.get("/zones")
def liste_zones() -> list[dict]:
    with sqlite3.connect(DEFAULT_DB) as conn:
        lignes = conn.execute(
            f"SELECT locationID, zone FROM {TABLE_ZONES} "
            "WHERE locationID NOT IN (264, 265) "
            "ORDER BY zone").fetchall()
    return [{"id": id_zone, "nom": nom} for id_zone, nom in lignes]


# noms des colonnes attendus par le frontend (format TLC)
_ALIAS_COLONNES = {
    "vendorID": "VendorID",
    "RateCodeID": "RatecodeID",
    "pu_locationID": "PULocationID",
    "do_locationID": "DOLocationID",
}


def _ligne_en_dict(ligne: sqlite3.Row) -> dict:
    return {_ALIAS_COLONNES.get(k, k): ligne[k] for k in ligne.keys()}


def _ouvrir_db() -> sqlite3.Connection:
    """Connexion SQLite en lecture seule (la base n'est accessible que depuis le backend)."""
    if not DEFAULT_DB.exists():
        raise HTTPException(status_code=503, detail=f"Base introuvable : {DEFAULT_DB}")
    conn = sqlite3.connect(f"file:{DEFAULT_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/courses")
def liste_courses(limit: int = 100, offset: int = 0) -> list[dict]:
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    with _ouvrir_db() as conn:
        lignes = conn.execute(
            f"SELECT * FROM {TABLE_TRAJETS} LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
    return [_ligne_en_dict(l) for l in lignes]


@app.get("/courseID")
def course_par_id(uid_trajet: int) -> dict:
    with _ouvrir_db() as conn:
        ligne = conn.execute(
            f"SELECT * FROM {TABLE_TRAJETS} WHERE uid_trajet = ?", (uid_trajet,)
        ).fetchone()
    if ligne is None:
        raise HTTPException(status_code=404, detail="Course non trouvée")
    return _ligne_en_dict(ligne)
