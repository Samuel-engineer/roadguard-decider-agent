#!/usr/bin/env bash
set -e

# Si SageMaker appelle le conteneur avec l'argument "serve" (ou sans argument)
if [ "$1" = "serve" ] || [ -z "$1" ]; then
    echo "Démarrage du serveur Uvicorn pour SageMaker..."
    exec uvicorn serve:app --host 0.0.0.0 --port 8080
else
    # Permet d'exécuter n'importe quelle autre commande passée au conteneur (ex: bash de debug)
    exec "$@"
fi