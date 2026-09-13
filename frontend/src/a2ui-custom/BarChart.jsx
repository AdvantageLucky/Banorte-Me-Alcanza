import { createComponentImplementation } from '@a2ui/react/v0_9';
import { BarChartApi } from './schemas.js';

export const BarChart = createComponentImplementation(BarChartApi, ({ props }) => {
  const bars = Array.isArray(props.bars) ? props.bars : [];
  const prefix = props.valuePrefix || '';
  const max = Math.max(1, ...bars.map((b) => Math.abs(b.value)));

  return (
    <div className="bar-chart">
      {props.title && <p className="bar-chart-title">{props.title}</p>}
      <div className="bar-chart-bars">
        {bars.map((bar, index) => {
          const tone = bar.tone || 'neutral';
          const widthPct = Math.max(2, (Math.abs(bar.value) / max) * 100);
          return (
            <div className="bar-chart-row" key={`${bar.label}-${index}`}>
              <span className="bar-chart-row-label">{bar.label}</span>
              <div className="bar-chart-row-track">
                <div
                  className={`bar-chart-row-fill bar-chart-row-fill-${tone}`}
                  style={{ width: `${widthPct}%` }}
                />
              </div>
              <span className="bar-chart-row-value">
                {prefix}
                {bar.value.toLocaleString('es-MX', { maximumFractionDigits: 2 })}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
});
