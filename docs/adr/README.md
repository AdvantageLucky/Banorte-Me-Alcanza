# Architecture Decision Records

Registro de las decisiones de arquitectura del proyecto en formato
[Nygard](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):
**Título · Estado · Contexto · Decisión · Consecuencias**. Un archivo por decisión,
numerados en orden; una decisión que se revierte no se edita — se marca como
reemplazada y se escribe una nueva.

| # | Decisión | Estado |
|---|---|---|
| [0001](0001-registrar-decisiones-como-adr.md) | Registrar las decisiones de arquitectura como ADRs | Aceptada |
| [0002](0002-problema-acotado-me-alcanza.md) | Un solo problema: "¿me alcanza para X?" | Aceptada |
| [0003](0003-frontend-y-backend-separados.md) | Frontend y backend como despliegues separados | Aceptada |
| [0004](0004-stack-backend-python-fastapi-uv.md) | Backend en Python 3.14 con FastAPI y uv | Aceptada |
| [0005](0005-gemini-via-google-ai-studio.md) | Gemini a través de Google AI Studio (API gratuita) | Aceptada |
| [0006](0006-mcp-como-proceso-separado-sobre-stdio.md) | Servidor MCP como proceso separado sobre stdio | Aceptada |
| [0007](0007-mcp-como-unica-capa-de-datos-del-backend.md) | El backend habla con los datos solo a través del MCP, incluso fuera del LLM | Aceptada |
| [0008](0008-superficie-de-tools-segmentada.md) | Tres niveles de visibilidad para las tools MCP | Aceptada |
| [0009](0009-patron-proponer-confirmar.md) | Toda mutación pasa por proponer → confirmar | Aceptada |
| [0010](0010-el-llm-no-calcula-dinero.md) | El LLM decide qué mostrar; los motores deterministas deciden cuánto | Aceptada |
| [0011](0011-a2ui-con-catalogo-basico-del-sdk.md) | A2UI v0.9 con el catálogo básico del SDK | Aceptada con deuda reconocida |
| [0012](0012-dos-clientes-mismo-stream-a2ui.md) | Dos clientes (React y Flutter) sobre el mismo stream A2UI | Aceptada |
| [0013](0013-sqlite-con-seed-relativo-a-hoy.md) | SQLite con datos sembrados relativos a la fecha actual | Aceptada |
| [0014](0014-autenticacion-pbkdf2-y-jwt.md) | Contraseñas con PBKDF2 y sesiones con JWT | Aceptada |
| [0015](0015-memoria-de-conversacion-por-hilos.md) | Memoria de conversación por hilos, con ventana acotada | Aceptada |
| [0016](0016-modo-offline-determinista.md) | Modo offline determinista como respaldo del LLM | Aceptada |
| [0017](0017-self-hosting-en-homelab-con-docker-compose.md) | Self-hosting en un homelab con Docker Compose | Aceptada |
| [0018](0018-exposicion-publica-tailscale-funnel-y-cloudflare.md) | Backend público por Tailscale Funnel; frontend por Cloudflare con dominio propio | Aceptada |
| [0019](0019-sugerencias-proactivas-sin-llm.md) | Sugerencias proactivas deterministas, fuera del chat | Aceptada |
| [0020](0020-explicabilidad-por-componente.md) | Explicabilidad: todo número derivado lleva un "¿Cómo se calculó?" | Aceptada |
| [0021](0021-estrategia-de-pruebas.md) | Pruebas: MCP real por stdio, LLM mockeado, TDD por feature | Aceptada |
| [0022](0022-adaptador-openai-sin-tocar-el-orquestador.md) | Soporte multi-proveedor de LLM vía adaptador, sin reescribir el orquestador | Aceptada |

## Cómo agregar una

1. Copia el formato de cualquiera de arriba; siguiente número libre.
2. *Contexto* dice qué problema había y qué alternativas se miraron.
3. *Consecuencias* incluye lo malo, no solo lo bueno.
4. Agrégala a esta tabla.
