
"""
Compare automatiquement tous les modèles .joblib du dossier backend/modeles.

- Évalue chaque modèle sur le même jeu de test.
- Classe les modèles selon leur MAE.
- Identifie les modèles conformes au seuil de qualité.
- Active le meilleur modèle conforme dans config/modele_actif.json.
- Conserve la configuration existante si aucun modèle n'est conforme.

"""

import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split

from Taxi_PichkupHour import (
    DEFAULT_DB,
    VARIABLES_NUMERIQUES,
    VARIABLES_CATEGORIELLES,
    VARIABLES_LOCATIONS,
    charger_donnees,
    nettoyer,
    construire_variables,
    GRAINE,
)


# ============================================================
# CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent.parent

DOSSIER_MODELES = BACKEND_DIR / "modeles"
CONFIG_DIR = BACKEND_DIR / "config"
CONFIG_MODELE = CONFIG_DIR / "modele_actif.json"

SEUIL_MAE_MINUTES = 3.50
TAILLE_ECHANTILLON = 1_000_000


# ============================================================
# GESTION DU MODÈLE ACTIF
# ============================================================

def enregistrer_modele_actif(chemin_modele):
    """Enregistre le modèle sélectionné dans la configuration: config/modele_actif.json"""

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    chemin_modele = chemin_modele.resolve()

    try:
        chemin_relatif = chemin_modele.relative_to(
            BACKEND_DIR.resolve()
        )
    except ValueError as erreur:
        raise ValueError(
            "Le modèle doit être situé dans le dossier backend/modeles."
        ) from erreur

    configuration = {
        "version": extraire_version(chemin_modele),
        "chemin_modele": chemin_relatif.as_posix(),
    }

    with CONFIG_MODELE.open("w", encoding="utf-8") as fichier:
        json.dump(
            configuration,
            fichier,
            indent=2,
            ensure_ascii=False,
        )

    print("\n=== Modèle actif mis à jour ===")
    print(f"Version : {configuration['version']}")
    print(f"Fichier : {configuration['chemin_modele']}")
    print(f"Configuration : {CONFIG_MODELE}")


def extraire_version(chemin_modele):
    """Déduit un nom de version à partir du nom du fichier."""

    nom = chemin_modele.stem

    if nom.startswith("modele_"):
        nom = nom[len("modele_"):]

    suffixe = "_duree_trajet"
    if nom.endswith(suffixe):
        nom = nom[:-len(suffixe)]

    return nom


# ============================================================
# PRÉPARATION DES DONNÉES
# ============================================================

def preparer_jeu_test():
    """Prépare un seul jeu de test partagé par tous les modèles."""

    df = charger_donnees(DEFAULT_DB, TAILLE_ECHANTILLON)
    df = nettoyer(df)
    df = construire_variables(df)

    colonnes = (
        VARIABLES_NUMERIQUES
        + VARIABLES_CATEGORIELLES
        + VARIABLES_LOCATIONS
    )

    X = df[colonnes]
    y = df["trip_duration_min"]

    _, X_test, _, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=GRAINE,
    )

    return X_test, y_test


# ============================================================
# COMPARAISON DYNAMIQUE
# ============================================================

def main():
    print("=== Comparaison automatique des modèles ===")

    # Recherche de tous les modèles dans le dossier dédié.
    fichiers_modeles = sorted(DOSSIER_MODELES.glob("*.joblib"))

    if not fichiers_modeles:
        print(f"Aucun modèle .joblib trouvé dans : {DOSSIER_MODELES}")
        return

    print(f"\nNombre de modèles détectés : {len(fichiers_modeles)}")

    # Les données sont préparées une seule fois.
    X_test, y_test = preparer_jeu_test()

    resultats = []
    modeles_valides = {}

    for chemin_modele in fichiers_modeles:
        version = extraire_version(chemin_modele)

        print(f"\nÉvaluation de {chemin_modele.name}...")

        try:
            modele = joblib.load(chemin_modele)
            predictions = modele.predict(X_test)

            mae = mean_absolute_error(y_test, predictions)

            resultats.append({
                "version": version,
                "fichier": chemin_modele.name,
                "MAE_minutes": mae,
                "conforme": mae <= SEUIL_MAE_MINUTES,
            })

            modeles_valides[chemin_modele] = mae

        except Exception as erreur:
            print(f"Évaluation impossible : {erreur}")

    if not resultats:
        print("\nAucun modèle n'a pu être évalué.")
        return

    # Classement de la meilleure MAE à la moins bonne.
    tableau = pd.DataFrame(resultats).sort_values(
        by=["MAE_minutes", "version"],
        ascending=[True, True],
    )

    print("\n=== Classement des modèles ===")
    print(
        tableau.to_string(
            index=False,
            formatters={
                "MAE_minutes": lambda valeur: f"{valeur:.3f}",
            },
        )
    )

    print(f"\nSeuil de qualité : {SEUIL_MAE_MINUTES:.2f} minutes")

    # Sélection du meilleur modèle qui respecte le seuil.
    conformes = tableau[tableau["conforme"]]

    if conformes.empty:
        print("\nQUALITÉ : aucun modèle ne respecte le seuil.")
        print("La configuration du modèle actif est conservée.")
        return

    meilleur_fichier = conformes.iloc[0]["fichier"]
    meilleur_chemin = DOSSIER_MODELES / meilleur_fichier

    print(f"\nMeilleur modèle conforme : {meilleur_fichier}")
    print(
        "MAE : "
        f"{conformes.iloc[0]['MAE_minutes']:.3f} minute(s)"
    )

    # Activation automatique du meilleur modèle conforme.
    enregistrer_modele_actif(meilleur_chemin)


if __name__ == "__main__":
    main()
