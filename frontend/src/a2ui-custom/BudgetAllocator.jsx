import { createComponentImplementation } from '@a2ui/react/v0_9';
import { BudgetAllocatorApi } from './schemas.js';

function formatMonto(monto) {
  return monto.toLocaleString('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
}

// Un solo grado de libertad: UNA categoría activa (categoriaSeleccionada) con
// UN monto (montoAsignado). El resto de 'total' se muestra como "sin
// asignar" — nunca reparto entre N categorías a la vez, porque eso exigiría
// una política de redistribución que tendría que reimplementarse idéntica en
// React y Flutter (riesgo real de que ambos clientes calculen distinto a
// partir del mismo stream A2UI). Todo el cálculo de abajo ocurre en el
// navegador; solo el Button que sigue a este componente manda algo al
// servidor.
export const BudgetAllocator = createComponentImplementation(BudgetAllocatorApi, ({ props }) => {
  const categorias = Array.isArray(props.categorias) ? props.categorias : [];
  if (categorias.length < 2) {
    return null;
  }
  const activaId = props.categoriaSeleccionada || categorias[0].id;
  const monto = typeof props.montoAsignado === 'number' ? props.montoAsignado : 0;
  const montoAcotado = Math.min(Math.max(monto, 0), props.total);
  const restante = props.total - montoAcotado;
  const activa = categorias.find((c) => c.id === activaId) || categorias[0];

  function seleccionar(id) {
    props.setCategoriaSeleccionada?.(id);
  }

  function handleChange(event) {
    props.setMontoAsignado?.(Number(event.target.value));
  }

  return (
    <div className="budget-allocator">
      {props.title && <p className="budget-allocator-title">{props.title}</p>}
      {props.subtitle && <p className="budget-allocator-subtitle">{props.subtitle}</p>}

      <div className="budget-allocator-chips">
        {categorias.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`budget-allocator-chip ${c.id === activaId ? 'budget-allocator-chip-selected' : ''}`}
            onClick={() => seleccionar(c.id)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="budget-allocator-result">
        <span className="budget-allocator-monto">{formatMonto(montoAcotado)}</span>
        <span className="budget-allocator-monto-label">para {activa.label}</span>
      </div>

      <input
        type="range"
        className="budget-allocator-slider"
        min={0}
        max={props.total}
        step="1"
        value={montoAcotado}
        onChange={handleChange}
        aria-label={`Ajustar monto para ${activa.label}`}
      />
      <div className="budget-allocator-range-labels">
        <span>{formatMonto(0)}</span>
        <span>{formatMonto(props.total)}</span>
      </div>

      <p className="budget-allocator-restante">
        Sin asignar: <strong>{formatMonto(restante)}</strong> de {formatMonto(props.total)}
      </p>
    </div>
  );
});
