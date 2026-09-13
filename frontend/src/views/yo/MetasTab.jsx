import { useState } from 'react';
import { apiClient } from '../../api/client.js';
import { useCrudResource } from '../../api/useCrudResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';
import { formatFecha, formatMonto } from './formatters.js';

function emptyForm() {
  return { descripcion: '', monto_objetivo: '', fecha_objetivo: '' };
}

export default function MetasTab() {
  const { token, logout } = useAuth();
  const { data: metas, loading, error, reload, submitting, formError, clearFormError, create, update, remove } =
    useCrudResource(() => apiClient.getMetas(token), { onUnauthorized: logout });

  const [mode, setMode] = useState(null); // null | 'create' | id en edición
  const [form, setForm] = useState(emptyForm());

  function startCreate() {
    clearFormError();
    setForm(emptyForm());
    setMode('create');
  }

  function startEdit(meta) {
    clearFormError();
    setForm({
      descripcion: meta.descripcion,
      monto_objetivo: String(meta.monto_objetivo),
      fecha_objetivo: meta.fecha_objetivo,
    });
    setMode(meta.id);
  }

  function cancelForm() {
    clearFormError();
    setMode(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const payload = {
      descripcion: form.descripcion,
      monto_objetivo: Number(form.monto_objetivo),
      fecha_objetivo: form.fecha_objetivo,
    };
    const ok =
      mode === 'create'
        ? await create(() => apiClient.createMeta(token, payload))
        : await update(() => apiClient.updateMeta(token, mode, payload));
    if (ok) {
      setMode(null);
    }
  }

  async function handleDelete(meta) {
    if (!window.confirm(`¿Eliminar la meta "${meta.descripcion}"?`)) {
      return;
    }
    await remove(() => apiClient.deleteMeta(token, meta.id));
  }

  return (
    <div className="yo-section">
      <div className="yo-toolbar">
        {mode === null && (
          <button type="button" className="yo-btn-primary" onClick={startCreate}>
            + Nueva meta
          </button>
        )}
      </div>

      {mode !== null && (
        <form className="yo-form" onSubmit={handleSubmit}>
          <div className="yo-form-row">
            <label>
              Descripción
              <input
                type="text"
                required
                value={form.descripcion}
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              />
            </label>
            <label>
              Monto objetivo
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={form.monto_objetivo}
                onChange={(e) => setForm({ ...form, monto_objetivo: e.target.value })}
              />
            </label>
          </div>
          <div className="yo-form-row">
            <label>
              Fecha objetivo
              <input
                type="date"
                required
                value={form.fecha_objetivo}
                onChange={(e) => setForm({ ...form, fecha_objetivo: e.target.value })}
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
        isEmpty={!metas?.length}
        emptyMessage="Todavía no tienes metas de ahorro."
      >
        <ul className="yo-list">
          {metas?.map((meta) => {
            const progreso = meta.monto_objetivo > 0
              ? Math.min(100, Math.round((meta.monto_ahorrado / meta.monto_objetivo) * 100))
              : 0;
            return (
              <li key={meta.id} className="yo-card yo-meta">
                <p className="yo-meta-descripcion">{meta.descripcion}</p>
                <div className="yo-meta-progreso-track">
                  <div className="yo-meta-progreso-fill" style={{ width: `${progreso}%` }} />
                </div>
                <p className="yo-meta-montos">
                  {formatMonto(meta.monto_ahorrado)} de {formatMonto(meta.monto_objetivo)}
                </p>
                <p className="yo-meta-fecha">Meta: {formatFecha(meta.fecha_objetivo)}</p>
                <div className="yo-card-actions">
                  <button type="button" onClick={() => startEdit(meta)}>
                    Editar
                  </button>
                  <button type="button" className="yo-btn-danger" onClick={() => handleDelete(meta)}>
                    Eliminar
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      </ResourceState>
    </div>
  );
}
