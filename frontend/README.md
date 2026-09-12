# me-alcanza — frontend (React + Vite)

Cliente React (JavaScript, sin TypeScript) para el backend de
`me-alcanza`. Renderiza las superficies A2UI que arma el agente y
confirma propuestas de acción (apartado de ahorro / transferencia).

## Requisitos

- Node.js y `npm`.
- El backend corriendo en `http://localhost:8000` (ver raíz del repo:
  `uv run me-alcanza`, con `.env` configurado con
  `GOOGLE_AI_STUDIO_API_KEY`, `GEMINI_MODEL`, `JWT_SECRET`).

## Uso

```bash
cd frontend
cp .env.example .env   # ajusta VITE_API_BASE_URL si el backend no está en localhost:8000
npm install
npm run dev
```

Abre la URL que imprime Vite (usualmente `http://localhost:5173`).

Usuarios demo (ya sembrados en la base de datos simulada del backend):

- `ana` / `pass123`
- `luis` / `pass456`

## Pruebas

```bash
npm test
```

Corre los tests unitarios de los módulos JavaScript puros
(`api/client.js`, `auth/tokenStorage.js`, `chat/actionHandler.js`). Los
componentes de React (`LoginView`, `ChatView`, `App`) se verifican
manualmente en el navegador — ver los dos flujos abajo.

## Verificación manual de los dos flujos núcleo

Con el backend corriendo y `npm run dev` activo:

1. **Afford-check + apartado**: inicia sesión como `ana` / `pass123`,
   escribe "¿me alcanza para el concierto del 13 de octubre?". Debe
   aparecer una tarjeta con el veredicto y, si no alcanza, un botón para
   activar el apartado sugerido. Al hacer click, debe aparecer una
   tarjeta de confirmación (el apartado se creó de verdad en la DB
   simulada del backend).
2. **Transferencia con desambiguación**: en la misma sesión, escribe
   "deposítale 500 a mi hermano Pepe". Deben aparecer dos tarjetas de
   confirmación (dos contactos candidatos). Confirma una: debe aparecer
   la tarjeta de confirmación de esa transferencia específica.

Ambos flujos deben sobrevivir un refresh de página sin perder la sesión
(el token persiste en `localStorage`); cerrar sesión con "Salir" debe
regresar a la pantalla de login y limpiar el token.

## Estado de la verificación (2026-09-12)

Verificado en esta sesión, contra el backend real corriendo localmente
(`uv run me-alcanza`) y la API real de Google AI Studio:

- ✅ Suite de tests Python (backend + MCP): 82/82 en verde.
- ✅ Suite de tests del frontend (`npm test`): 12/12 en verde.
- ✅ `npm run build`: sin errores.
- ✅ `POST /api/login` real contra el MCP real: devuelve JWT válido.
- ✅ Manejo de errores del backend cuando Gemini falla: cae de forma
  limpia a un bloque A2UI de error legible (`Card` + `Text` con el
  mensaje), en vez de crashear o devolver una respuesta corrupta.

⚠️ **No verificado en vivo por saturación de la API de Gemini**: el
12 de septiembre de 2026 (día del hackathon), los modelos
`gemini-3.6-flash` (el configurado), `gemini-3.7-flash`,
`gemini-3.8-flash` y `gemini-flash-latest` devolvieron consistentemente
`503 UNAVAILABLE` ("This model is currently experiencing high demand")
al intentar los dos flujos de conversación de arriba — probablemente por
tráfico alto de otros equipos usando los mismos modelos preview
gratuitos el día del evento. `gemini-2.5-flash` respondió con `404`:
está deprecado para esta cuenta y Google recomienda usar
`gemini-3.6-flash`, confirmando que el modelo configurado es el
correcto, solo que está sobrecargado en este momento.

**Antes de la demo real**, correr manualmente los dos flujos de arriba
contra el backend real para confirmar que el contenido de las tarjetas
generadas por el LLM es el esperado (esto no se pudo verificar en esta
sesión por la causa externa ya descrita). Si `gemini-3.6-flash` sigue
saturado, considerar como respaldo `gemini-3.1-pro-preview` o
`gemini-2.5-pro` (mayor probabilidad de tener menos tráfico que los
modelos *-flash gratuitos, aunque con más latencia).
