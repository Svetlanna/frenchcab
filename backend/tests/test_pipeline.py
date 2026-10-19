import json
import sys
from pathlib import Path

import pytest

# pipeline.py est dans backend/ (pas dans ML/) : on ajoute ce dossier au chemin d'import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pipeline  # noqa: E402


@pytest.fixture
def dossier_temporaire(tmp_path, monkeypatch):
    """Redirige tout ce que le pipeline écrit vers un dossier temporaire.

    monkeypatch remplace une variable le temps d'UN test, puis la remet :
    le vrai dossier modeles/candidat n'est jamais touché.
    """
    cand = tmp_path / "candidat"
    monkeypatch.setattr(pipeline, "DOSSIER_CANDIDAT", cand)
    monkeypatch.setattr(pipeline, "MODELE_CANDIDAT", cand / "modele_duree_trajet.joblib")
    monkeypatch.setattr(pipeline, "RAPPORT_CANDIDAT", cand / "rapport_candidat.json")
    monkeypatch.setattr(pipeline, "RAPPORT_PRODUCTION", cand / "rapport_production.json")
    # le journal doit rester "sous" BACKEND pour l'affichage relatif
    monkeypatch.setattr(pipeline, "BACKEND", tmp_path)
    monkeypatch.setattr(pipeline, "JOURNAL", cand / "journal_pipeline.json")
    return cand


def test_etape_inconnue_refusee():
    # argparse arrête le programme (SystemExit) si une étape n'existe pas
    with pytest.raises(SystemExit):
        pipeline.main(["--etapes", "nimportequoi"])


def test_evaluation_sans_candidat_est_une_erreur_technique(dossier_temporaire):
    assert pipeline.main(["--etapes", "evaluation"]) == 2


def test_le_pipeline_s_arrete_a_la_premiere_erreur(dossier_temporaire):
    pipeline.main(["--etapes", "evaluation,controle,prediction"])
    journal = json.loads((dossier_temporaire / "journal_pipeline.json").read_text(encoding="utf-8"))
    # seule l'étape en échec est dans le journal : les suivantes n'ont pas été lancées
    assert [e["nom"] for e in journal["etapes"]] == ["evaluation"]
    assert journal["etapes"][0]["statut"] == "ECHEC"


def test_controle_echoue_si_mae_au_dessus_du_seuil(dossier_temporaire):
    # faux rapport avec une très mauvaise MAE (99 minutes)
    dossier_temporaire.mkdir(parents=True)
    (dossier_temporaire / "rapport_candidat.json").write_text(
        json.dumps({"modele": {"version": "test"}, "metriques": {"mae_minutes": 99.0}}))
    # code 1 = échec qualité (et pas 2 = erreur technique)
    assert pipeline.main(["--etapes", "controle"]) == 1


def test_ordre_des_etapes_toujours_respecte(dossier_temporaire):
    # même si on les donne dans le désordre, l'évaluation passe avant le contrôle
    pipeline.main(["--etapes", "controle,evaluation"])
    journal = json.loads((dossier_temporaire / "journal_pipeline.json").read_text(encoding="utf-8"))
    assert journal["etapes_demandees"] == ["evaluation", "controle"]