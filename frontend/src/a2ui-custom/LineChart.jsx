import { createComponentImplementation } from '@a2ui/react/v0_9';
import { LineChartApi } from './schemas.js';

const VIEW_W = 600;
const VIEW_H = 220;
const PAD_X = 12;
const PAD_TOP = 28;
const PAD_BOTTOM = 34;

function formatValue(prefix, value) {
  return `${prefix}${value.toLocaleString('es-MX', { maximumFractionDigits: 0 })}`;
}

export const LineChart = createComponentImplementation(LineChartApi, ({ props }) => {
  const points = Array.isArray(props.points) ? props.points : [];
  const prefix = props.valuePrefix || '';
  if (points.length < 2) {
    return null;
  }

  const values = points.map((p) => p.value);
  const hasThreshold = typeof props.thresholdValue === 'number';
  const allValues = hasThreshold ? [...values, props.thresholdValue] : values;
  const rawMin = Math.min(...allValues);
  const rawMax = Math.max(...allValues);
  // Un poco de aire arriba/abajo para que la línea nunca toque el borde.
  const span = rawMax - rawMin || 1;
  const min = rawMin - span * 0.1;
  const max = rawMax + span * 0.1;

  const plotW = VIEW_W - PAD_X * 2;
  const plotH = VIEW_H - PAD_TOP - PAD_BOTTOM;

  const xAt = (i) => PAD_X + (i / (points.length - 1)) * plotW;
  const yAt = (value) => PAD_TOP + plotH - ((value - min) / (max - min)) * plotH;

  const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${xAt(i)} ${yAt(p.value)}`).join(' ');
  const areaPath = `${linePath} L ${xAt(points.length - 1)} ${PAD_TOP + plotH} L ${xAt(0)} ${PAD_TOP + plotH} Z`;

  const criticalIndex = points.findIndex((p) => p.tone === 'negative' || p.tone === 'warning');

  return (
    <div className="line-chart">
      {props.title && <p className="line-chart-title">{props.title}</p>}
      <svg className="line-chart-svg" viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} preserveAspectRatio="none">
        <path className="line-chart-area" d={areaPath} />
        {hasThreshold && (
          <>
            <line
              className="line-chart-threshold"
              x1={PAD_X}
              x2={VIEW_W - PAD_X}
              y1={yAt(props.thresholdValue)}
              y2={yAt(props.thresholdValue)}
            />
            {props.thresholdLabel && (
              <text className="line-chart-threshold-label" x={VIEW_W - PAD_X} y={yAt(props.thresholdValue) - 4}>
                {props.thresholdLabel}
              </text>
            )}
          </>
        )}
        <path className="line-chart-line" d={linePath} />
        {points.map((p, i) => {
          const tone = p.tone || 'neutral';
          const isCritical = i === criticalIndex;
          return (
            <g key={`${p.label}-${i}`}>
              <circle
                className={`line-chart-dot line-chart-dot-${tone}`}
                cx={xAt(i)}
                cy={yAt(p.value)}
                r={isCritical ? 6 : 4}
              />
              {isCritical && (
                <text className="line-chart-value-label" x={xAt(i)} y={yAt(p.value) - 12}>
                  {formatValue(prefix, p.value)}
                </text>
              )}
              <text className="line-chart-x-label" x={xAt(i)} y={VIEW_H - 10}>
                {p.label}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
});
