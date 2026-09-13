import { useState } from 'react';
import { apiClient } from '../../api/client.js';
import { useCrudResource } from '../../api/useCrudResource.js';
import { useAuth } from '../../auth/AuthContext.jsx';
import ResourceState from './ResourceState.jsx';

function emptyForm() {
  return { nombre: '', alias: '', cuenta_destino: '', relacion: '' };
}

export default function ContactosTab() {
  const { token, logout } = useAuth();
  const { data: contactos, loading, error, reload, submitting, formError, clearFormError, create, update, remove } =
    useCrudResource(() => apiClient.getContactos(token), { onUnauthorized: logout });

  const [mode, setMode] = useState(null); // null | 'create' | id en edición
  const [form, setForm] = useState(emptyForm());

  function startCreate() {
    clearFormError();
    setForm(emptyForm());
    setMode('create');
  }

  function startEdit(contacto) {
    clearFormError();
    setForm({
      nombre: contacto.nombre,
      alias: contacto.alias,
      cuenta_destino: contacto.cuenta_destino,
      relacion: contacto.relacion,
    });
    setMode(contacto.id);
  }

  function cancelForm() {
    clearFormError();
    setMode(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const ok =
      mode === 'create'
        ? await create(() => apiClient.createContacto(token, form))
        : await update(() => apiClient.updateContacto(token, mode, form));
    if (ok) {
      setMode(null);
    }
  }

  async function handleDelete(contacto) {
    if (!window.confirm(`¿Eliminar a "${contacto.nombre}" de tus contactos?`)) {
      return;
    }
    await remove(() => apiClient.deleteContacto(token, contacto.id));
  }

  return (
    <div className="yo-section">
      <div className="yo-toolbar">
        {mode === null && (
          <button type="button" className="yo-btn-primary" onClick={startCreate}>
            + Nuevo contacto
          </button>
        )}
      </div>

      {mode !== null && (
        <form className="yo-form" onSubmit={handleSubmit}>
          <div className="yo-form-row">
            <label>
              Nombre
              <input
                type="text"
                required
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </label>
            <label>
              Alias
              <input
                type="text"
                required
                value={form.alias}
                onChange={(e) => setForm({ ...form, alias: e.target.value })}
              />
            </label>
          </div>
          <div className="yo-form-row">
            <label>
              Cuenta destino
              <input
                type="text"
                required
                value={form.cuenta_destino}
                onChange={(e) => setForm({ ...form, cuenta_destino: e.target.value })}
              />
            </label>
            <label>
              Relación
              <input
                type="text"
                required
                placeholder="hermano, amiga, etc."
                value={form.relacion}
                onChange={(e) => setForm({ ...form, relacion: e.target.value })}
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
        isEmpty={!contactos?.length}
        emptyMessage="Todavía no tienes contactos guardados."
      >
        <ul className="yo-list">
          {contactos?.map((contacto) => (
            <li key={contacto.id} className="yo-card yo-contacto">
              <div>
                <p className="yo-contacto-nombre">{contacto.nombre} <span className="yo-contacto-alias">({contacto.alias})</span></p>
                <p className="yo-contacto-detalle">{contacto.relacion} · cuenta {contacto.cuenta_destino}</p>
              </div>
              <div className="yo-card-actions">
                <button type="button" onClick={() => startEdit(contacto)}>
                  Editar
                </button>
                <button type="button" className="yo-btn-danger" onClick={() => handleDelete(contacto)}>
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
