#!/bin/bash

# Repo originale da cui è stato fatto il fork
UPSTREAM_URL="https://github.com/HKUDS/FastAgent"

# 1. Aggiungi il remote 'upstream' se non esiste
if ! git remote | grep -q "^upstream$"; then
    echo "Aggiungo il remote upstream: $UPSTREAM_URL"
    git remote add upstream "$UPSTREAM_URL"
fi

# 2. Recupera i cambiamenti dall'upstream
echo "Recupero i cambiamenti dall'upstream..."
git fetch upstream

# 3. Assicurati di essere sul branch principale (assumendo 'main' o 'master')
# Determina il branch di default se necessario, qui usiamo 'main' come standard moderno
CURRENT_BRANCH=$(git symbolic-ref --short HEAD)
echo "Branch corrente: $CURRENT_BRANCH"

# 4. Merge dei cambiamenti di upstream/main nel branch locale
# NOTA: Sostituisci 'main' con 'master' se il repo originale usa master
echo "Eseguo il merge di upstream/main in $CURRENT_BRANCH..."
git merge upstream/main

# 5. Push dei cambiamenti sul proprio fork (origin)
echo "Aggiorno il mio fork (origin)..."
git push origin "$CURRENT_BRANCH"

echo "Sincronizzazione completata!"
