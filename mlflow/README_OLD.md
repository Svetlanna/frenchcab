
# MLflow Service

## Description

Service de suivi des expériences Machine Learning.
Il permet de centraliser les paramètres, les métriques
et les artefacts des modèles de prédiction.

## Fonctionnalités

- Suivi des expériences d'entraînement
- Comparaison des performances des modèles
- Enregistrement des métriques et des paramètres
- Stockage des modèles entraînés

## Architecture

Le service MLflow fonctionne dans un conteneur Docker
indépendant du backend applicatif.

## Configuration

- Port : 5000
- Base de données : SQLite
- Stockage des artefacts : /mlflow/artifacts
- Persistance : volume Docker

## Démarrage

Depuis la racine du projet :

```bash
docker compose up -d --build mlflow
```

## Interface web

http://localhost:5000

## Connexion depuis le backend

```text
http://mlflow:5000
```

Cette adresse fonctionne depuis un autre conteneur
connecté au même réseau Docker Compose.
