
from __future__ import annotations

import argparse
import sys
from datetime import date, time
from pathlib import Path

# fonctions deja écrites  on les réutilise telles quelles
from modele_info import lire_infos
from taxi_duree_prediction import (CHEMIN_MODELE, DEFAULT_DB, afficher,
                                   charger_modele, construire_course_prediction,
                                   predire)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Prédit la durée d'une course avec un modèle donné")
    p.add_argument("--modele", type=Path, default=CHEMIN_MODELE,
                   help="fichier .joblib à utiliser (défaut : modèle en production)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="base SQLite frenchcab.db")
    p.add_argument("--depart", type=int, default=161, help="numéro de zone de départ")
    p.add_argument("--arrivee", type=int, default=237, help="numéro de zone d'arrivée")
    # date.fromisoformat transforme "2027-03-15" en objet date
    p.add_argument("--date", type=date.fromisoformat, default=date(2027, 3, 15))
    # time.fromisoformat transforme "10:00" en objet time
    p.add_argument("--heure", type=time.fromisoformat, default=time(10, 0))
    a = p.parse_args(argv)

    try:
        modele = charger_modele(a.modele)
        df = construire_course_prediction(a.db, a.depart, a.arrivee, a.date, a.heure)
    except Exception as e:  # fichier absent, zone inconnue, base mal formée...
        # code 2 = erreur technique (même convention que controle_qualite.py)
        print(f"ERREUR : prédiction impossible ({e})", file=sys.stderr)
        return 2

    df = predire(modele, df)
    afficher(df)

    duree = float(df["duree_predite"].iloc[0])
    # une durée négative ou absurde = modèle cassé, même si le calcul "marche"
    if not 0 < duree < 300:
        print(f"ERREUR : durée prédite incohérente ({duree:.1f} min)", file=sys.stderr)
        return 1

    print(f"Modèle utilisé : version {lire_infos(a.modele)['version']} ({a.modele.name})")
    return 0


if __name__ == "__main__":
    sys.exit(main())