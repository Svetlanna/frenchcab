"""Contrôle de qualité du modèle pour la CI.

Évalue le modèle (ou lit un rapport JSON déjà produit par evaluation_modele.py)
et compare la MAE au seuil défini dans seuil_qualite.json.

Codes de retour :
    0  MAE <= seuil          (qualité suffisante)
    1  MAE >  seuil          (échec qualité -> la CI échoue)
    2  erreur technique      (modèle / données introuvables, rapport illisible...)

Exemples :
    python controle_qualite.py
    python controle_qualite.py --seuil 4.5
    python controle_qualite.py --rapport rapport.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent
SEUIL_PAR_DEFAUT = DOSSIER / "seuil_qualite.json"


def charger_seuil(chemin: Path) -> float:
    return float(json.loads(chemin.read_text(encoding="utf-8"))["seuil_mae_minutes"])


def verifier(mae: float, seuil: float) -> bool:
    return mae <= seuil


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Vérifie que la MAE du modèle respecte le seuil")
    p.add_argument("--seuil", type=float, default=None,
                   help="seuil en minutes (défaut : seuil_qualite.json)")
    p.add_argument("--rapport", type=Path, default=None,
                   help="rapport JSON existant (sinon le modèle est évalué)")
    p.add_argument("--sortie", type=Path, default=None, help="écrit le rapport JSON évalué")
    a = p.parse_args(argv)

    try:
        seuil = a.seuil if a.seuil is not None else charger_seuil(SEUIL_PAR_DEFAUT)
        if a.rapport:
            rapport = json.loads(a.rapport.read_text(encoding="utf-8"))
        else:
            from evaluation_modele import (CHEMIN_MODELE, DONNEES_PAR_DEFAUT,
                                           ZONES_PAR_DEFAUT, evaluer_modele)
            rapport = evaluer_modele(CHEMIN_MODELE, DONNEES_PAR_DEFAUT, ZONES_PAR_DEFAUT)
            if a.sortie:
                a.sortie.write_text(json.dumps(rapport, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
        mae = float(rapport["metriques"]["mae_minutes"])
    except (OSError, ValueError, KeyError) as e:
        print(f"ERREUR : contrôle impossible ({type(e).__name__}: {e})", file=sys.stderr)
        return 2

    version = rapport.get("modele", {}).get("version", "?")
    if verifier(mae, seuil):
        print(f"OK : MAE = {mae:.2f} min <= seuil {seuil:.2f} min (modèle {version})")
        return 0
    print(f"ECHEC : MAE = {mae:.2f} min > seuil {seuil:.2f} min (modèle {version})",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
