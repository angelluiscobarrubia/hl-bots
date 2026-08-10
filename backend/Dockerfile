# Imagen única usada por ``migrate`` y ``backend`` en docker-compose.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema (cryptography, asyncpg, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Poetry
ENV POETRY_VERSION=1.8.3
RUN pip install "poetry==${POETRY_VERSION}"

WORKDIR /app

# Copiar solo manifests primero para cachear capas de dependencias
COPY pyproject.toml poetry.lock* ./

# Instalar deps (sin dev para producción). Aceptamos poetry.lock ausente.
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root || \
       poetry install --no-interaction --no-ansi --no-root --only main

# Código fuente (en compose se monta como volumen para dev hot-reload)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
