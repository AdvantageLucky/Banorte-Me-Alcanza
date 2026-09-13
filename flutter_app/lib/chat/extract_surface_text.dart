// flutter_app/lib/chat/extract_surface_text.dart
//
// Extrae, en texto plano, todo lo "leíble" de una respuesta A2UI, para que
// el botón de "escuchar en voz alta" (TTS, accesibilidad) tenga algo que
// leer sin duplicar cómo cada componente se renderiza.
//
// Los componentes que arma el backend son mapas "planos"
// ({id, component, ...props}, ver orchestrator.py/sugerencias_a2ui.py):
// nada de envoltura anidada. Cada prop de contenido puede ser un literal
// (String/num) o un binding {path: "/algo"} que se resuelve contra el
// dataModel que llega en un mensaje updateDataModel aparte (mismo turno).
// Misma lista de keys "de contenido", a mano, que
// frontend/src/chat/extractSurfaceText.js — se mantienen en sync entre
// plataformas porque no hay generación automática desde el catálogo.
const _contentKeys = {
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
};

bool _isBinding(Object? node) {
  return node is Map && node.length == 1 && node['path'] is String;
}

List<String> _splitPointer(String? path) {
  if (path == null) return const [];
  return path.split('/').where((segment) => segment.isNotEmpty).toList();
}

// Sigue las mismas reglas simples de path que usa el backend: path "/" (o
// vacío) mezcla `value` en la raíz del modelo; cualquier otro path anida.
Map<String, dynamic> _applyDataModelUpdate(
  Map<String, dynamic> model,
  Map<String, dynamic> update,
) {
  final segments = _splitPointer(update['path'] as String?);
  final value = update['value'];
  if (segments.isEmpty) {
    if (value is Map) {
      return {...model, ...value.cast<String, dynamic>()};
    }
    return model;
  }
  final next = Map<String, dynamic>.from(model);
  var cursor = next;
  for (var i = 0; i < segments.length; i++) {
    final segment = segments[i];
    if (i == segments.length - 1) {
      cursor[segment] = value;
    } else {
      final existing = cursor[segment];
      final nested = existing is Map
          ? Map<String, dynamic>.from(existing)
          : <String, dynamic>{};
      cursor[segment] = nested;
      cursor = nested;
    }
  }
  return next;
}

Map<String, dynamic> _buildDataModel(List<dynamic> messages, String? surfaceId) {
  var model = <String, dynamic>{};
  for (final message in messages) {
    if (message is! Map) continue;
    final update = message['updateDataModel'];
    if (update is! Map || update['surfaceId'] != surfaceId) continue;
    model = _applyDataModelUpdate(model, update.cast<String, dynamic>());
  }
  return model;
}

dynamic _resolveBinding(Map binding, Map<String, dynamic> dataModel) {
  final segments = _splitPointer(binding['path'] as String?);
  dynamic cursor = dataModel;
  for (final segment in segments) {
    if (cursor is! Map) return null;
    cursor = cursor[segment];
  }
  return cursor;
}

void _pushIfContent(Object? value, List<String> out) {
  if (value is String && value.trim().isNotEmpty) {
    out.add(value.trim());
  } else if (value is num) {
    out.add(value.toString());
  }
}

void _walk(Object? node, Map<String, dynamic> dataModel, List<String> out) {
  if (node is List) {
    // Los arrays de contenido real (options, bars, ...) traen objetos; los
    // arrays de puros ids (p.ej. "children") no aportan texto leíble.
    for (final item in node) {
      if (item is Map || item is List) {
        _walk(item, dataModel, out);
      }
    }
    return;
  }
  if (node is! Map) return;
  node.forEach((key, value) {
    final keyStr = key as String;
    if (_isBinding(value)) {
      if (_contentKeys.contains(keyStr)) {
        _pushIfContent(_resolveBinding(value as Map, dataModel), out);
      }
      return;
    }
    if (_contentKeys.contains(keyStr) && (value is String || value is num)) {
      _pushIfContent(value, out);
      return;
    }
    if (value is Map || value is List) {
      _walk(value, dataModel, out);
    }
  });
}

// join('. ') duplicaría el punto cuando un fragmento (p.ej. un título
// completo) ya termina en puntuación propia.
String _joinReadable(List<String> fragments) {
  final sentenceEnd = RegExp(r'[.!?]$');
  var result = '';
  for (var i = 0; i < fragments.length; i++) {
    if (i == 0) {
      result = fragments[i];
      continue;
    }
    final separator = sentenceEnd.hasMatch(result) ? ' ' : '. ';
    result = '$result$separator${fragments[i]}';
  }
  return result;
}

String extractSurfaceText(List<dynamic>? messages) {
  if (messages == null) return '';
  final createMessage = messages.cast<dynamic>().firstWhere(
    (message) => message is Map && message['createSurface'] != null,
    orElse: () => null,
  );
  String? surfaceId;
  if (createMessage is Map) {
    final createSurface = createMessage['createSurface'];
    if (createSurface is Map) {
      surfaceId = createSurface['surfaceId'] as String?;
    }
  }
  final componentMessages = messages.where((message) {
    if (message is! Map) return false;
    final updateComponents = message['updateComponents'];
    if (updateComponents is! Map) return false;
    return surfaceId == null || updateComponents['surfaceId'] == surfaceId;
  }).toList();
  if (componentMessages.isEmpty) return '';

  final dataModel = _buildDataModel(messages, surfaceId);
  final out = <String>[];
  for (final message in componentMessages) {
    final components = (message as Map)['updateComponents']['components'];
    _walk(components, dataModel, out);
  }
  return _joinReadable(out);
}
