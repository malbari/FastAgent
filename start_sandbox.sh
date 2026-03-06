#!/bin/bash

# Script per avviare il FastAgent Local Server (Sandbox) in modalità detached
# La porta utilizzata è la 52100 come configurata nel docker-compose.yml

echo "Avvio della sandbox FastAgent..."
cd "$(dirname "$0")/fastagent/local_server" || exit

# Forza la build per applicare le modifiche al Dockerfile e al codice
docker-compose up -d --build

if [ $? -eq 0 ]; then
    echo "------------------------------------------------"
    echo "Sandbox avviata con successo!"
    echo "Endpoint: http://localhost:52100"
    echo "------------------------------------------------"
else
    echo "Errore durante l'avvio della sandbox."
    exit 1
fi
