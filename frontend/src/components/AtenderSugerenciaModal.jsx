// Modal HITL antes de marcar una sugerencia como atendida — mismo shell
// visual que ConfirmActionModal. La diferencia clave: título/descripción son
// deterministas (ya se le mostraron al usuario en la tarjeta), y la
// "propuesta del asistente" es texto del LLM que solo se genera si el
// usuario lo pide explícitamente (ver Orchestrator.generar_propuesta_sugerencia),
// nunca automático — así nunca hay una alerta fantasma esperando a que
// alguien la lea.
export default function AtenderSugerenciaModal({
  titulo,
  descripcion,
  propuestaEstado,
  propuesta,
  onGenerarPropuesta,
  onConfirm,
  onCancel,
}) {
  return (
    <div className="confirm-modal-overlay" onClick={onCancel}>
      <div
        className="confirm-modal-card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="atender-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="atender-modal-title" className="confirm-modal-title">
          ¿Atender esta notificación?
        </h3>
        <p className="confirm-modal-resumen">
          <strong>{titulo}</strong>
          <br />
          {descripcion}
        </p>
        <div className="atender-modal-propuesta">
          {propuestaEstado === 'idle' && (
            <button type="button" className="atender-modal-generar" onClick={onGenerarPropuesta}>
              Ver propuesta del asistente
            </button>
          )}
          {propuestaEstado === 'cargando' && (
            <p className="atender-modal-propuesta-loading">Generando propuesta…</p>
          )}
          {propuestaEstado === 'lista' && (
            <div className="atender-modal-propuesta-lista">
              <p className="atender-modal-propuesta-label">Propuesta del asistente</p>
              <p className="atender-modal-propuesta-texto">{propuesta}</p>
            </div>
          )}
          {propuestaEstado === 'error' && (
            <p className="atender-modal-propuesta-error">No se pudo generar la propuesta, intenta de nuevo.</p>
          )}
        </div>
        <p className="confirm-modal-note">
          La detección de este aviso es determinista (reglas sobre tus datos reales); la
          propuesta de arriba, si la pides, la elabora el modelo de IA a partir de esos mismos
          hechos.
        </p>
        <div className="confirm-modal-actions">
          <button type="button" className="confirm-modal-cancel" onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" className="confirm-modal-confirm" onClick={onConfirm}>
            Marcar como atendida
          </button>
        </div>
      </div>
    </div>
  );
}
