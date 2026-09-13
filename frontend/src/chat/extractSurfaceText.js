// Extrae, en texto plano, todo lo "leíble" de una respuesta A2UI, para que
// el botón de "escuchar en voz alta" (TTS, accesibilidad) tenga algo que
// leer sin duplicar cómo cada componente se renderiza.
//
// Los componentes que arma el backend son objetos "planos"
// ({id, component, ...props}, ver orchestrator.py/sugerencias_a2ui.py):
// nada de envoltura tipo componentProperties. Cada prop de contenido puede
// ser un literal (string/number) o un binding {path: "/algo"} que se
// resuelve contra el dataModel que llega en un mensaje updateDataModel
// aparte (mismo turno). No hay generación automática desde el catálogo:
// esta lista de keys "de contenido" se mantiene a mano igual que
// extractTituloDescripcion.js.
const CONTENT_KEYS = new Set([
  'text',
  'label',
  'title',
  'subtitle',
  'value',
  'trendLabel',
  'detail',
  'amount',
  'description',
  'placeholder',
  'hint',
]);

function isBinding(node) {
  return (
    node && typeof node === 'object' && !Array.isArray(node) && typeof node.path === 'string'
  );
}

function splitPointer(path) {
  return (path || '').split('/').filter(Boolean);
}

// Sigue las mismas reglas simples de path que usa el backend: path "/" (o
// vacío) mezcla `value` en la raíz del modelo; cualquier otro path anida.
function applyDataModelUpdate(model, { path, value }) {
  const segments = splitPointer(path);
  if (segments.length === 0) {
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return { ...model, ...value };
    }
    // Un valor no-objeto en la raíz es una actualización malformada (todo
    // productor real manda un objeto, ver orchestrator.py/
    // sugerencias_a2ui.py): se descarta en vez de reemplazar el modelo
    // entero, igual que en extract_surface_text.dart.
    return model;
  }
  const next = { ...model };
  let cursor = next;
  segments.forEach((segment, index) => {
    if (index === segments.length - 1) {
      cursor[segment] = value;
      return;
    }
    cursor[segment] = { ...(cursor[segment] || {}) };
    cursor = cursor[segment];
  });
  return next;
}

function buildDataModel(messages, surfaceId) {
  let model = {};
  for (const message of messages) {
    const update = message?.updateDataModel;
    if (!update || update.surfaceId !== surfaceId) {
      continue;
    }
    model = applyDataModelUpdate(model, update);
  }
  return model;
}

function resolveBinding(binding, dataModel) {
  const segments = splitPointer(binding.path);
  let cursor = dataModel;
  for (const segment of segments) {
    if (cursor == null) {
      return undefined;
    }
    cursor = cursor[segment];
  }
  return cursor;
}

function pushIfContent(value, out) {
  if (typeof value === 'string' && value.trim() !== '') {
    out.push(value.trim());
  } else if (typeof value === 'number' && Number.isFinite(value)) {
    out.push(String(value));
  }
}

function walk(node, dataModel, out) {
  if (Array.isArray(node)) {
    // Los arrays de contenido real (options, bars, ...) traen objetos; los
    // arrays de puros ids (p.ej. "children") no aportan texto leíble.
    node.filter((item) => item && typeof item === 'object').forEach((item) => walk(item, dataModel, out));
    return;
  }
  if (!node || typeof node !== 'object') {
    return;
  }
  for (const [key, value] of Object.entries(node)) {
    if (isBinding(value)) {
      if (CONTENT_KEYS.has(key)) {
        pushIfContent(resolveBinding(value, dataModel), out);
      }
      continue;
    }
    if (CONTENT_KEYS.has(key) && (typeof value === 'string' || typeof value === 'number')) {
      pushIfContent(value, out);
      continue;
    }
    if (value && typeof value === 'object') {
      walk(value, dataModel, out);
    }
  }
}

export function extractSurfaceText(messages) {
  if (!Array.isArray(messages)) {
    return '';
  }
  const createMessage = messages.find((message) => message?.createSurface);
  const surfaceId = createMessage?.createSurface?.surfaceId ?? null;
  const componentMessages = messages.filter(
    (message) => message?.updateComponents && (!surfaceId || message.updateComponents.surfaceId === surfaceId),
  );
  if (componentMessages.length === 0) {
    return '';
  }
  const dataModel = buildDataModel(messages, surfaceId);
  const out = [];
  for (const message of componentMessages) {
    walk(message.updateComponents.components, dataModel, out);
  }
  return joinReadable(out);
}

// Simple join('. ') duplicaría el punto cuando un fragmento (p.ej. un
// título completo) ya termina en puntuación propia.
function joinReadable(fragments) {
  return fragments.reduce((acc, fragment, index) => {
    if (index === 0) {
      return fragment;
    }
    const separator = /[.!?]$/.test(acc) ? ' ' : '. ';
    return acc + separator + fragment;
  }, '');
}
