import { useState } from 'react';
import { apiClient } from '../../api/client.js';
import { useApiResource } from '../../api/useApiResource.js';
import { useCrudResource } from '../../api/useCrudResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';
import { formatFecha, formatMonto } from './formatters.js';

const FRECUENCIAS = ['semanal', 'quincenal', 'mensual', 'anual'];

function emptyForm(metas) {
  return { meta_id: metas?.[0]?.id ?? '', monto_por_periodo: '', periodicidad: 'mensual' };
}

export default function ApartadosTab() {
  const { token, logout } = useAuth();
  const { data: apartados, loading, error, reload, submitting, formError, clearFormError, create, remove } =
    useCrudResource(() => apiClient.getApartados(token), { onUnauthorized: logout });
  // El apartado solo puede apuntar a una meta ya existente — se necesita esa
  // lista para el selector del formulario. No se usa useCrudResource aquí
  // porque este recurso no se muta desde esta pestaña, solo se lee.
  const { data: metas } = useApiResource(() => apiClient.getMetas(token), { onUnauthorized: logout });

  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(emptyForm(metas));

  function startCreate() {
    clearFormError();
    setForm(emptyForm(metas));
    setCreating(true);
  }

  function cancelForm() {
    clearFormError();
    setCreating(false);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const payload = {
      meta_id: Number(form.meta_id),
      monto_por_periodo: Number(form.monto_por_periodo),
      periodicidad: form.periodicidad,
    };
    const ok = await create(() => apiClient.createApartado(token, payload));
    if (ok) {
      setCreating(false);
    }
  }

  async function handleCancelar(apartado) {
    if (!window.confirm('¿Cancelar este apartado automático?')) {
      return;
    }
    await remove(() => apiClient.cancelarApartado(token, apartado.id));
  }

  const sinMetas = !metas?.length;

  return (
    <div className="yo-section">
      <div className="yo-toolbar">
        {!creating && (
          <button type="button" className="yo-btn-primary" onClick={startCreate} disabled={sinMetas}>
            + Nuevo apartado
          </button>
        )}
        {sinMetas && !creating && (
          <span className="yo-toolbar-hint">Crea una meta primero para poder apartar hacia ella.</span>
        )}
      </div>

      {creating && (
        <form className="yo-form" onSubmit={handleSubmit}>
          <div className="yo-form-row">
            <label>
              Meta
              <select value={form.meta_id} onChange={(e) => setForm({ ...form, meta_id: e.target.value })}>
                {metas?.map((meta) => (
                  <option key={meta.id} value={meta.id}>
                    {meta.descripcion}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Monto por periodo
              <input
                type="number"
                step="0.01"
                min="0.01"
                required
                value={form.monto_por_periodo}
                onChange={(e) => setForm({ ...form, monto_por_periodo: e.target.value })}
              />
            </label>
          </div>
          <div className="yo-form-row">
            <label>
              Periodicidad
              <select
                value={form.periodicidad}
                onChange={(e) => setForm({ ...form, periodicidad: e.target.value })}
              >
                {FRECUENCIAS.map((f) => (
                  <option key={f} value={f}>
                    {f}
                  </option>
                ))}
              </select>
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
        isEmpty={!apartados?.length}
        emptyMessage="No tienes apartados automáticos configurados."
      >
        <ul className="yo-list">
          {apartados?.map((apartado) => (
            <li key={apartado.id} className="yo-card yo-apartado">
              <div>
                <p className="yo-apartado-monto">{formatMonto(apartado.monto_por_periodo)} / {apartado.periodicidad}</p>
                <p className="yo-apartado-detalle">Meta #{apartado.meta_id} · desde {formatFecha(apartado.fecha_inicio)}</p>
              </div>
              <span className={`yo-badge yo-badge-${apartado.estado}`}>{apartado.estado}</span>
              {apartado.estado === 'activo' && (
                <div className="yo-card-actions">
                  <button type="button" className="yo-btn-danger" onClick={() => handleCancelar(apartado)}>
                    Cancelar
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </ResourceState>
    </div>
  );
}
