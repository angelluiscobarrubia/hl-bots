# Índice de Documentación · HL Bots

Navegación de la documentación del proyecto. Cada archivo describe una decisión
arquitectónica, un subsistema o un flujo. Mantener sincronizado con la implementación.

## Documentos fundamentales (decisiones arquitectónicas)

| Doc | Pregunta que responde |
|---|---|
| [`Diagrama Conceptual de Alto Nivel.txt`](Diagrama%20Conceptual%20de%20Alto%20Nivel.txt) | ¿Cómo se organizan las capas (UI, API, Core, Adapters) y qué hay en cada una? |
| [`Diagrama (Multiusuario + Paper).txt`](Diagrama%20(Multiusuario%20+%20Paper).txt) | ¿Cómo se aísla cada usuario y cómo funciona el toggle paper/real? |
| [`Estructura de Carpetas Propuesta.txt`](Estructura%20de%20Carpetas%20Propuesta.txt) | ¿Dónde va cada archivo? (estado actual) |
| [`Stack Tecnológico.txt`](Stack%20Tecnol%C3%B3gico.txt) | ¿Qué librerías usamos y por qué? (fuente única de verdad) |

## Subsistemas

| Doc | Subsistema |
|---|---|
| [`Estrategias como Plugins (Hot-Reload).txt`](Estrategias%20como%20Plugins%20(Hot-Reload).txt) | Cómo se cargan las estrategias dinámicamente |
| [`Paperbroker (Modo Simulación).txt`](Paperbroker%20(Modo%20Simulaci%C3%B3n).txt) | Cómo se simula la exchange sin dinero real |
| [`Gestión de API Keys (Multiusuario + Seguridad).txt`](Gesti%C3%B3n%20de%20API%20Keys%20(Multiusuario%20+%20Seguridad).txt) | Cifrado Fernet + JWT + aislamiento multi-tenant |
| [`Logging y Observabilidad.txt`](Logging%20y%20Observabilidad.txt) | structlog + Prometheus + health checks |

## Decisiones de producto / UI

| Doc | Decisión |
|---|---|
| [`Elección de UI (Orientado a Agente IA y Ahorro de Tokens).txt`](Elecci%C3%B3n%20de%20UI%20(Orientado%20a%20Agente%20IA%20y%20Ahorro%20de%20Tokens).txt) | Por qué React+Vite+TS+Tailwind+DaisyUI+Zustand |

## Operación y calidad

| Doc | Tema |
|---|---|
| [`Desarrollo Local (Quickstart).txt`](Desarrollo%20Local%20(Quickstart).txt) | Cómo arrancar el stack desde cero |
| [`Calidad de Código.txt`](Calidad%20de%20C%C3%B3digo.txt) | ruff + mypy + pytest + vitest + pre-commit |

---

## Leyenda de estado

| Marca | Significado |
|---|---|
| ✅ | Implementado y verificado en vivo |
| 🟡 | Diseño listo, código pendiente |
| ⚪ | Concepto / idea para futuro |

## Estado actual (2026-08-09)

| Subsistema | Estado |
|---|---|
| Stack base (Postgres + Redis + backend + frontend) | ✅ |
| FastAPI con lifespan + /health + /strategies + /metrics | ✅ |
| Logging estructurado (structlog) | ✅ |
| Métricas Prometheus | ✅ |
| Hot-reload de estrategias (watchfiles) | ✅ (probado en vivo) |
| Linter + formatter (ruff) | ✅ (0 errores) |
| Migraciones Alembic (async) | ✅ (1ª migración aplicada) |
| TypeScript strict en frontend | ✅ |
| Build de producción frontend | ✅ (92 KB gzip) |
| Dockerfile backend | ✅ |
| docker-compose con migrate service | 🟡 (usa `docker run` directo de momento) |
| Adapters Hyperliquid (Real + Paper) | 🟡 |
| Auth JWT + permisos (admin/user) | ✅ |
| Fernet cipher para API keys de exchanges | ✅ (cipher + modelo ApiKey + migración aplicada) |
| Risk Manager | ⚪ |
| WebSocket de bots en vivo | ⚪ |
| CI/CD (GitHub Actions) | ⚪ |

## Cómo mantener estos docs sincronizados

Cuando implementes algo nuevo:
1. ¿Cambia la estructura? → actualizar `Estructura de Carpetas Propuesta.txt`
2. ¿Añades una librería? → actualizar `Stack Tecnológico.txt`
3. ¿Cambia un flujo? → actualizar el diagrama correspondiente
4. ¿Nuevo subsistema? → crear un doc nuevo y enlazarlo aquí
5. ¿Completa algo pendiente? → cambiar 🟡 a ✅ en este índice
