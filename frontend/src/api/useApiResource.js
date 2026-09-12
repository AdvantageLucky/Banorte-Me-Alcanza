import { useCallback, useEffect, useState } from 'react';

// Hook compartido por las pestañas de "Yo": pide un recurso de solo lectura
// al montar, expone loading/error/data y un `reload` para el botón de
// reintentar. Mismo manejo de 401 que ya usa ChatView (cerrar sesión en vez
// de mostrar un error genérico), para no duplicar ese criterio 6 veces.
export function useApiResource(fetchFn, { onUnauthorized } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      if (err?.status === 401 && onUnauthorized) {
        onUnauthorized();
        return;
      }
      setError(err?.detail || 'No se pudo cargar la información, intenta de nuevo.');
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}
