#!/bin/bash

# Naviga nella root del progetto
cd "$(dirname "$0")"

# 1. Gestione Virtual Environment
VENV_DIR=".venv"
VENV_SENTINEL="$VENV_DIR/.installed"

if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Virtual environment non trovato. Creazione in corso..."
    python3 -m venv "$VENV_DIR"
fi

# Attiva il venv
source "$VENV_DIR/bin/activate"

# 2. Verifica/Aggiornamento dipendenze (forzato se manca il file sentinella)
if [ ! -f "$VENV_SENTINEL" ] || [ requirements.txt -nt "$VENV_SENTINEL" ]; then
    echo "[INFO] Installazione/Aggiornamento dipendenze nel virtual environment..."
    pip install --upgrade pip
    pip install -r requirements.txt
    touch "$VENV_SENTINEL"
fi

# 3. Esegue il test
echo "[INFO] Avvio test con prompt turistico..."
python test/run_test.py --prompt "Mi dici le ultime 5 news sul turismo ?"

# Disattiva venv alla fine
deactivate
