import { useState } from 'react';
import { useAuth } from '../../auth/AuthContext.jsx';
import { useCrudResource } from '../../api/useCrudResource.js';
import ResourceState from './ResourceState.jsx';
import { formatFecha, formatMonto } from './formatters.js';

const FRECUENCIAS = ['semanal', 'quincenal', 'mensual', 'anual'];

function emptyForm() {
  return { label: '', monto: '', frecuencia: 'mensual', proxima_fecha: '' };
}

function toPayload(labelField, form) {
  return {
    [labelField]: form.label,
    monto: Number(form.monto),
    frecuencia: form.frecuencia,
    proxima_fecha: form.proxima_fecha,
  };
}

// Pagos fijos e ingresos programados comparten exactamente la misma forma
// ({concepto|descripcion, monto, frecuencia, proxima_fecha}) — una sola
// pestaña genérica evita duplicar el mismo card (y ahora el mismo
// crear/editar/borrar) dos veces.
export default function RecurrenteTab({ fetchFn, createFn, updateFn, deleteFn, labelField, labelText, emptyMessage }) {
  const { token, logout } = useAuth();
  const { data: items, loading, error, reload, submitting, formError, clearFormError, create, update, remove } =
    useCrudResource(() => fetchFn(token), { onUnauthorized: logout });

  const [mode, setMode] = useState(null); // null | 'create' | número de id en edición
  const [form, setForm] = useState(emptyForm());

  function startCreate() {
    clearFormError();
    setForm(emptyForm());
    setMode('create');
  }

  function startEdit(item) {
    clearFormError();
    setForm({
      label: item[labelField],
      monto: String(item.monto),
      frecuencia: item.frecuencia,
      proxima_fecha: item.proxima_fecha,
    });
    setMode(item.id);
  }

  function cancelForm() {
    clearFormError();
    setMode(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const payload = toPayload(labelField, form);
    const ok =
      mode === 'create'
        ? await create(() => createFn(token, payload))
        : await update(() => updateFn(token, mode, payload));
    if (ok) {
      setMode(null);
    }
  }

  async function handleDelete(item) {
    if (!window.confirm(`¿Eliminar "${item[labelField]}"?`)) {
      return;
    }
    await remove(() => deleteFn(token, item.id));
  }

  return (
    <div className="yo-section">
      <div className="yo-toolbar">
        {mode === null && (
          <button type="button" className="yo-btn-primary" onClick={startCreate}>
            + Agregar
          </button>
        )}
      </div>

      {mode !== null && (
        <form className="yo-form" onSubmit={handleSubmit}>
          <div className="yo-form-row">
            <label>
              {labelText}
              <input
                type="text"
                required
                value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })}
              />
            </label>
            <label>
              Monto
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={form.monto}
                onChange={(e) => setForm({ ...form, monto: e.target.value })}
              />
            </label>
          </div>
          <div className="yo-form-row">
            <label>
              Frecuencia
              <select value={form.frecuencia} onChange={(e) => setForm({ ...form, frecuencia: e.target.value })}>
                {FRECUENCIAS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Próxima fecha
              <input
                type="date"
                required
                value={form.proxima_fecha}
                onChange={(e) => setForm({ ...form, proxima_fecha: e.target.value })}
              />
            </label>
          </div>
          {formError && <p className="yo-form-error">{formError}</p>}
          <div className="yo-form-actions">
            <button type="button" onClick={cancelForm} disabled={submitting}>
              Cancelar
            </button>
            <button type="submit" className="yo-btn-primary" disabled={submitting}>
              {submitting ? 'Guardando...' : 'Guardar'}
            </button>
          </div>
        </form>
      )}

      <ResourceState
        loading={loading}
        error={error}
        reload={reload}
        isEmpty={!items?.length}
        emptyMessage={emptyMessage}
      >
        <ul className="yo-list">
          {items?.map((item) => (
            <li key={item.id} className="yo-card yo-recurrente">
              <div>
                <p className="yo-recurrente-label">{item[labelField]}</p>
                <p className="yo-recurrente-detalle">{item.frecuencia} · próxima: {formatFecha(item.proxima_fecha)}</p>
              </div>
              <p className="yo-monto">{formatMonto(item.monto)}</p>
              <div className="yo-card-actions">
                <button type="button" onClick={() => startEdit(item)}>
                  Editar
                </button>
                <button type="button" className="yo-btn-danger" onClick={() => handleDelete(item)}>
                  Eliminar
                </button>
              </div>
            </li>
          ))}
        </ul>
      </ResourceState>
    </div>
  );
}
