# Dockerfile per il FastAgent Local Server (Sandbox Mode)
FROM python:3.12-slim

# Installazione dipendenze di sistema minime per Python ed eventuale networking
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia i file necessari per l'installazione delle dipendenze
COPY fastagent/local_server/requirements.txt ./fastagent/local_server/

# Installazione dipendenze Python (bypass SSL per Zscaler/Corporate Proxy se necessario)
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r fastagent/local_server/requirements.txt

# Copia il codice sorgente (mantenendo la struttura dei pacchetti)
COPY fastagent/ ./fastagent/

# Espone la porta interna del server Flask
EXPOSE 5000

# Comando di avvio (usando il modulo come specificato nel README)
CMD ["python", "-m", "fastagent.local_server.main", "--host", "0.0.0.0", "--port", "5000"]
