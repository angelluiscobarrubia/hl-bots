# HL Bots · Plataforma multi-bot para Hyperliquid DEX

Arquitectura hexagonal (Ports & Adapters) · multi-usuario · paper-trading · plugins de estrategias con hot-reload · cifrado de API keys con Fernet.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.10+ · FastAPI · SQLAlchemy 2 (async) · asyncpg · Redis · Pydantic v2 · structlog |
| Hot-reload | watchfiles + pkgutil (las estrategias en `backend/strategies/` se detectan en vivo) |
| Migraciones | Alembic (async) |
| Observabilidad | prometheus-fastapi-instrumentator en `/metrics` |
| Linter | ruff (lint + format) + mypy |
| Frontend | React 18 + Vite 5 + TypeScript 5 + Tailwind 3 + DaisyUI 4 + Zustand + React Query + lightweight-charts |

## Estructura

```
hl-bots/
├── backend/
│   ├── src/
│   │   ├── core/                 # Lógica (entities, ports, services, config, logging, models)
│   │   ├── adapters/             # Hyperliquid, database, notifications
│   │   ├── api/                  # routes, websocket, dependencies
│   │   └── main.py               # Entrypoint FastAPI
│   ├── strategies/               # Plugins dinámicos (hot-reload)
│   │   ├── base_strategy.py
│   │   ├── moving_average_crossover.py
│   │   └── watcher.py
│   ├── alembic/                  # Migraciones async
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                     # Vite + React + TS + Tailwind + DaisyUI
└── doc/                          # Especificación
```

## Arranque rápido (desarrollo)

### 1. Levantar Postgres + Redis

```bash
docker run -d --name hl_postgres -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=securepass \
  -e POSTGRES_DB=bot_platform -p 5432:5432 -v pg_data:/var/lib/postgresql/data postgres:15
docker run -d --name hl_redis -p 6379:6379 -v redis_data:/data redis:7-alpine
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Edita .env y rellena MASTER_ENCRYPTION_KEY (32 bytes Fernet)
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Backend

```bash
cd backend
poetry install
poetry run alembic upgrade head     # Aplica migraciones
poetry run uvicorn src.main:app --reload --port 8000
# → http://localhost:8000/docs
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## Añadir una nueva estrategia

1. Crea `backend/strategies/mi_estrategia.py` con una clase que herede de `BaseStrategy`.
2. Implementa `async def analyze(market_data) -> Signal | None` y `def get_required_params() -> dict`.
3. El `StrategiesWatcher` detecta el archivo y `StrategyManager.reload()` la registra automáticamente (~500 ms).
4. Aparecerá en la página `/strategies` de la UI y en `GET /strategies`.

> **Importante:** los bots activos siguen usando la instancia anterior; reinícialos manualmente desde la UI para aplicar la nueva versión.

## Endpoints principales

| Método | Path | Descripción |
|---|---|---|
| GET | `/health` | Estado + estrategias cargadas |
| GET | `/strategies` | Lista estrategias registradas |
| POST | `/strategies/reload` | Recarga manual del manager |
| GET | `/metrics` | Métricas Prometheus |
| GET | `/docs` | OpenAPI / Swagger |
| POST | `/auth/login` | Login (devuelve access + refresh token) |
| POST | `/auth/refresh` | Renueva access token usando refresh token |
| POST | `/auth/logout` | Logout (invalida tokens) |
| GET | `/auth/me` | Perfil del usuario autenticado |
| POST | `/auth/change-password` | Cambiar password propio |
| POST | `/admin/users` | Crear usuario (solo admin) |
| GET | `/admin/users` | Listar usuarios (solo admin) |
| PATCH | `/admin/users/{id}` | Activar/desactivar usuario (solo admin) |
| POST | `/admin/users/{id}/reset-password` | Resetear password (solo admin) |

## Crear usuario admin

```bash
cd backend
poetry run python -m src.scripts.create_admin --email [REDACTED] --password "tu-password-seguro"
```

El primer admin debe crearse por CLI. Después, puede crear más usuarios desde la UI en `/admin`.

## Comandos útiles

```bash
# Backend
poetry run ruff check .            # Linter
poetry run ruff format .           # Formatter
poetry run pytest                  # Tests + coverage
poetry run alembic revision --autogenerate -m "msg"   # Nueva migración
poetry run alembic downgrade -1    # Rollback última migración

# Frontend
npm run dev          # Dev server
npm run build        # Build producción
npm run typecheck    # tsc --noEmit
npm run lint         # ESLint
npm run test         # Vitest

# Raíz
pre-commit run --all-files   # Hooks (ruff + mypy)
```

## Variables de entorno

Ver [`.env.example`](.env.example). Las críticas:

- `MASTER_ENCRYPTION_KEY` — Fernet key (32 bytes url-safe base64) para cifrar API keys de usuarios
- `JWT_SECRET` — Secret para tokens de autenticación
- `DATABASE_URL` / `REDIS_URL` — conexiones a Postgres/Redis
- `HYPERLIQUID_MAINNET_URL` / `HYPERLIQUID_TESTNET_URL` — endpoints del exchange
- `TELEGRAM_BOT_TOKEN` — opcional, para notificaciones

## Smoke tests verificados

- ✅ `poetry run ruff check .` → All checks passed
- ✅ `uvicorn src.main:app` → startup con watcher activo
- ✅ `GET /health`, `/strategies`, `/strategies/reload`, `/metrics` → 200 OK
- ✅ Crear `rsi_strategy.py` → watcher lo detecta y lo registra sin reiniciar
- ✅ `alembic upgrade head` → migración aplicada a Postgres real
- ✅ `npm run typecheck` → exit 0
- ✅ `npm run build` → 152 módulos, ~92 KB gzip
