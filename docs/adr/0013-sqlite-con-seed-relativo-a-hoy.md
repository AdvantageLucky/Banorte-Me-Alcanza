# ADR 0013 — SQLite con datos sembrados relativos a la fecha actual

**Estado:** Aceptada · 2026-09-11

## Contexto

Los datos deben ser propios y pueden ser sintéticos. Un Postgres gestionado
habría añadido credenciales, red y un servicio más que operar durante el evento.
La demo, además, depende de que "en 3 días vence la colegiatura" siga siendo
cierto el día que se grabe o se presente.

## Decisión

SQLite en un archivo (`BANK_DB_PATH`), schema creado con `CREATE TABLE IF NOT
EXISTS` al conectar, y un `seed()` idempotente que calcula todas las fechas
como `hoy + N días`. El servidor MCP abre y cierra una conexión por tool. En
Docker el archivo vive en un volumen.

## Consecuencias

- Cero infraestructura; los tests usan `:memory:` o un archivo temporal.
- La cuenta `ana` dispara el mismo escenario (margen −$570, apartado de $142.50)
  cualquier día.
- Una sola escritura a la vez; no es multi-proceso. Migraciones de schema se
  hacen a mano (ej. la columna `categoria` se añade con `ALTER TABLE` protegido
  por `try/except`).
- El seed es la fuente de verdad de la demo: si cambia, cambian las cifras del
  README y de los tests de integración.
