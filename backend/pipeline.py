
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent          # .../frenchcab/backend
DOSSIER_ML = BACKEND / "ML"
DOSSIER_ETL = BACKEND / "etl"
DB = BACKEND / "data" / "frenchcab.db"
JEU_EVALUATION = BACKEND / "eval" / "tlc_eval_2026-01.csv"
MODELE_PRODUCTION = BACKEND / "modele_duree_trajet.joblib"
SEUIL = DOSSIER_ML / "seuil_qualite.json"


DOSSIER_CANDIDAT = BACKEND / "modeles" / "candidat"
MODELE_CANDIDAT = DOSSIER_CANDIDAT / "modele_duree_trajet.joblib"
RAPPORT_CANDIDAT = DOSSIER_CANDIDAT / "rapport_candidat.json"
RAPPORT_PRODUCTION = DOSSIER_CANDIDAT / "rapport_production.json"
JOURNAL = DOSSIER_CANDIDAT / "journal_pipeline.json"

# toutes les étapes possibles, dans l'ordre d'exécution
ORDRE_ETAPES = ["etl", "verification", "entrainement", "evaluation",
                "controle", "tests", "prediction"]


class EchecEtape(Exception):


    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code  # 1 = échec qualité, 2 = erreur technique


# ---------------------------------------------------------------------------
# 2. Un outil commun : lancer un script Python et vérifier qu'il a réussi.
# ---------------------------------------------------------------------------
def lancer(commande: list[str], dossier: Path) -> int:


    print(f"   $ {' '.join(commande)}   (dans {dossier.name}/)", flush=True)
    env = dict(os.environ, PYTHONUTF8="1")  # évite les soucis d'accents sous Windows
    resultat = subprocess.run([sys.executable, *commande], cwd=dossier, env=env)
    return resultat.returncode


def lancer_ou_echouer(commande: list[str], dossier: Path, message: str,
                      code_1_qualite: bool = False) -> None:

    code = lancer(commande, dossier)
    if code != 0:
        est_qualite = code_1_qualite and code == 1
        raise EchecEtape(f"{message} (code {code})", code=1 if est_qualite else 2)



# 3. Les étapes. Chaque étape = une fonction qui réussit ou lève EchecEtape.
def etape_etl(args) -> dict:
    """Refait la base : CSV brut -> CSV propre -> frenchcab.db (très long)."""
    lancer_ou_echouer(["extraction.py"], DOSSIER_ETL, "extraction ETL en échec")
    lancer_ou_echouer(["load_taxi_data.py"], DOSSIER_ETL, "chargement en base en échec")
    return {}


def etape_verification(args) -> dict:

    requis = {
        "base de données": args.db,
        "jeu d'évaluation": JEU_EVALUATION,
        "seuil de qualité": SEUIL,
        "modèle en production": MODELE_PRODUCTION,
    }
    manquants = [f"{nom} : {chemin}" for nom, chemin in requis.items() if not chemin.exists()]
    if manquants:
        raise EchecEtape("fichiers introuvables ->\n      " + "\n      ".join(manquants))
    for nom, chemin in requis.items():
        print(f"   [OK] {nom} : {chemin.relative_to(BACKEND) if chemin.is_relative_to(BACKEND) else chemin}")
    return {}


def etape_entrainement(args) -> dict:
    """entraîne un NOUVEAU modèle et le range comme candidat"""
    DOSSIER_CANDIDAT.mkdir(parents=True, exist_ok=True)
    lancer_ou_echouer(
        ["Taxi_PichkupHour.py", str(args.echantillon),
         "--db", str(args.db), "--sortie", str(MODELE_CANDIDAT)],
        DOSSIER_ML, "entraînement en échec")
    return {"modele_candidat": str(MODELE_CANDIDAT.relative_to(BACKEND))}


def etape_evaluation(args) -> dict:

    if not MODELE_CANDIDAT.exists():
        raise EchecEtape(f"pas de modèle candidat ({MODELE_CANDIDAT}) : lance d'abord l'entraînement")

    # le candidat : on enregistre aussi sa MAE dans son .meta.json
    lancer_ou_echouer(
        ["evaluation_modele.py", "--modele", str(MODELE_CANDIDAT),
         "--donnees", str(JEU_EVALUATION), "--sortie", str(RAPPORT_CANDIDAT),
         "--maj-metadonnees"],
        DOSSIER_ML, "évaluation du candidat en échec")

    # la production : on la note seulement, on NE TOUCHE PAS à ses fichiers
    lancer_ou_echouer(
        ["evaluation_modele.py", "--modele", str(MODELE_PRODUCTION),
         "--donnees", str(JEU_EVALUATION), "--sortie", str(RAPPORT_PRODUCTION)],
        DOSSIER_ML, "évaluation de la production en échec")

    cand = json.loads(RAPPORT_CANDIDAT.read_text(encoding="utf-8"))
    prod = json.loads(RAPPORT_PRODUCTION.read_text(encoding="utf-8"))
    return {
        "candidat": {"version": cand["modele"]["version"],
                     "mae_minutes": cand["metriques"]["mae_minutes"]},
        "production": {"version": prod["modele"]["version"],
                       "mae_minutes": prod["metriques"]["mae_minutes"]},
        "jeu_evaluation": cand["jeu_evaluation"]["fichier"],
    }


def etape_controle(args) -> dict:
    """le candidat respecte-t-il le seuil ? (réutilise controle_qualite.py)"""
    if not RAPPORT_CANDIDAT.exists():
        raise EchecEtape("pas de rapport candidat : lance d'abord l'étape evaluation")
    # controle_qualite.py renvoie 0 = OK, 1 = au-dessus du seuil, 2 = erreur
    lancer_ou_echouer(["controle_qualite.py", "--rapport", str(RAPPORT_CANDIDAT)],
                      DOSSIER_ML, "le candidat ne respecte pas le seuil de qualité",
                      code_1_qualite=True)
    seuil = json.loads(SEUIL.read_text(encoding="utf-8"))["seuil_mae_minutes"]
    return {"seuil_mae_minutes": seuil, "admissible": True}


def etape_tests(args) -> dict:
    """tests automatisés de l'équipe (pytest lit backend/pytest.ini)"""
    lancer_ou_echouer(["-m", "pytest", "-q"], BACKEND, "des tests échouent")
    return {}


def etape_prediction(args) -> dict:
    """Test de fumée le candidat sait-il prédire une vraie course ?"""
    if not MODELE_CANDIDAT.exists():
        raise EchecEtape("pas de modèle candidat : lance d'abord l'entraînement")
    lancer_ou_echouer(
        ["predire_exemple.py", "--modele", str(MODELE_CANDIDAT), "--db", str(args.db),
         "--depart", str(args.depart), "--arrivee", str(args.arrivee)],
        DOSSIER_ML, "la prédiction d'exemple a échoué", code_1_qualite=True)
    return {}


# dictionnaire "nom de l'étape" -> "fonction à appeler"
ETAPES = {
    "etl": etape_etl,
    "verification": etape_verification,
    "entrainement": etape_entrainement,
    "evaluation": etape_evaluation,
    "controle": etape_controle,
    "tests": etape_tests,
    "prediction": etape_prediction,
}


# ---------------------------------------------------------------------------
# 4. le résumé final et le journal (pour garder une trace de chaque exécution)
# ---------------------------------------------------------------------------
def afficher_resume(journal: dict) -> None:
    print("\n" + "=" * 64)
    print(" RÉSUMÉ DU PIPELINE")
    print("=" * 64)
    for e in journal["etapes"]:
        print(f"  {e['statut']:<7} {e['nom']:<13} {e['duree_s']:>7.1f} s  {e.get('message', '')}")

    evalu = next((e["details"] for e in journal["etapes"]
                  if e["nom"] == "evaluation" and e["statut"] == "OK"), None)
    if evalu:
        c, p = evalu["candidat"], evalu["production"]
        print(f"\n  Comparaison sur {evalu['jeu_evaluation']} :")
        print(f"    production  {p['version']}   MAE = {p['mae_minutes']:.3f} min")
        print(f"    candidat    {c['version']}   MAE = {c['mae_minutes']:.3f} min")
    print(f"\n  Résultat : {journal['resultat']}")
    print(f"  Journal  : {JOURNAL.relative_to(BACKEND)}")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pipeline ML FrenchCab")
    p.add_argument("--etapes", default=None,
                   help="étapes séparées par des virgules (défaut : toutes sauf etl). "
                        f"Possibles : {','.join(ORDRE_ETAPES)}")
    p.add_argument("--avec-etl", action="store_true", help="ajoute l'étape ETL (très longue)")
    p.add_argument("--echantillon", type=int, default=1_000_000,
                   help="nombre de courses pour l'entraînement (0 = toutes)")
    p.add_argument("--db", type=Path, default=DB, help="base SQLite à utiliser")
    p.add_argument("--depart", type=int, default=161, help="zone de départ pour la prédiction test")
    p.add_argument("--arrivee", type=int, default=237, help="zone d'arrivée pour la prédiction test")
    args = p.parse_args(argv)

    # quelles étapes lancer ?
    if args.etapes:
        choisies = [e.strip() for e in args.etapes.split(",") if e.strip()]
        inconnues = [e for e in choisies if e not in ETAPES]
        if inconnues:
            p.error(f"étapes inconnues : {inconnues}. Possibles : {ORDRE_ETAPES}")
    else:
        choisies = [e for e in ORDRE_ETAPES if e != "etl"]
    if args.avec_etl and "etl" not in choisies:
        choisies.append("etl")
    # on remet toujours dans le bon ordre, même si l'utilisateur les a mélangées
    choisies = [e for e in ORDRE_ETAPES if e in choisies]

    journal = {"debut": datetime.now().isoformat(timespec="seconds"),
               "etapes_demandees": choisies, "etapes": [], "resultat": "?"}
    code_final = 0

    for numero, nom in enumerate(choisies, start=1):
        print(f"\n[{numero}/{len(choisies)}] {nom.upper()}", flush=True)
        t0 = time.time()
        trace = {"nom": nom}
        try:
            trace["details"] = ETAPES[nom](args)
            trace["statut"] = "OK"
        except EchecEtape as e:
            trace["statut"] = "ECHEC"
            trace["message"] = str(e).splitlines()[0]
            print(f"   [ECHEC] {e}", file=sys.stderr)
            code_final = e.code
        trace["duree_s"] = round(time.time() - t0, 1)
        journal["etapes"].append(trace)
        if code_final != 0:
            break  # une étape a échoué : on arrête la chaîne

    journal["fin"] = datetime.now().isoformat(timespec="seconds")
    journal["resultat"] = {0: "SUCCES : le candidat est prêt (non activé)",
                           1: "ECHEC QUALITE : le candidat ne doit pas être utilisé",
                           2: "ERREUR TECHNIQUE : voir l'étape en échec"}[code_final]
    DOSSIER_CANDIDAT.mkdir(parents=True, exist_ok=True)
    JOURNAL.write_text(json.dumps(journal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    afficher_resume(journal)
    return code_final


if __name__ == "__main__":
    sys.exit(main())