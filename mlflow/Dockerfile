
FROM ghcr.io/mlflow/mlflow:v3.5.0

EXPOSE 5000

CMD ["mlflow", "server", "--host", "conteneur-mlflow", "--port", "5000", "--backend-store-uri", "sqlite:////mlflow/mlflow.db", "--artifacts-destination", "/mlflow/artifacts", "--allowed-hosts", "127.0.0.1:*", "--cors-allowed-origins", "0.0.0.0", "--static-prefix", "/mlflow"]