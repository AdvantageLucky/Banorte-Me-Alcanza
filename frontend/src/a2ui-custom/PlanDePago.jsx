import { createComponentImplementation } from '@a2ui/react/v0_9';
import { PlanDePagoApi } from './schemas.js';

export const PlanDePago = createComponentImplementation(PlanDePagoApi, ({ props }) => {
  const options = Array.isArray(props.options) ? props.options : [];
  const selectedId = typeof props.selectedId === 'string' ? props.selectedId : '';

  return (
    <div className="plan-de-pago">
      {props.title && <p className="plan-de-pago-title">{props.title}</p>}
      {props.subtitle && <p className="plan-de-pago-subtitle">{props.subtitle}</p>}
      <div className="plan-de-pago-options">
        {options.map((option) => {
          const isSelected = option.id === selectedId;
          return (
            <button
              type="button"
              key={option.id}
              className={`plan-de-pago-option ${isSelected ? 'plan-de-pago-option-selected' : ''} ${
                option.highlighted ? 'plan-de-pago-option-highlighted' : ''
              }`}
              onClick={() => props.setSelectedId?.(option.id)}
            >
              <span className="plan-de-pago-option-label">{option.label}</span>
              <span className="plan-de-pago-option-detail">{option.detail}</span>
              <span className="plan-de-pago-option-amount">{option.amount}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
});
