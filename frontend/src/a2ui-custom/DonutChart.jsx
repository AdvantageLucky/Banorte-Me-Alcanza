import { createComponentImplementation } from '@a2ui/react/v0_9';
import { DonutChartApi } from './schemas.js';

const SIZE = 180;
const STROKE = 26;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// Paleta fija asignada por posición, no por nombre de categoría: 'categoria'
// viene de datos reales (get_resumen_movimientos) y es texto libre, así que
// no podemos mapear colores a nombres conocidos de antemano.
const PALETTE = ['#ec0029', '#1a8f4c', '#b9770e', '#2f6fed', '#8a4fd8', '#0f9aa8', '#6a6867'];

function formatMonto(monto) {
  return monto.toLocaleString('es-MX', { style: 'currency', currency: 'MXN', maximumFractionDigits: 0 });
}

export const DonutChart = createComponentImplementation(DonutChartApi, ({ props }) => {
  const slices = Array.isArray(props.slices) ? props.slices : [];
  if (slices.length < 2) {
    return null;
  }
  const total = slices.reduce((sum, s) => sum + Math.abs(s.value), 0) || 1;

  let acumulado = 0;
  const arcos = slices.map((slice, index) => {
    const pct = Math.abs(slice.value) / total;
    const dash = pct * CIRCUMFERENCE;
    const offset = acumulado * CIRCUMFERENCE;
    acumulado += pct;
    return {
      ...slice,
      pct,
      dash,
      offset,
      color: PALETTE[index % PALETTE.length],
    };
  });

  function seleccionar(id) {
    props.setSelectedId?.(id === props.selectedId ? undefined : id);
  }

  return (
    <div className="donut-chart">
      {props.title && <p className="donut-chart-title">{props.title}</p>}
      <div className="donut-chart-body">
        <svg
          className="donut-chart-svg"
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
        >
          <g transform={`translate(${SIZE / 2}, ${SIZE / 2}) rotate(-90)`}>
            {arcos.map((arco) => {
              const isSelected = props.selectedId && arco.id === props.selectedId;
              return (
                <circle
                  key={arco.id}
                  className="donut-chart-arc"
                  r={RADIUS}
                  cx={0}
                  cy={0}
                  fill="none"
                  stroke={arco.color}
                  strokeWidth={isSelected ? STROKE + 6 : STROKE}
                  strokeDasharray={`${arco.dash} ${CIRCUMFERENCE - arco.dash}`}
                  strokeDashoffset={-arco.offset}
                  opacity={props.selectedId && !isSelected ? 0.45 : 1}
                  onClick={() => seleccionar(arco.id)}
                  style={{ cursor: 'pointer', transition: 'stroke-width 0.15s ease, opacity 0.15s ease' }}
                />
              );
            })}
          </g>
          {(props.centerLabel || props.centerValue) && (
            <g textAnchor="middle">
              {props.centerValue && (
                <text className="donut-chart-center-value" x={SIZE / 2} y={SIZE / 2 - 2}>
                  {props.centerValue}
                </text>
              )}
              {props.centerLabel && (
                <text className="donut-chart-center-label" x={SIZE / 2} y={SIZE / 2 + 18}>
                  {props.centerLabel}
                </text>
              )}
            </g>
          )}
        </svg>

        <ul className="donut-chart-legend">
          {arcos.map((arco) => {
            const isSelected = props.selectedId && arco.id === props.selectedId;
            return (
              <li key={arco.id}>
                <button
                  type="button"
                  className={`donut-chart-legend-row ${isSelected ? 'donut-chart-legend-row-selected' : ''}`}
                  onClick={() => seleccionar(arco.id)}
                >
                  <span className="donut-chart-legend-swatch" style={{ background: arco.color }} />
                  <span className="donut-chart-legend-label">{arco.label}</span>
                  <span className="donut-chart-legend-pct">{Math.round(arco.pct * 100)}%</span>
                  <span className="donut-chart-legend-value">{formatMonto(arco.value)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
});
