// Modal de confirmación nativo (no A2UI) para cualquier acción que mueva
// dinero o cree datos reales. El texto que muestra (`resumen`) no lo escribe
// el LLM: viene de GET /api/propuestas/{id}, que el backend construyó con
// f-strings sobre datos ya validados (ver Orchestrator.obtener_resumen_propuesta).
// Así el usuario siempre confirma contra el dato real de su cuenta, sin
// depender de que el modelo haya transcrito bien el monto o el destinatario
// en la tarjeta que generó.
export default function ConfirmActionModal({ resumen, onConfirm, onCancel }) {
  return (
    <div className="confirm-modal-overlay" onClick={onCancel}>
      <div
        className="confirm-modal-card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h3 id="confirm-modal-title" className="confirm-modal-title">
          ¿Estás seguro de hacer esto?
        </h3>
        <p className="confirm-modal-resumen">{resumen}</p>
        <p className="confirm-modal-note">
          Estos datos los validamos directamente contra tu cuenta antes de mostrarlos, no
          los genera el modelo de IA.
        </p>
        <div className="confirm-modal-actions">
          <button type="button" className="confirm-modal-cancel" onClick={onCancel}>
            Cancelar
          </button>
          <button type="button" className="confirm-modal-confirm" onClick={onConfirm}>
            Confirmar
          </button>
        </div>
      </div>
    </div>
  );
}
