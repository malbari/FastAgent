#!/bin/bash

# Script per fermare il FastAgent Local Server (Sandbox)

echo "Fermata e rimozione della sandbox FastAgent..."
cd "$(dirname "$0")/fastagent/local_server" || exit

docker-compose down

if [ $? -eq 0 ]; then
    echo "------------------------------------------------"
    echo "Sandbox fermata correttamente."
    echo "------------------------------------------------"
else
    echo "Errore durante lo spegnimento della sandbox."
    exit 1
fi
