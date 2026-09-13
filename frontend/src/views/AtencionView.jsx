import { useEffect, useMemo, useState } from 'react';
import { MessageProcessor } from '@a2ui/web_core/v0_9';
import { A2uiSurface } from '@a2ui/react/v0_9';
import { meAlcanzaCatalog } from '../a2ui-custom/catalog.js';
import { apiClient } from '../api/client.js';
import { useApiResource } from '../api/useApiResource.js';
import { createSugerenciaActionHandler } from '../chat/sugerenciaActionHandler.js';
import { dropDuplicateCreateSurface } from '../chat/messageFilter.js';
import { extractSurfaceId } from '../chat/extractSurfaceId.js';
import { extractTituloDescripcion } from '../chat/extractSugerenciaCopy.js';
import AtenderSugerenciaModal from '../components/AtenderSugerenciaModal.jsx';
import { useAuth } from '../auth/AuthContext.jsx';

// Todas las "notificaciones" (avisos que el sistema detecta solas, sin que
// nadie pregunte) viven aquí, en un solo lugar filtrable — antes competían
// por espacio con el chat en el mismo feed de Asistente. Cada tarjeta trae
// su propia UI generativa (misma tarjeta A2UI de siempre) y su botón
// "Atender" ahora pasa por un modal HITL con la opción de pedirle al
// asistente una propuesta de qué hacer, en vez de resolverse solo.
const FILTROS = [
  { id: 'pendiente', label: 'Pendientes' },
  { id: 'atendida', label: 'Atendidas' },
  { id: 'descartada', label: 'Descartadas' },
  { id: 'todas', label: 'Todas' },
];

export default function AtencionView() {
  const { token, logout } = useAuth();
  const [filtro, setFiltro] = useState('pendiente');
  const [errorMessage, setErrorMessage] = useState(null);
  const [pendingAtencion, setPendingAtencion] = useState(null);
  const [propuestas, setPropuestas] = useState({});
  // Ver el comentario en el useEffect que llama a processMessages: este
  // estado no se lee en ningún lado, solo existe para forzar el re-render
  // que expone las superficies recién registradas en processor.model.
  const [, setSurfacesVersion] = useState(0);

  const {
    data: sugerencias,
    reload: reloadSugerencias,
  } = useApiResource(() => apiClient.getSugerencias(token), { onUnauthorized: logout });

  function handleApiError(err, fallback) {
    if (err?.status === 401) {
      logout();
      return;
    }
    setErrorMessage(err?.detail || fallback);
  }

  const sugerenciaActionHandler = useMemo(
    () =>
      createSugerenciaActionHandler({
        atenderSugerencia: (id) => apiClient.atenderSugerencia(token, id),
        descartarSugerencia: (id) => apiClient.descartarSugerencia(token, id),
        requestConfirmacion: ({ sugerenciaId, onConfirm, onCancel }) =>
          setPendingAtencion({ sugerenciaId, onConfirm, onCancel }),
        onResuelta: () => {
          setErrorMessage(null);
          reloadSugerencias();
        },
        onError: (err) => handleApiError(err, 'No se pudo actualizar la notificación, intenta de nuevo.'),
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token],
  );

  const processor = useMemo(
    () => new MessageProcessor([meAlcanzaCatalog], sugerenciaActionHandler),
    [sugerenciaActionHandler],
  );

  useEffect(() => {
    if (!sugerencias) {
      return;
    }
    for (const sugerencia of sugerencias) {
      if (!sugerencia.a2ui_json) {
        continue;
      }
      processor.processMessages(
        dropDuplicateCreateSurface(sugerencia.a2ui_json, new Set(processor.model.surfacesMap.keys())),
      );
    }
    // processMessages no dispara por sí solo un re-render de este componente
    // (el modelo del processor vive fuera de React): sin este bump, la
    // primera vez que se listan las sugerencias, processor.model.getSurface
    // en el render de abajo se evalúa con las superficies aún sin registrar.
    setSurfacesVersion((v) => v + 1);
  }, [sugerencias, processor]);

  async function handleGenerarPropuesta(sugerenciaId) {
    setPropuestas((prev) => ({ ...prev, [sugerenciaId]: { estado: 'cargando' } }));
    try {
      const { propuesta } = await apiClient.getPropuestaSugerencia(token, sugerenciaId);
      setPropuestas((prev) => ({ ...prev, [sugerenciaId]: { estado: 'lista', texto: propuesta } }));
    } catch (err) {
      setPropuestas((prev) => ({ ...prev, [sugerenciaId]: { estado: 'error' } }));
      handleApiError(err, 'No se pudo generar la propuesta, intenta de nuevo.');
    }
  }

  const sugerenciaEnModal =
    pendingAtencion && sugerencias?.find((s) => s.id === pendingAtencion.sugerenciaId);
  const { titulo: tituloModal, descripcion: descripcionModal } = sugerenciaEnModal
    ? extractTituloDescripcion(sugerenciaEnModal.a2ui_json)
    : { titulo: '', descripcion: '' };
  const propuestaModal = pendingAtencion ? propuestas[pendingAtencion.sugerenciaId] : null;

  const visibles = (sugerencias || []).filter((s) => filtro === 'todas' || s.estado === filtro);

  return (
    <div className="atencion-view">
      <div className="atencion-filtros">
        {FILTROS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`atencion-filtro ${f.id === filtro ? 'atencion-filtro-activo' : ''}`}
            onClick={() => setFiltro(f.id)}
          >
            {f.label}
          </button>
        ))}
      </div>
      {errorMessage && <p className="chat-error">{errorMessage}</p>}
      {sugerencias && visibles.length === 0 && (
        <p className="atencion-vacio">No hay notificaciones en este filtro.</p>
      )}
      <div className="atencion-lista">
        {visibles.map((sugerencia) => {
          if (!sugerencia.a2ui_json) {
            // Historial sin tarjeta generativa (ver sugerencias_a2ui.py: solo
            // se arma para estado="pendiente"): fila simple, sin inventar copy.
            return (
              <div className="atencion-historial-item" key={sugerencia.id}>
                <span className="atencion-historial-tipo">{sugerencia.tipo}</span>
                <span className={`atencion-historial-estado atencion-historial-estado-${sugerencia.estado}`}>
                  {sugerencia.estado}
                </span>
                {sugerencia.resuelta_at && (
                  <span className="atencion-historial-fecha">{sugerencia.resuelta_at}</span>
                )}
              </div>
            );
          }
          const surfaceId = extractSurfaceId(sugerencia.a2ui_json);
          const surface = surfaceId && processor.model.getSurface(surfaceId);
          if (!surface) {
            return null;
          }
          return (
            <div className="atencion-tarjeta" key={sugerencia.id}>
              <A2uiSurface surface={surface} />
            </div>
          );
        })}
      </div>
      {pendingAtencion && (
        <AtenderSugerenciaModal
          titulo={tituloModal}
          descripcion={descripcionModal}
          propuestaEstado={propuestaModal?.estado || 'idle'}
          propuesta={propuestaModal?.texto}
          onGenerarPropuesta={() => handleGenerarPropuesta(pendingAtencion.sugerenciaId)}
          onConfirm={() => {
            const { onConfirm } = pendingAtencion;
            setPendingAtencion(null);
            onConfirm();
          }}
          onCancel={() => {
            const { onCancel } = pendingAtencion;
            setPendingAtencion(null);
            onCancel();
          }}
        />
      )}
    </div>
  );
}
