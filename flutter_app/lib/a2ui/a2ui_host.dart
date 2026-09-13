// flutter_app/lib/a2ui/a2ui_host.dart
//
// Plomería de genui para renderizar superficies A2UI que llegan ya
// parseadas desde nuestro backend (no por streaming de texto). Un host
// por pantalla: el chat y Sugerencias usan exactamente el mismo
// mecanismo, así que vive aquí una sola vez.
//
// Las firmas de genui usadas están verificadas contra el código fuente
// del paquete en flutter_app/GENUI_API_NOTES.md.
import 'dart:async';
import 'dart:convert';

import 'package:a2ui_core/a2ui_core.dart' as core;
import 'package:flutter/foundation.dart';
import 'package:genui/genui.dart';

/// Callback con la acción de usuario tal cual la emite el catálogo:
/// `{surfaceId, name, sourceComponentId, timestamp, context}`.
typedef A2uiActionHandler = Future<void> Function(Map<String, dynamic> action);

class A2uiHost {
  A2uiHost({required this._onAction}) {
    controller = SurfaceController(catalogs: [BasicCatalogItems.asCatalog()]);
    _transport = A2uiTransportAdapter(onSend: _handleSend);
    _conversation = Conversation(controller: controller, transport: _transport);
    _eventsSubscription = _conversation.events.listen(_onEvent);
  }

  final A2uiActionHandler _onAction;

  late final SurfaceController controller;
  late final A2uiTransportAdapter _transport;
  late final Conversation _conversation;
  late final StreamSubscription<ConversationEvent> _eventsSubscription;

  final _surfaceAdded = StreamController<String>.broadcast();
  final _errors = StreamController<Object>.broadcast();

  /// Emite el `surfaceId` de cada superficie nueva, en orden de llegada.
  Stream<String> get surfaceAdded => _surfaceAdded.stream;

  /// Errores internos del motor (payload inválido, etc.).
  Stream<Object> get errors => _errors.stream;

  SurfaceContext contextFor(String surfaceId) => controller.contextFor(surfaceId);

  /// Inyecta una lista de envelopes A2UI crudos (`a2ui_messages` del
  /// backend). Cada uno debe ser un `Map` con `version: v0.9` y exactamente
  /// una de `createSurface | updateComponents | updateDataModel |
  /// deleteSurface`.
  void feed(Iterable<dynamic> messages) {
    for (final message in messages) {
      _transport.addMessage(
        core.A2uiMessage.fromJson((message as Map).cast<String, dynamic>()),
      );
    }
  }

  /// Quita una superficie del motor (y libera su estado).
  void deleteSurface(String surfaceId) {
    feed([
      {'version': 'v0.9', 'deleteSurface': {'surfaceId': surfaceId}},
    ]);
  }

  void _onEvent(ConversationEvent event) {
    if (event is ConversationSurfaceAdded) {
      _surfaceAdded.add(event.surfaceId);
    } else if (event is ConversationError) {
      debugPrint('A2uiHost ConversationError: ${event.error}');
      _errors.add(event.error);
    }
  }

  Future<void> _handleSend(ChatMessage message) async {
    // Toda acción de botón llega aquí: Conversation reenvía al transport
    // el ChatMessage que arma SurfaceController.handleUiEvent. Los parts
    // son DataPart con el mimeType de interacción; la extensión
    // `uiInteractionParts` los filtra y expone `.interaction` (JSON).
    final part = message.parts.uiInteractionParts.firstOrNull;
    if (part == null) return;
    final decoded = jsonDecode(part.interaction) as Map<String, dynamic>;
    // SurfaceController.reportError empuja por este mismo canal un
    // payload {"version","error"} sin "action": se ignora.
    final action = decoded['action'] as Map<String, dynamic>?;
    if (action == null) return;
    await _onAction(action);
  }

  void dispose() {
    _eventsSubscription.cancel();
    _conversation.dispose();
    controller.dispose();
    _transport.dispose();
    _surfaceAdded.close();
    _errors.close();
  }
}

/// Lee el `surfaceId` de un bloque A2UI (`a2ui_messages`) sin pasar por
/// el motor: útil para asociar una tarjeta a su recurso antes de que
/// genui la registre.
String? surfaceIdOf(Iterable<dynamic> messages) {
  for (final message in messages) {
    final map = (message as Map).cast<String, dynamic>();
    final create = map['createSurface'] as Map?;
    if (create != null) return create['surfaceId'] as String?;
  }
  return null;
}
