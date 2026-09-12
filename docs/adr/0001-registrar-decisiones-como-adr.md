# ADR 0001 — Registrar las decisiones de arquitectura como ADRs

**Estado:** Aceptada · 2026-09-12

## Contexto

Durante el hackathon cada feature se diseñó como un *spec* y un *plan* ejecutable
(`docs/superpowers/`). Esos documentos servían para construir, pero no para
explicar *por qué* el sistema es como es: mezclaban pasos de implementación con
decisiones, quedaban obsoletos en cuanto el código cambiaba, y el entregable
técnico del reto pide explícitamente "decisiones y trade-offs: modelo,
protocolo, infraestructura".

## Decisión

Sustituir specs y planes por *Architecture Decision Records* en el formato de
Michael Nygard: un archivo por decisión, con Título, Estado, Contexto, Decisión y
Consecuencias. Se numeran en orden y nunca se editan para cambiar el sentido: una
decisión que se revierte se marca como *Reemplazada por ADR-NNNN* y se escribe
una nueva.

## Consecuencias

- Los planes de implementación viven en el historial de git, no en `docs/`.
- Cada ADR es corto y responde a una sola pregunta; el índice está en
  [`README.md`](README.md).
- Una decisión no documentada aquí se considera accidental, no arquitectura.
