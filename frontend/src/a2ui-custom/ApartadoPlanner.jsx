import { createComponentImplementation } from '@a2ui/react/v0_9';
import { ApartadoPlannerApi } from './schemas.js';

function formatMonto(monto) {
  return monto.toLocaleString('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
}

// Todo el cálculo de abajo (periodos, total cubierto) ocurre en el navegador,
// a partir de datos ya reales (montoObjetivo lo calculó el backend) — no hay
// llamada de red mientras se arrastra el slider. Solo al tocar el Button que
// sigue a este componente (fuera de aquí) se manda algo al servidor, leyendo
// el mismo path de montoPorPeriodo. Ver ADR-worthy nota en orchestrator.py.
export const ApartadoPlanner = createComponentImplementation(ApartadoPlannerApi, ({ props }) => {
  const monto = typeof props.montoPorPeriodo === 'number' ? props.montoPorPeriodo : props.minMonto;
  const periodos = Math.max(1, Math.ceil(props.montoObjetivo / Math.max(monto, 1)));
  const total = periodos * monto;
  const alcanzaCompleto = total >= props.montoObjetivo;

  function handleChange(event) {
    props.setMontoPorPeriodo?.(Number(event.target.value));
  }

  return (
    <div className="apartado-planner">
      {props.title && <p className="apartado-planner-title">{props.title}</p>}
      {props.subtitle && <p className="apartado-planner-subtitle">{props.subtitle}</p>}

      <div className="apartado-planner-result">
        <span className="apartado-planner-periodos">{periodos}</span>
        <span className="apartado-planner-periodos-label">
          pago{periodos === 1 ? '' : 's'} {props.periodicidadLabel}es de {formatMonto(monto)}
        </span>
      </div>

      <input
        type="range"
        className="apartado-planner-slider"
        min={props.minMonto}
        max={props.maxMonto}
        step="1"
        value={monto}
        onChange={handleChange}
        aria-label={props.title || 'Ajustar monto por periodo'}
      />
      <div className="apartado-planner-range-labels">
        <span>{formatMonto(props.minMonto)}</span>
        <span>{formatMonto(props.maxMonto)}</span>
      </div>

      <p className={`apartado-planner-total ${alcanzaCompleto ? 'apartado-planner-total-ok' : 'apartado-planner-total-corto'}`}>
        Total cubierto: {formatMonto(total)} de {formatMonto(props.montoObjetivo)}
      </p>
    </div>
  );
});
