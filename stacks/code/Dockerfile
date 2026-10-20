FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility

WORKDIR /app

# Dépendances système d'exécution et OpenMP
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Mise à jour des outils de packaging
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Étape 1 : PyTorch verrouillé sur CUDA 11.8
RUN pip install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cu118

# Étape 2 : Toutes les dépendances requises (avec numpy < 2 pour éviter les conflits d'ABI)
RUN pip install --no-cache-dir \
    accelerate \
    fastapi \
    huggingface-hub \
    peft \
    pydantic \
    pyyaml \
    rich \
    safetensors \
    transformers \
    typer \
    uvicorn

# Étape 3 : Installation de strands-decider sans résolution de dépendances
RUN pip install --no-cache-dir --no-deps strands-decider

# Copie du code applicatif et de l'entrypoint
COPY serve.py /app/serve.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]