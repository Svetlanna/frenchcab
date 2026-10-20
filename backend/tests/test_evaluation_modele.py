import json

import pytest

import controle_qualite
import modele_info
from evaluation_modele import (CHEMIN_MODELE, DONNEES_PAR_DEFAUT, ZONES_PAR_DEFAUT,
                               evaluer_modele, preparer, lire_donnees)


def _rapport(tmp_path, mae):
    p = tmp_path / "rapport.json"
    p.write_text(json.dumps({"modele": {"version": "test"}, "metriques": {"mae_minutes": mae}}))
    return p


def test_controle_ok_sous_le_seuil(tmp_path):
    assert controle_qualite.main(["--rapport", str(_rapport(tmp_path, 3.0)), "--seuil", "5"]) == 0


def test_controle_echec_au_dessus_du_seuil(tmp_path):
    assert controle_qualite.main(["--rapport", str(_rapport(tmp_path, 6.0)), "--seuil", "5"]) == 1


def test_controle_erreur_technique_si_rapport_absent(tmp_path):
    assert controle_qualite.main(["--rapport", str(tmp_path / "absent.json")]) == 2


def test_seuil_par_defaut_est_defini():
    assert controle_qualite.charger_seuil(controle_qualite.SEUIL_PAR_DEFAUT) > 0


def test_preparation_calcule_la_duree_en_minutes():
    df = preparer(lire_donnees(DONNEES_PAR_DEFAUT).head(50), ZONES_PAR_DEFAUT)
    assert (df["trip_duration_min"] > -1e-9).sum() > 0
    assert df["pickup_hour"].str.fullmatch(r"\d\d:\d\d:00").all()
    assert {"quartier_dep", "zone_service_arr"} <= set(df.columns)


def test_infos_modele_liees_au_fichier(tmp_path):
    f = tmp_path / "m.joblib"
    f.write_bytes(b"abc")
    assert modele_info.lire_infos(f)["metadonnees_a_jour"] is False
    modele_info.ecrire_meta(f, date_entrainement="2026-01-01T00:00:00", mae_test_minutes=4.2)
    infos = modele_info.lire_infos(f)
    assert infos["version"] == modele_info.empreinte(f)[:12]
    assert infos["mae_minutes"] == 4.2 and infos["metadonnees_a_jour"] is True
    # le fichier est remplacé par un autre modèle : les anciennes métadonnées ne s'appliquent plus
    f.write_bytes(b"autre modele")
    infos = modele_info.lire_infos(f)
    assert infos["mae_minutes"] is None and infos["metadonnees_a_jour"] is False


def test_modele_livre_respecte_le_seuil():
    """Même vérification que la CI, sur un échantillon pour rester rapide."""
    rapport = evaluer_modele(CHEMIN_MODELE, DONNEES_PAR_DEFAUT, ZONES_PAR_DEFAUT, echantillon=3000)
    seuil = controle_qualite.charger_seuil(controle_qualite.SEUIL_PAR_DEFAUT)
    assert rapport["metriques"]["mae_minutes"] <= seuil
