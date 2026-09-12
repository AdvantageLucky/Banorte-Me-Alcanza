# ADR 0014 — Contraseñas con PBKDF2 y sesiones con JWT

**Estado:** Aceptada · 2026-09-11

## Contexto

Hacen falta cuentas separadas (`ana`, `luis`) para demostrar aislamiento: un
usuario no debe poder confirmar la propuesta de otro ni listar sus contactos.
No se quería un servicio de identidad externo ni sesiones con estado en el
backend.

## Decisión

El servidor MCP guarda `pbkdf2_hmac(sha256, 100 000 iteraciones, salt de 16
bytes)` y expone `autenticar`. El backend emite un JWT HS256 (`pyjwt`) con
`sub=account_id` y 30 minutos de vida; cada ruta lo exige vía
`Depends(auth.get_current_account_id)`. Toda tool MCP recibe `account_id` y
filtra por él. El JWT se guarda en `localStorage` en web y en
`shared_preferences` en Flutter.

## Consecuencias

- Sin estado de sesión en el servidor: un reinicio no desconecta a nadie.
- El aislamiento por cuenta se prueba en tests (`marcar_sugerencia` de otra
  cuenta falla, `get_contacto` ajeno falla).
- No hay refresh token ni revocación: a los 30 minutos el usuario vuelve a
  entrar. Aceptable para una demo.
- `JWT_SECRET` viene de entorno; el de `.env.example` es un placeholder.
