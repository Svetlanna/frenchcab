import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from Taxi_PichkupHour import CHEMIN_MODELE, DEFAULT_DB
from taxti_dure_prediction import charger_courses, charger_modele, predire

app = FastAPI(title="FrenchCab - prédiction durée")

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:4200"],
                   allow_methods=["GET"], allow_headers=["*"])

# le modèle est chargé UNE seule fois, au démarrage
modele = charger_modele(CHEMIN_MODELE)


@app.get("/api/prediction/{uid_trajet}")
def prediction_par_uid(uid_trajet: int) -> dict:
    # 1. chercher la course dans la base
    try:
        df = charger_courses(DEFAULT_DB, [uid_trajet])
    except ValueError:
        raise HTTPException(status_code=404, detail=f"course {uid_trajet} introuvable")

    # 2. prédire
    df = predire(modele, df)
    c = df.iloc[0]
    depart = pd.to_datetime(c["tpep_pickup_datetime"])

    # 3. renvoyer le résultat en JSON
    return {
        "uid_trajet": int(c["uid_trajet"]),
        "date": f"{depart:%Y-%m-%d}",
        "start_time": f"{depart:%H:%M}",
        "duree_predite": round(float(c["duree_predite"])),
        "duree_reelle": round(float(c["trip_duration_min"])),
        "depart": f"{c['quartier_dep']}/{c['zone_dep']}/{c['zone_service_dep']}",
        "arrivee": f"{c['quartier_arr']}/{c['zone_arr']}/{c['zone_service_arr']}",
    }