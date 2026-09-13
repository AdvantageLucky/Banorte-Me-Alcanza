import { createComponentImplementation } from '@a2ui/react/v0_9';
import { StatCardApi } from './schemas.js';

const TREND_ARROW = { up: '↑', down: '↓', flat: '→' };

export const StatCard = createComponentImplementation(StatCardApi, ({ props }) => {
  const tone = props.tone || 'neutral';
  const label = typeof props.label === 'string' ? props.label : String(props.label ?? '');
  const value = typeof props.value === 'string' ? props.value : String(props.value ?? '');

  return (
    <div className={`stat-card stat-card-${tone}`}>
      <p className="stat-card-label">{label}</p>
      <p className="stat-card-value">{value}</p>
      {props.trendLabel && (
        <p className="stat-card-trend">
          {props.trend && <span className="stat-card-trend-arrow">{TREND_ARROW[props.trend] || ''}</span>}
          {typeof props.trendLabel === 'string' ? props.trendLabel : String(props.trendLabel)}
        </p>
      )}
    </div>
  );
});
