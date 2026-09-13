// Convierte los mensajes persistidos de una conversación (GET
// /api/conversaciones/{id}/mensajes) en la misma forma de "turno" que
// AsistenteView ya usa para los mensajes en vivo. Los turnos rol="model" que
// sí traen a2ui_json (el backend reconstruyó la tarjeta real, ver
// Orchestrator.reparsear_mensaje_modelo) se procesan contra el
// MessageProcessor para que se rendericen igual que en vivo; si ese texto
// viejo ya no parseó (a2ui_json es null), el turno cae a texto plano en vez
// de perderse.
export function buildTurnsFromHistorial(mensajes, { processMessages, extractSurfaceId }) {
  const turns = [];
  for (const m of mensajes) {
    if (m.rol === 'user') {
      turns.push({ kind: 'user', id: crypto.randomUUID(), text: m.contenido });
      continue;
    }
    if (m.a2ui_json) {
      processMessages(m.a2ui_json);
      const surfaceId = extractSurfaceId(m.a2ui_json);
      if (surfaceId) {
        turns.push({ kind: 'agent', id: surfaceId, surfaceId });
      }
      continue;
    }
    turns.push({ kind: 'agent-text', id: crypto.randomUUID(), text: m.contenido });
  }
  return turns;
}
