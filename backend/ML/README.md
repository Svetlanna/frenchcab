# FrenchCab — BACKEND 

## ETL

### /backend/etl/extraction.py

```from __future__ import annotations```
Cela permet d'utiliser les types de données annotées dans ce script

```import argparse```
Cette bibliothèque permet de créer un programme commande ligne qui peut recevoir des arguments en ligne de commande

```import json```
Cette bibliothèque permet de travailler avec du JSON

```import time```
Cette bibliothèque permet de mesurer le temps d'exécution de certains blocs de code

```from collections import Counter```
Cette bibliothèque permet de compter les occurrences de chaque élément d'une liste

>python backend/etl/extraction.py --nrows 100000

##### Étapes du traitement

1. le script lit les **19 colonnes** ; les 4 colonnes techniques du portail (id, version, created_at, updated_at) sont ignorées.

2. le script normalise :
    * les noms repassent au format du dictionnaire TLC (vendorid → VendorID, pulocationid → PULocationID…),
    * les dates deviennent des dates,
    * les codes convertis en entiers,
    * les montants sont convertis en décimaux

3. le script filtre ; les lignes aberrantes sont comptées puis retirées.

4. le script écrit ; une première écriture crée le fichier avec les ent^tes de colonnes, chaque enregistrement s'ajoute ensuite à la fin du dataframe

##### Règles de nettoyage

1. **date_invalide**
    * Date de départ ou d'arrivée illisible.
    * Impossible de calculer la durée.
2. **hors_annee**
    * Départ hors de 2023 _(l'export contient des courses du 31/12/2022)_
3. **duree_negative_ou_nulle**
    * Arrivée avant ou à l'heure du départ.
    * Erreur de compteur.
4. **duree_sup_6h**
    * Course de plus de 6 h.
    * Compteur resté allumé _(vu : 23 h pour 1,2 mile)_.
5. **distance_nulle_ou_aberrante**
    * Distance ≤ 0 ou > 200 miles.
    * Distance non enregistrée.
6. **montant_negatif_ou_nul**
    * Tarif ou total ≤ 0.
    * Lignes d'annulation ou de remboursement.
7. **montant_aberrant**
    * Total > 1 000 $.
    * Saisie erronée.
8. **vendor_inconnu**
    * VendorID hors 1, 2, 6, 7.
    * Code absent du dictionnaire.
9. **ratecode_invalide**
    * RatecodeID hors 1–6 et 99.
    * Code absent du dictionnaire.
10. **payment_type_invalide**
    * payment_type hors 0–6.
    * Code absent du dictionnaire.

11. **Doublons**

Est considéré 'doublon' une ligne qui est identique à une autre dans l'échantillon de donnéees traité.

![ATTENTION] Deux valeurs sont vidées sans supprimer la course : 
    * passenger_count = 0
    * RatecodeID = 99 
Ils deviennent « inconnu » (case vide).

Deux fichiers sont écrits dans backend/data/clean/
    * yellow_tripdata_2023.csv   les courses propres, 23 colonnes (les 19 du dictionnaire + 4 ajoutées). il peut peser plusieurs Go ,vérifier l'espace disque
    * rapport_extraction_2023.json  lignes lues, gardées, rejetées, taux de rejet et détail par motif.


#### Colonnes ajoutées

**cbd_congestion_fee**
0 pour 2023 (taxe créée le 5 janvier 2025), gardée pour un schéma identique d'une année à l'autre
**trip_duration_min**
durée de la course en minutes
**pickup_hour**
heure de départ (0–23)

**pickup_weekday**
jour de départ (0 = lundi, 6 = dimanche)

![ATTENTION]
 Remboursements--- une annulation apparaît en deux lignes, une négative et une positive. La négative est retirée, la positive reste : la course compte donc une fois alors qu'elle a été remboursée

• doublons --- ils ne sont détectés qu'à l'intérieur d'un même morceau , deux lignes identiques dans deux morceaux différents
• frais d'aéroport, VendorID 1 : pour les courses à l'aéroport, extra semble déjà contenir les 1,25 $ de airport_fee. La somme des colonnes dépasse alors total_amount de 1,25 $ ; se fier à total_amount
•pourboires en espèces  ----- ils ne sont pas enregistrés ; tip_amount ne concerne que les paiements par carte
• improvement_surcharge : quelques lignes sont à 0,30 $ au lieu de 1,00 $ (ancien tarif) ; elles sont gardées
•test le script a été vérifié sur un petit extrait, pas encore sur les 6 Go complets

 lancer d'abord avec --nrows 100000 et relire le rapport    python backend/etl/extraction.py --nrows 100000

 ## Problématiques

Incohérences entre colonnes et tables sql -> ajouter les quelques colonnes manquantes dans la table "trajets" et  s'assurer de la présence du champ `uid_trajet` qui est un identifiant unique auutoincrémenté et fait office de clé primaire.

## Prédiction de la durée d'une course de taxi

Ce module prédit **combien de minutes va durer une course de taxi jaune** (New York, 2023), à partir des informations connues **au moment du départ** : la distance, l'heure, le jour et les zones de départ et d'arrivée

```
backend/
├── data/
│   └── frenchcab.db                  ← base SQLite (tables trajets + localisations)
└── ML/
    ├── Taxi_PickupHour.py          ← 1. entraînement du modèle
    ├── modele_duree_trajet.joblib   ←    modèle sauvegardé
    ├── taxi_duree_prediction.py.py     ← 2. prédiction d'une course par (zone_depart, zone_arrivee, date, heure)
    ├── api_prediction.py            ← 3. API FastAPI
    ├── requirements.txt             ← 4. dépendances Python
    ├── Dockerfile                   ← 4. image Docker de l'API
    └── .dockerignore
```

Le chemin complet :

```
frenchcab.db ──► Taxi_PickupHour.py ──► modele_duree_trajet.joblib
                                               │
                       taxi_duree_prediction.py.py ◄┘
                                │
                       api_prediction.py (FastAPI, port 8000)
                                │
                       Angular / navigateur : GET /api/prediction/13
```

---

## 1. Le modèle — `Taxi_PickupHour.py`

### Le but

Une fonction : **informations de la course → durée en minutes**

C'est de l'**apprentissage supervisé** : le modèle apprend à partir de courses passées dont on connaît la vraie durée
Comme la réponse est un nombre, c'est une **régression**

- **X** (les variables, ou *features*) : ce qu'on donne au modèle
- **y** (la cible) : `trip_duration_min`, déjà calculée par l'ETL (`load_taxi_data.py`)

### Les étapes

| Étape | Fonction | Description |
|---|---|---|
| 1. Charger | `charger_donnees()` | |
| 2. Nettoyer | `nettoyer()` | |
| 3. Variables | `construire_variables()` | Crée `heure` et `est_weekend`, ainsi que la paire de zones `trajet_zones` (ex. `"zone_names"`) |
| 4. Train / test | `train_test_split` | 80 % des courses pour apprendre, 20 % pour vérifier sur des courses jamais vues |
| 5. Baselines | `DummyRegressor`, médiane par paire, `LinearRegression` | Modèles très simples que le vrai modèle doit battre |
| 6. Entraîner | `creer_pipeline()` | Prépare les données, puis entraîne un Gradient Boosting |
| 7. Évaluer | `evaluer()` | Calcule MAE, RMSE et R², et l'importance de chaque variable |
| 8. Sauvegarder | `joblib.dump` | Écrit le fichier `modele_duree_trajet.joblib` |

### Les variables utilisées

| Type | Variables | Traitement |
|---|---|---|
| Nombres | `trip_distance`, `heure`, `pickup_weekday`, `est_weekend`, `mois` | Utilisées telles quelles |
| Peu de catégories | `quartier_dep/arr`, `zone_service_dep/arr`, `RateCodeID`, `vendorID` | **OneHotEncoder** : une colonne 0/1 par valeur |
| Beaucoup de catégories | `pu_locationID`, `do_locationID`, `trajet_zones` | **TargetEncoder** : chaque zone est remplacée par la durée moyenne de ses courses |

### Le modèle : `HistGradientBoostingRegressor`

- `max_iter=300` : au maximum 300 arbres
- `learning_rate=0.1` : chaque arbre corrige 10 % de l'erreur restante
- `early_stopping=True` : l'entraînement s'arrête quand le modèle ne progresse plus

Le **Pipeline** regroupe la préparation des données et le modèle dans **un seul objet**. On sauvegarde cet objet, et on le réutilise tel quel pour prédire

### Les mesures

- **MAE** : erreur moyenne en minutes. C'est la plus facile à lire
- **RMSE** : ressemble à la MAE, mais punit davantage les grosses erreurs
- **R²** : entre 0 et 1, la part de la variation expliquée (1 = parfait)
- Si le score **train** est bien meilleur que le score **test**, le modèle a appris par cœur : c'est du **surapprentissage**

### Lancer

```bash
cd backend/ML
python Taxi_PickupHour.py                  # avec la distance (1 million de courses)
python Taxi_PickupHour.py 2000000          # échantillon plus grand (0 = toutes les courses)
python Taxi_PickupHour.py --sans-distance  # seulement les zones et l'heure
```

## 2. La prédiction — `taxi_duree_prediction.py`

Ce fichier **utilise** le modèle déjà entraîné. Il ne réentraîne rien

| Fonction | Rôle |
|---|---|
| `charger_modele()` | Ouvre `modele_duree_trajet.joblib` |
| `constuire_course_prediction(db, zone_depart, zone_arrivee, date_depart, heure_depart)` | `SELECT ... FROM trajets WHERE zone IN (...)`, puis la jointure avec `localisations` |
| `predire(modele, df)` | Applique `construire_variables()` (**la même** fonction qu'à l'entraînement), puis `modele.predict()` |
| `afficher(df)` | Affiche une phrase par course |
| `prediction(id_trajet)` | Fait tout : charger, prédire et afficher |

Points importants :

- Les constantes et `construire_variables` sont **importées** depuis `Taxi_PickupHour.py`
  Ainsi, l'entraînement et la prédiction préparent les données exactement de la même façon
- `modele.feature_names_in_` donne la liste des colonnes vues pendant l'entraînement, on donne au modèle exactement ces colonnes, dans le même ordre
- Le `if __name__ == "__main__":` de `Taxi_PickupHour.py` empêche l'entraînement de se relancer quand on importe ce fichier

### Lancer

```bash
cd backend/ML
python taxi_duree_prediction.py      # lance prediction(20)
```

Résultat :

```
Course prévue le 2027-03-15 à 10:00 de Bronx/Allerton/Pelham Gardens/Boro Zone vers Manhattan/Battery Park City/Yellow Zone - durée prédite : 48 min
```

> Remarque : si la course a servi à l'entraînement, le modèle l'a déjà « vue ». La prédiction sera donc un peu trop bonne

---

## 3. L'API — `api_prediction.py` (FastAPI)

Angular tourne dans le **navigateur**, qui ne peut pas lancer un fichier Python. Il envoie des **requêtes HTTP**. FastAPI transforme donc la prédiction en **adresse web**

### La route

```
GET /api/prediction/{uid_trajet}

```
Pour ouvrir FASTApi [http://127.0.0.1:8000/docs]

| Partie du code | Rôle |
|---|---|
| `app = FastAPI(...)` | Crée l'application web |
| `http://localhost:4200` | Autorise Angular (port 4200) à appeler l'API (port 8000) |
| Chargement du modèle | Le modèle est chargé **une seule fois**, au démarrage, et pas à chaque requête |
| `@app.get("/api/prediction")` | Attend les paramètres dans le body `zone_depart: str, zone_arrivee: str, date_depart: date, heure_depart: time` |
| `HTTPException(404)` | Erreur renvoyée si la course n'existe pas |
| `return {...}` | Le dictionnaire est renvoyé en JSON (on convertit avec `int()` et `float()`, car le JSON ne connaît pas les types de pandas) |

### Réponses possibles

| Route | Code HTTP | Réponse |
|---|---|---|
| `/api/prediction/13` | 200 | JSON de la course (voir ci-dessous) |
| `/api/prediction/99999999` | 404 | `{"detail": "course 99999999 introuvable"}` |
| `/api/prediction/abc` | 422 | Erreur de validation : ce n'est pas un nombre |

```json
{
  "zone_depart": "Allerton/Pelham Gardens",
  "zone_arrivee": "Battery Park City",
  "date_depart": "2027-03-15",
  "heure_depart": "10:00:00",
}
```

### Lancer sans Docker

```bash
cd backend/ML
pip install fastapi uvicorn
uvicorn api_prediction:app --reload --port 8000
```

## 4. Docker

Le projet a maintenant **3 conteneurs** :

| Service | Image | Port | Rôle |
|---|---|---|---|
| `backend` | `node:22` | 3001 | API Express (liste des courses) |
| `ml` | `python:3.14-slim` | 8000 | API FastAPI (prédiction) |
| `frontend` | nginx | 4200 | Angular |

> Le service `backend` est une image **Node** : elle ne contient pas Python. C'est pour ça que la prédiction a besoin de son propre conteneur, `ml`

### `backend/ML/requirements.txt`

```text
fastapi
uvicorn
pandas
joblib
scikit-learn==VOTRE_VERSION
```

> Mettez **la même version** de scikit-learn que celle qui a entraîné le modèle (`pip show scikit-learn`). Avec une autre version, le fichier `.joblib` peut refuser de se charger

### `backend/ML/Dockerfile`

```dockerfile
FROM python:3.14-slim
WORKDIR /app/ML
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api_prediction:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Service dans `docker-compose.yml`

```yml
  ml:
    build: ./backend/ML
    container_name: conteneur-ml
    ports:
      - "8000:8000"
    volumes:
      - ./backend/data:/app/data
    restart: always
```

- `ports "8000:8000"` : le port 8000 du PC mène au port 8000 du conteneur

### Démarrer le projet

```bash
cd C:\python-projs\frenchcab
docker compose up --build
```

Puis ouvrir [http://localhost:8000/api/prediction/13](http://localhost:8000/api/prediction/13)

## Ordre de lancement (résumé)

1. `python Taxi_PickupHour.py` → crée le modèle `.joblib` (seulement si les données changent)
2. `python taxi_duree_prediction.py.py` → vérifie qu'une prédiction marche
3. `uvicorn api_prediction:app --port 8000` → vérifie l'API sans Docker
4. `docker compose up --build` → lance tout : backend, ml et frontend

## 5. Identification, évaluation et contrôle qualité du modèle

### Identifier le modèle utilisé

Les informations sont stockées dans `backend/modele_duree_trajet.meta.json`, à côté du modèle, et exposées par l'API :

```text
GET /modele                      (backend, port 3001)
GET /prediction/modele           (gateway, port 3000)
```

Exemple de réponse :

```json
{
  "version": "c3cecda3ba02",
  "date_entrainement": "2026-10-13T13:16:35",
  "date_entrainement_source": "date_fichier",
  "mae_minutes": 3.921,
  "mae_source": "evaluation",
  "jeu_evaluation": "tlc_eval_2026-01.csv",
  "metadonnees_a_jour": true
}
```

* `version` : 12 premiers caractères du SHA-256 du fichier `.joblib` réellement chargé. Elle est recalculée au démarrage : un modèle remplacé change automatiquement de version.
* `date_entrainement` : écrite par le script d'entraînement (`date_entrainement_source = "entrainement"`). Pour un modèle livré avant l'ajout des métadonnées, c'est la date du fichier (`"date_fichier"`).
* `mae_minutes` : MAE du jeu TLC d'évaluation (`mae_source = "evaluation"`), ou à défaut MAE du jeu de test de l'entraînement (`"test_entrainement"`).
* Le fichier meta n'est repris que si son empreinte correspond au modèle chargé. Sinon `metadonnees_a_jour` vaut `false` et la date et la MAE restent `null` : les infos d'un ancien modèle ne sont jamais attribuées à un autre.

Chaque réponse de `/prediction` contient aussi `modele_version`.

### Évaluer le modèle (sans réentraînement) — `evaluation_modele.py`

```bash
cd backend/ML
python evaluation_modele.py --sortie rapport.json
```

Le script :

1. charge le modèle existant (`modele_duree_trajet.joblib`), sans le réentraîner ;
2. lit un jeu de courses TLC distinct des données d'entraînement : `backend/eval/tlc_eval_2026-01.csv` (20 000 courses de janvier 2026, le modèle étant entraîné sur 2023) ;
3. calcule la durée réelle (arrivée - départ, en minutes), nettoie les courses aberrantes avec les mêmes règles que l'entraînement, puis prédit chaque durée ;
4. compare prédictions et durées réelles et produit un rapport JSON (console et fichier `--sortie`).

Extrait du rapport :

```json
"metriques": {
  "mae_minutes": 3.921,
  "rmse_minutes": 7.174,
  "r2": 0.7225,
  "mae_baseline_mediane_minutes": 8.852
}
```

`mae_baseline_mediane_minutes` est la MAE d'un prédicteur qui répondrait toujours la durée médiane : c'est le point de comparaison du seuil.

| Option | Rôle |
| --- | --- |
| `--donnees <fichier>` | autre jeu TLC (CSV ou parquet ; parquet demande `pyarrow`) avec les colonnes `tpep_pickup_datetime`, `tpep_dropoff_datetime`, `trip_distance`, `PULocationID`, `DOLocationID` |
| `--zones <fichier>` | `taxi_zone_lookup.csv` (par défaut `backend/eval/taxi_zone_lookup.csv`) |
| `--echantillon N` | n'évalue que N courses (0 = toutes) |
| `--sortie <fichier>` | écrit le rapport JSON |
| `--maj-metadonnees` | enregistre la MAE dans `modele_duree_trajet.meta.json`, donc dans `/modele` |

### Contrôle automatique du seuil — `controle_qualite.py`

```bash
python controle_qualite.py              # évalue puis compare au seuil
python controle_qualite.py --seuil 4.5  # seuil explicite
python controle_qualite.py --rapport rapport.json   # à partir d'un rapport existant
```

| Code retour | Signification |
| --- | --- |
| `0` | MAE <= seuil |
| `1` | MAE > seuil : échec qualité, la CI échoue |
| `2` | erreur technique (modèle, données ou rapport introuvables) |

Le seuil (5,0 min) et sa justification sont dans `seuil_qualite.json` : environ 25 % de marge sur la MAE mesurée (3,92 min) et nettement sous la baseline (8,85 min), au-delà de laquelle le modèle n'apporterait plus de gain réel. À revoir si le modèle ou le jeu d'évaluation change.

### Tests et CI

* Tests : `cd backend && python -m pytest` (7 tests dont la vérification du seuil sur un échantillon).
* Pipeline `.github/workflows/ci-cd.yml` : `qualite-modele` (tests + contrôle de la MAE), puis `build-and-push` (images Docker Hub), puis `deploy` (VM). Si le contrôle échoue, rien n'est construit ni déployé.

### Après un réentraînement

```bash
python Taxi_PickupHour.py 200000
python evaluation_modele.py --maj-metadonnees
curl http://localhost:3001/modele
```

La version change, la date d'entraînement est enregistrée et la MAE sur le jeu TLC est mise à jour. Commiter ensuite le `.joblib` et son `.meta.json` ensemble.

## 6. MLOps workflow

Pour lancer la comparaison du modèle en production et du modèle 'candidat', dans le terminal depuis la racine du projet :

```bash
cd backend/
py pipeline.py
```

Le pipeline :

* vérifie les bases et jeux de données ainsi que l'existence d'un seuil de qualité et d'un modèle ML en production
* entraîne et teste le modèle modele_duree_trajet.joblib avec un échantillon de 1017292 enregistrements 
* évalue le modèle 'candidat' et le modèle en production avec un même jeu de données et émet un rapport par version du modèle pour comparaison
* effectue un contrôle de la qualité du modèle 'candidat' et met à jour le 'rapport_candidat' émis pendant son évaluation
* effectue les 12 tests unitaires du pipeline
* effectue une prédiction avec le modèle candidat pour comparaison avec le modèle en production
* affiche dans la console et dans un fichier JSON le résumé de l'exécution du pipeline ainsi que la comparaison des 2 modèles


### Comparaison entre la version actuelle du modéle et une version candidate `comparer_modeles.py`

```bash
cd backend/ML
python comparer_modeles.py 

```

Le script compare automatiquement tous les modèles ```.joblib``` contenus dans le dossier backend/modeles.
A l'exécution, il :

<<<<<<< HEAD
le modéle actif se trouve  dans backend/config/modele_actif.json la version qui est utilisée par frenchcab pour prédire les courses.


Pour changer de version, il suffit de lancer la route : 
          
POST /modele/activer  (backend, port 3001) avec la version dans le body
 
```json
{
  "version": "v2"
}
```
Exemple de réponse :

```json
{
  "message": "Modèle activé avec succès.",
  "version": "v2",
  "fichier": "modele_v2_duree_trajet.joblib"
}
```

=======
* Évalue chaque modèle sur le même jeu de test.
* Classe les modèles selon leur MAE.
* Identifie les modèles conformes au seuil de qualité.
* Active le meilleur modèle conforme dans config/modele_actif.json.
* Conserve la configuration existante si aucun modèle n'est conforme.

Le modéle actif se trouve dans backend/config/modele_actif.json. Le modèle actif correspond à la version qui est utilisée par frenchcab pour prédire ses courses.

Pour changer de version, il suffit de changer le modéle dans ce fichier.
>>>>>>> thomas
