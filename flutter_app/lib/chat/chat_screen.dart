// flutter_app/lib/chat/chat_screen.dart
import 'dart:convert';

import 'package:a2ui_core/a2ui_core.dart' as core;
import 'package:flutter/material.dart';
import 'package:genui/genui.dart';

import '../api/api_client.dart';
import '../auth/auth_controller.dart';
import 'action_router.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({
    super.key,
    required this.apiClient,
    required this.authController,
  });

  final ApiClient apiClient;
  final AuthController authController;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

// Un turno de la transcripción: o bien un mensaje del usuario (texto
// plano), o bien la superficie A2UI que armó el agente para ese turno.
// Mismo patrón de "cada turno es una entrada nueva" que ya aplicamos
// en React — nunca se sobrescribe un turno anterior.
sealed class ChatTurn {
  const ChatTurn(this.id);
  final String id;
}

class UserTurn extends ChatTurn {
  UserTurn(super.id, this.text);
  final String text;
}

class AgentTurn extends ChatTurn {
  AgentTurn(super.id, this.surfaceId);
  final String surfaceId;
}

class _ChatScreenState extends State<ChatScreen> {
  final _messageController = TextEditingController();
  final List<ChatTurn> _turns = [];
  bool _sending = false;
  String? _errorMessage;
  int _turnCounter = 0;

  late final SurfaceController _surfaceController;
  late final A2uiTransportAdapter _transport;
  late final Conversation _conversation;

  @override
  void initState() {
    super.initState();

    _surfaceController = SurfaceController(
      catalogs: [BasicCatalogItems.asCatalog()],
    );

    _transport = A2uiTransportAdapter(onSend: _handleSend);

    _conversation = Conversation(
      controller: _surfaceController,
      transport: _transport,
    );

    _conversation.events.listen((event) {
      if (event is ConversationSurfaceAdded) {
        setState(() {
          _turns.add(AgentTurn('turn-${_turnCounter++}', event.surfaceId));
        });
      }
    });
  }

  late final ActionRouter _actionRouter = ActionRouter(
    confirmAction: (proposalId) =>
        widget.apiClient.confirmAction(widget.authController.token!, proposalId),
    onMessages: _feedMessagesToConversation,
    onError: (err) => _handleError(err, 'No se pudo confirmar la acción, intenta de nuevo.'),
  );

  void _feedMessagesToConversation(List<dynamic> messages) {
    for (final message in messages) {
      _transport.addMessage(core.A2uiMessage.fromJson(message as Map<String, dynamic>));
    }
  }

  Future<void> _handleSend(ChatMessage message) async {
    // Cualquier acción de botón (incluyendo confirmar_accion) llega aquí
    // automáticamente: Conversation suscribe internamente
    // controller.onSubmit.listen(sendRequest), y sendRequest reenvía al
    // onSend del transporte el ChatMessage que armó
    // SurfaceController.handleUiEvent (ver GENUI_API_NOTES.md). Los
    // mensajes de texto del usuario NO pasan por aquí — ver
    // _handleSubmit abajo, que llama a la API propia directamente sin
    // pasar por _conversation.sendRequest.
    //
    // Nota: `message.parts` es `List<StandardPart>` — los parts reales
    // que llegan aquí son `DataPart` con
    // mimeType == UiPartConstants.interactionMimeType, no instancias de
    // `UiInteractionPart` (esa clase es solo una "vista" sobre un
    // DataPart, ver genui-0.10.3/lib/src/model/parts/ui.dart). Por eso
    // no se puede usar `whereType<UiInteractionPart>()`; hay que usar la
    // extensión `uiInteractionParts` (sobre Iterable<StandardPart>), que
    // filtra por mimeType y construye la vista vía
    // UiInteractionPart.fromDataPart. El campo con el JSON crudo se
    // llama `.interaction` (verificado leyendo
    // genui-0.10.3/lib/src/model/parts/ui.dart línea 130), no `.data`.
    final interactionPart = message.parts.uiInteractionParts.firstOrNull;
    if (interactionPart == null) {
      return;
    }
    final decoded = jsonDecode(interactionPart.interaction) as Map<String, dynamic>;
    final action = decoded['action'] as Map<String, dynamic>;
    await _actionRouter.handle(action);
  }

  void _handleError(Object err, String fallback) {
    if (err is ApiException && err.statusCode == 401) {
      widget.authController.logout();
      return;
    }
    setState(() {
      _errorMessage = err is ApiException ? (err.detail ?? fallback) : fallback;
    });
  }

  Future<void> _handleSubmit() async {
    final texto = _messageController.text.trim();
    if (texto.isEmpty || _sending) {
      return;
    }
    setState(() {
      _sending = true;
      _errorMessage = null;
      _turns.add(UserTurn('turn-${_turnCounter++}', texto));
    });
    _messageController.clear();
    try {
      final token = widget.authController.token!;
      final messages = await widget.apiClient.sendMessage(token, texto);
      _feedMessagesToConversation(messages);
    } catch (err) {
      _handleError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      if (mounted) {
        setState(() => _sending = false);
      }
    }
  }

  @override
  void dispose() {
    _messageController.dispose();
    _transport.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('me-alcanza'),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: widget.authController.logout,
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _turns.isEmpty
                ? const Center(child: Text('Escribe tu primer mensaje para empezar.'))
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _turns.length,
                    itemBuilder: (context, index) {
                      final turn = _turns[index];
                      if (turn is UserTurn) {
                        return Align(
                          alignment: Alignment.centerRight,
                          child: Container(
                            margin: const EdgeInsets.symmetric(vertical: 4),
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                            decoration: BoxDecoration(
                              color: Theme.of(context).colorScheme.primary,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              turn.text,
                              style: TextStyle(color: Theme.of(context).colorScheme.onPrimary),
                            ),
                          ),
                        );
                      }
                      turn as AgentTurn;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Surface(
                          surfaceContext: _surfaceController.contextFor(turn.surfaceId),
                        ),
                      );
                    },
                  ),
          ),
          if (_errorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
            ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _messageController,
                      enabled: !_sending,
                      decoration: const InputDecoration(hintText: 'Escribe tu mensaje...'),
                      onSubmitted: (_) => _handleSubmit(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  ElevatedButton(
                    onPressed: _sending ? null : _handleSubmit,
                    child: Text(_sending ? 'Enviando...' : 'Enviar'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
