import { useState } from 'react';
import { useApiResource } from './useApiResource.js';

// Extiende useApiResource (que ya maneja loading/error/reload de solo
// lectura) con create/update/remove: cada uno corre la mutación, y si
// funciona recarga la lista — así el estado siempre refleja lo que el
// backend confirmó, nunca un optimistic-update que podría desincronizarse
// si el backend rechaza el cambio (ej. "monto debe ser mayor a cero").
export function useCrudResource(fetchFn, { onUnauthorized } = {}) {
  const resource = useApiResource(fetchFn, { onUnauthorized });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  async function runMutation(mutationFn) {
    setSubmitting(true);
    setFormError(null);
    try {
      await mutationFn();
      await resource.reload();
      return true;
    } catch (err) {
      if (err?.status === 401 && onUnauthorized) {
        onUnauthorized();
        return false;
      }
      setFormError(err?.detail || 'No se pudo guardar el cambio, intenta de nuevo.');
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  return {
    ...resource,
    submitting,
    formError,
    clearFormError: () => setFormError(null),
    create: (mutationFn) => runMutation(mutationFn),
    update: (mutationFn) => runMutation(mutationFn),
    remove: (mutationFn) => runMutation(mutationFn),
  };
}
