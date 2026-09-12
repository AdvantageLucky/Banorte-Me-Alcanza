// flutter_app/lib/chat/chat_screen.dart
import 'dart:async';
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
  final _scrollController = ScrollController();
  final List<ChatTurn> _turns = [];
  bool _sending = false;
  bool _confirmingAction = false;
  bool _awaitingResponse = false;
  String? _errorMessage;
  int _turnCounter = 0;

  late final SurfaceController _surfaceController;
  late final A2uiTransportAdapter _transport;
  late final Conversation _conversation;
  late final StreamSubscription<ConversationEvent> _eventsSubscription;

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

    _eventsSubscription = _conversation.events.listen((event) {
      if (event is ConversationSurfaceAdded) {
        setState(() {
          _awaitingResponse = false;
          _turns.add(AgentTurn('turn-${_turnCounter++}', event.surfaceId));
        });
        _scrollToBottom();
      } else if (event is ConversationError) {
        // Cubre, entre otros casos, el error interno que
        // SurfaceController.reportError empuja por el mismo stream
        // onSubmit que las acciones de botón (payload
        // {"version": "v0.9", "error": {...}}, sin clave "action"): ese
        // caso hace que A2uiTransportAdapter.sendRequest falle dentro de
        // _handleSend (ver más abajo), y Conversation.sendRequest
        // convierte esa excepción en este evento en vez de dejarla
        // propagar sin control.
        debugPrint('ConversationError: ${event.error}');
        setState(() {
          _awaitingResponse = false;
          _errorMessage = 'Ocurrió un error inesperado. Intenta de nuevo.';
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
    if (_errorMessage != null) {
      setState(() => _errorMessage = null);
    }
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
    // No todo UiInteractionPart representa una acción de usuario: por
    // ejemplo, SurfaceController.reportError empuja por este mismo canal
    // un payload {"version": "v0.9", "error": {...}} sin clave "action"
    // (ver genui-0.10.3/lib/src/engine/surface_controller.dart:296-309).
    // Forzar el cast a Map no-nulable lanzaría un TypeError en ese caso;
    // en vez de eso, simplemente ignoramos interacciones sin acción.
    final action = decoded['action'] as Map<String, dynamic>?;
    if (action == null) {
      return;
    }
    if (mounted) setState(() => _confirmingAction = true);
    try {
      await _actionRouter.handle(action);
    } finally {
      if (mounted) setState(() => _confirmingAction = false);
    }
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
      _awaitingResponse = true;
      _errorMessage = null;
      _turns.add(UserTurn('turn-${_turnCounter++}', texto));
    });
    _messageController.clear();
    _scrollToBottom();
    try {
      final token = widget.authController.token!;
      final messages = await widget.apiClient.sendMessage(token, texto);
      _feedMessagesToConversation(messages);
    } catch (err) {
      if (mounted) setState(() => _awaitingResponse = false);
      _handleError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      if (mounted) {
        setState(() => _sending = false);
      }
    }
  }

  @override
  void dispose() {
    _eventsSubscription.cancel();
    _conversation.dispose();
    _surfaceController.dispose();
    _messageController.dispose();
    _scrollController.dispose();
    _transport.dispose();
    super.dispose();
  }

  // Como en cualquier chat (WhatsApp, Messenger), cada turno nuevo debe
  // dejar visible la última línea sin que el usuario tenga que
  // scrollear manualmente. Se agenda para después del frame porque el
  // ListView todavía no midió el nuevo item cuando se dispara este
  // callback desde setState.
  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) return;
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text(
              'Banorte',
              style: TextStyle(fontFamily: 'BankGothic', fontWeight: FontWeight.w700),
            ),
            const Text(' — ¿Me Alcanza?'),
          ],
        ),
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
                    controller: _scrollController,
                    padding: const EdgeInsets.all(16),
                    itemCount: _turns.length + (_awaitingResponse ? 1 : 0),
                    itemBuilder: (context, index) {
                      final maxBubbleWidth = MediaQuery.of(context).size.width * 0.78;
                      if (index == _turns.length) {
                        // Fila de "el agente está pensando", visible entre
                        // que se manda el mensaje y que llega la primera
                        // superficie A2UI de la respuesta — sin esto el
                        // usuario no tiene ninguna señal de que el mensaje
                        // sí se envió y algo está en proceso.
                        return const Padding(
                          padding: EdgeInsets.symmetric(vertical: 4),
                          child: _TypingIndicator(),
                        );
                      }
                      final turn = _turns[index];
                      if (turn is UserTurn) {
                        return Align(
                          alignment: Alignment.centerRight,
                          child: ConstrainedBox(
                            constraints: BoxConstraints(maxWidth: maxBubbleWidth),
                            child: Container(
                              margin: const EdgeInsets.symmetric(vertical: 4),
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                              decoration: BoxDecoration(
                                color: Theme.of(context).colorScheme.tertiary,
                                borderRadius: const BorderRadius.only(
                                  topLeft: Radius.circular(12),
                                  topRight: Radius.circular(12),
                                  bottomLeft: Radius.circular(12),
                                  bottomRight: Radius.circular(3),
                                ),
                              ),
                              child: Text(
                                turn.text,
                                style: TextStyle(color: Theme.of(context).colorScheme.onTertiary),
                              ),
                            ),
                          ),
                        );
                      }
                      turn as AgentTurn;
                      // Misma convención que WhatsApp/Messenger: los
                      // mensajes entrantes llevan la foto de perfil del
                      // remitente a la izquierda; los salientes (arriba)
                      // no llevan avatar y quedan alineados a la derecha.
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            // Image.asset en vez de CircleAvatar: el
                            // recorte circular de CircleAvatar le cortaba
                            // la colita del globo de comic a la mascota
                            // (ver frontend/src/assets/images/banorberto.png,
                            // el sticker ya trae su propio contorno).
                            const Image(
                              image: AssetImage('assets/icon/icon.png'),
                              width: 32,
                              height: 32,
                            ),
                            const SizedBox(width: 8),
                            Flexible(
                              child: ConstrainedBox(
                                constraints: BoxConstraints(maxWidth: maxBubbleWidth),
                                child: Surface(
                                  surfaceContext: _surfaceController.contextFor(turn.surfaceId),
                                ),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
          if (_confirmingAction) const LinearProgressIndicator(),
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

// Tres puntos con opacidad animada en cascada, misma composición
// avatar+burbuja que un AgentTurn real para que la fila no salte de
// posición cuando la respuesta de verdad la reemplaza.
class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Image(
          image: AssetImage('assets/icon/icon.png'),
          width: 32,
          height: 32,
        ),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(12),
          ),
          child: AnimatedBuilder(
            animation: _controller,
            builder: (context, _) {
              return Row(
                mainAxisSize: MainAxisSize.min,
                children: List.generate(3, (i) {
                  final t = (_controller.value - i * 0.2) % 1.0;
                  final opacity = 0.3 + 0.7 * (1 - (t - 0.5).abs() * 2).clamp(0.0, 1.0);
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 2),
                    child: Opacity(
                      opacity: opacity,
                      child: Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                          shape: BoxShape.circle,
                        ),
                      ),
                    ),
                  );
                }),
              );
            },
          ),
        ),
      ],
    );
  }
}
