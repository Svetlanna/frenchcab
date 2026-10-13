"""Identification du modèle de durée de trajet.

Les informations (version, date d'entraînement, métrique) sont stockées dans un
fichier JSON à côté du modèle : ``modele_duree_trajet.meta.json``.

La version est l'empreinte SHA-256 du fichier .joblib : elle est recalculée à
partir du fichier réellement chargé, donc elle ne peut pas être "oubliée" lors
d'un réentraînement. Les métadonnées ne sont reprises que si leur empreinte
correspond au modèle : un fichier meta périmé n'est jamais attribué à un autre
modèle.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


def chemin_meta(chemin_modele: Path) -> Path:
    return Path(chemin_modele).with_suffix(".meta.json")


def empreinte(chemin_modele: Path) -> str:
    h = hashlib.sha256()
    with open(chemin_modele, "rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _lire_meta(chemin_modele: Path) -> dict:
    p = chemin_meta(chemin_modele)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ecrire_meta(chemin_modele: Path, **champs) -> dict:
    """Met à jour le fichier meta du modèle (en le recréant si l'empreinte a changé)."""
    sha = empreinte(chemin_modele)
    meta = _lire_meta(chemin_modele)
    if meta.get("empreinte") != sha:
        meta = {}  # métadonnées d'un ancien modèle : on repart de zéro
    meta["empreinte"] = sha
    meta.update({k: v for k, v in champs.items() if v is not None})
    chemin_meta(chemin_modele).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return meta


def date_fichier(chemin_modele: Path) -> str:
    return datetime.fromtimestamp(Path(chemin_modele).stat().st_mtime).isoformat(timespec="seconds")


def lire_infos(chemin_modele: Path) -> dict:
    """Infos du modèle réellement présent sur le disque (None si non disponible)."""
    chemin_modele = Path(chemin_modele)
    sha = empreinte(chemin_modele)
    meta = _lire_meta(chemin_modele)
    valide = meta.get("empreinte") == sha
    meta = meta if valide else {}
    return {
        "version": sha[:12],
        "empreinte_sha256": sha,
        "fichier": chemin_modele.name,
        "date_entrainement": meta.get("date_entrainement"),
        "date_entrainement_source": meta.get("date_entrainement_source"),
        "mae_minutes": meta.get("mae_evaluation_minutes", meta.get("mae_test_minutes")),
        "mae_source": (
            "evaluation" if "mae_evaluation_minutes" in meta
            else "test_entrainement" if "mae_test_minutes" in meta
            else None
        ),
        "jeu_evaluation": meta.get("jeu_evaluation"),
        "date_evaluation": meta.get("date_evaluation"),
        "metadonnees_a_jour": valide,
    }
