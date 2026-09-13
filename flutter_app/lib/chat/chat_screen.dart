// flutter_app/lib/chat/chat_screen.dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:genui/genui.dart';

import '../a2ui/a2ui_host.dart';
import '../api/api_client.dart';
import '../auth/auth_controller.dart';
import '../models/models.dart';
import '../shared/widgets.dart';
import '../theme/tokens.dart';
import 'action_router.dart';
import 'conversaciones_drawer.dart';
import 'extract_surface_text.dart';
import 'speech_service.dart';

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
// Cada turno es una entrada nueva — nunca se sobrescribe uno anterior.
sealed class ChatTurn {
  const ChatTurn(this.id);
  final String id;
}

class UserTurn extends ChatTurn {
  UserTurn(super.id, this.text);
  final String text;
}

class AgentTurn extends ChatTurn {
  AgentTurn(super.id, this.surfaceId, this.rawMessages);
  final String surfaceId;

  // El a2ui crudo de este turno, guardado además del surfaceId para que el
  // botón de "escuchar en voz alta" (extractSurfaceText) tenga de dónde
  // sacar texto sin reconstruirlo desde el SurfaceController.
  final List<dynamic> rawMessages;
}

// Un turno "model" del historial cuyo texto viejo ya no parsea como A2UI
// (a2ui_json vino null desde el backend — ver Orchestrator.reparsear_mensaje_
// modelo). Nunca ocurre en vivo, solo al reabrir una conversación pasada.
class AgentTextTurn extends ChatTurn {
  AgentTextTurn(super.id, this.text);
  final String text;
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

  /// Hilo de conversación actual. El backend lo devuelve en el primer
  /// turno; reenviarlo es lo que le da memoria al asistente.
  int? _conversacionId;

  // Historial de hilos (drawer) — se recarga cada vez que se abre, así que
  // una conversación recién creada por el primer mensaje aparece sin tener
  // que refrescar nada a mano.
  late Future<List<Conversacion>> _conversacionesFuture;

  // El a2ui crudo del envío en curso, a la espera de que el host confirme
  // el surfaceId real para adjuntarlo al AgentTurn correspondiente.
  List<dynamic> _pendingRawMessages = const [];

  // Accesibilidad: dictado por voz (STT) y lectura en voz alta (TTS). Ver
  // speech_service.dart — ambos usan los motores nativos del OS.
  final _speechService = SpeechService();
  bool _sttSupported = false;
  bool _listening = false;
  String _interimTranscript = '';
  String? _speakingTurnId;

  late final A2uiHost _host;
  late final StreamSubscription<String> _surfaceSub;
  late final StreamSubscription<Object> _errorSub;

  late final ActionRouter _actionRouter = ActionRouter(
    confirmAction: (proposalId, context) => widget.apiClient.confirmAction(
      widget.authController.token!,
      proposalId,
      context,
    ),
    onMessages: _feedMessages,
    onError: (err) => _handleError(err, 'No se pudo confirmar la acción, intenta de nuevo.'),
  );

  @override
  void initState() {
    super.initState();
    _conversacionesFuture = widget.apiClient.getConversaciones(widget.authController.token!);
    _host = A2uiHost(onAction: _onAction);
    _surfaceSub = _host.surfaceAdded.listen((surfaceId) {
      setState(() {
        _awaitingResponse = false;
        _turns.add(AgentTurn('turn-${_turnCounter++}', surfaceId, _pendingRawMessages));
      });
      _scrollToBottom();
    });
    _errorSub = _host.errors.listen((_) {
      setState(() {
        _awaitingResponse = false;
        _errorMessage = 'Ocurrió un error inesperado. Intenta de nuevo.';
      });
    });
    // Chequeo único: si el dispositivo no trae reconocimiento de voz, el
    // botón de mic ni se muestra — igual que en React con `supported`.
    _speechService.sttAvailable.then((available) {
      if (mounted) setState(() => _sttSupported = available);
    });
  }

  @override
  void dispose() {
    _surfaceSub.cancel();
    _errorSub.cancel();
    _host.dispose();
    _messageController.dispose();
    _scrollController.dispose();
    _speechService.dispose();
    super.dispose();
  }

  void _feedMessages(List<dynamic> messages) {
    if (_errorMessage != null) setState(() => _errorMessage = null);
    // Antes de alimentar el host: surfaceAdded puede disparar de forma
    // síncrona y para entonces ya debe estar disponible.
    _pendingRawMessages = messages;
    _host.feed(messages);
  }

  Future<void> _onAction(Map<String, dynamic> action) async {
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
    setState(() => _errorMessage = describirError(err, fallback: fallback));
  }

  Future<void> _handleSubmit() async {
    final texto = _messageController.text.trim();
    if (texto.isEmpty || _sending) return;
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
      final turno = await widget.apiClient.sendMessage(token, texto, conversacionId: _conversacionId);
      _conversacionId = turno.conversacionId ?? _conversacionId;
      _feedMessages(turno.a2uiMessages);
    } catch (err) {
      if (mounted) setState(() => _awaitingResponse = false);
      _handleError(err, 'No se pudo enviar el mensaje, intenta de nuevo.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _nuevoHilo() async {
    await _speechService.stopSpeaking();
    if (!mounted) return;
    setState(() {
      _conversacionId = null;
      _turns.clear();
      _errorMessage = null;
      _speakingTurnId = null;
    });
  }

  void _reloadConversaciones() {
    setState(() {
      _conversacionesFuture = widget.apiClient.getConversaciones(widget.authController.token!);
    });
  }

  /// Reabre un hilo pasado: pide su historial completo y reconstruye cada
  /// turno. Los turnos "model" con a2ui_json se re-alimentan al mismo
  /// A2uiHost que usan los mensajes en vivo (mismo camino que _feedMessages,
  /// así que el listener de `surfaceAdded` en initState agrega el AgentTurn
  /// solo) — nunca se arma la tarjeta a mano aquí.
  Future<void> _cargarConversacion(int id) async {
    await _speechService.stopSpeaking();
    if (!mounted) return;
    setState(() {
      _turns.clear();
      _conversacionId = id;
      _errorMessage = null;
      _speakingTurnId = null;
    });
    try {
      final token = widget.authController.token!;
      final mensajes = await widget.apiClient.getMensajesConversacion(token, id);
      for (final m in mensajes) {
        if (!mounted) return;
        if (m.rol == 'user') {
          setState(() => _turns.add(UserTurn('turn-${_turnCounter++}', m.contenido)));
          continue;
        }
        if (m.a2uiJson != null) {
          _feedMessages(m.a2uiJson!);
          continue;
        }
        setState(() => _turns.add(AgentTextTurn('turn-${_turnCounter++}', m.contenido)));
      }
      _scrollToBottom();
    } catch (err) {
      _handleError(err, 'No se pudo cargar esta conversación, intenta de nuevo.');
    }
  }

  // Dictado por voz (STT): al detectar el final del habla se manda el
  // mensaje directo, igual que si el usuario lo hubiera escrito y enviado.
  Future<void> _handleToggleMic() async {
    if (_listening) {
      await _speechService.stopListening();
      return;
    }
    setState(() {
      _listening = true;
      _interimTranscript = '';
    });
    await _speechService.startListening(
      localeId: 'es_MX',
      onFinalResult: (texto) {
        if (!mounted) return;
        setState(() {
          _listening = false;
          _interimTranscript = '';
        });
        if (texto.isNotEmpty) {
          _messageController.text = texto;
          _handleSubmit();
        }
      },
      onPartialResult: (texto) {
        if (mounted) setState(() => _interimTranscript = texto);
      },
      onListeningEnded: () {
        if (mounted) setState(() => _listening = false);
      },
    );
  }

  // Lectura en voz alta (TTS) de la respuesta de un turno — tanto una
  // tarjeta A2UI en vivo/reabierta (AgentTurn) como un turno de historial
  // viejo que ya no parsea como A2UI (AgentTextTurn, texto plano).
  Future<void> _handleSpeakId(String id, String texto) async {
    if (_speakingTurnId == id) {
      await _speechService.stopSpeaking();
      if (mounted) setState(() => _speakingTurnId = null);
      return;
    }
    if (texto.isEmpty) return;
    _speechService.onSpeakComplete = () {
      if (mounted) setState(() => _speakingTurnId = null);
    };
    setState(() => _speakingTurnId = id);
    await _speechService.speak(texto, lang: 'es-MX');
  }

  Future<void> _handleSpeakTurn(AgentTurn turn) =>
      _handleSpeakId(turn.id, extractSurfaceText(turn.rawMessages));

  // Cada turno nuevo debe dejar visible la última línea. Se agenda para
  // después del frame porque el ListView todavía no midió el item nuevo.
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
      drawer: ConversacionesDrawer(
        future: _conversacionesFuture,
        activeId: _conversacionId,
        onSelect: _cargarConversacion,
        onNueva: _nuevoHilo,
      ),
      onDrawerChanged: (opened) {
        if (opened) _reloadConversaciones();
      },
      appBar: BrandAppBar(
        seccion: 'Asistente',
        onLogout: widget.authController.logout,
        actions: [
          if (_turns.isNotEmpty)
            IconButton(
              tooltip: 'Nueva conversación',
              icon: const Icon(Icons.add_comment_outlined),
              onPressed: _nuevoHilo,
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _turns.isEmpty
                ? _Sugeridas(onPick: (p) {
                    _messageController.text = p;
                    _handleSubmit();
                  })
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(Space.m),
                    itemCount: _turns.length + (_awaitingResponse ? 1 : 0),
                    itemBuilder: (context, index) {
                      final maxBubbleWidth = MediaQuery.of(context).size.width * 0.78;
                      if (index == _turns.length) {
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
                              padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 10),
                              decoration: const BoxDecoration(
                                color: BrandColors.burbujaUsuario,
                                borderRadius: BorderRadius.only(
                                  topLeft: Radius.circular(12),
                                  topRight: Radius.circular(12),
                                  bottomLeft: Radius.circular(12),
                                  bottomRight: Radius.circular(3),
                                ),
                              ),
                              child: Text(turn.text, style: const TextStyle(color: Colors.white)),
                            ),
                          ),
                        );
                      }
                      if (turn is AgentTextTurn) {
                        final hablando = _speakingTurnId == turn.id;
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _AgentAvatarColumn(
                                hablando: hablando,
                                onSpeak: () => _handleSpeakId(turn.id, turn.text),
                              ),
                              const SizedBox(width: Space.s),
                              Flexible(
                                child: ConstrainedBox(
                                  constraints: BoxConstraints(maxWidth: maxBubbleWidth),
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 10),
                                    decoration: BoxDecoration(
                                      color: Theme.of(context).colorScheme.surfaceContainerHighest,
                                      borderRadius: BorderRadius.circular(12),
                                    ),
                                    child: Text(turn.text),
                                  ),
                                ),
                              ),
                            ],
                          ),
                        );
                      }
                      turn as AgentTurn;
                      final hablando = _speakingTurnId == turn.id;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _AgentAvatarColumn(
                              hablando: hablando,
                              onSpeak: () => _handleSpeakTurn(turn),
                            ),
                            const SizedBox(width: Space.s),
                            Flexible(
                              child: ConstrainedBox(
                                constraints: BoxConstraints(maxWidth: maxBubbleWidth),
                                child: Surface(surfaceContext: _host.contextFor(turn.surfaceId)),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
          ),
          if (_confirmingAction) const LinearProgressIndicator(minHeight: 2),
          if (_errorMessage != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: Space.xs),
              child: Text(_errorMessage!, style: const TextStyle(color: BrandColors.error)),
            ),
          if (_listening)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: Space.xs),
              child: Row(
                children: [
                  const Icon(Icons.graphic_eq, size: 18, color: BrandColors.rojo),
                  const SizedBox(width: Space.s),
                  Expanded(
                    child: Text(
                      _interimTranscript.isEmpty ? 'Escuchando…' : _interimTranscript,
                      style: const TextStyle(color: BrandColors.gris),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(Space.s),
              child: Row(
                children: [
                  // Accesibilidad: dictado por voz — se oculta si el
                  // dispositivo no lo soporta (ver initState).
                  if (_sttSupported)
                    IconButton(
                      icon: Icon(_listening ? Icons.stop_circle : Icons.mic_none),
                      color: _listening ? BrandColors.rojo : BrandColors.gris,
                      tooltip: _listening ? 'Detener dictado' : 'Dictar por voz',
                      onPressed: _sending ? null : _handleToggleMic,
                    ),
                  Expanded(
                    child: TextField(
                      controller: _messageController,
                      enabled: !_sending,
                      textInputAction: TextInputAction.send,
                      decoration: const InputDecoration(hintText: 'Pregunta si te alcanza…'),
                      onSubmitted: (_) => _handleSubmit(),
                    ),
                  ),
                  const SizedBox(width: Space.xs),
                  IconButton.filled(
                    tooltip: 'Enviar',
                    onPressed: _sending ? null : _handleSubmit,
                    style: IconButton.styleFrom(
                      backgroundColor: BrandColors.rojo,
                      foregroundColor: Colors.white,
                      minimumSize: const Size(48, 48),
                    ),
                    icon: const Icon(Icons.arrow_upward),
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

/// Columna a la izquierda de cada respuesta del agente: mascota ("Banorberto"),
/// su nombre debajo (estilo WhatsApp) y el botón de leer en voz alta debajo de
/// eso. Antes el botón vivía a la DERECHA de la tarjeta, en la misma fila,
/// robándole ancho a la UI generativa; aquí queda apilado con el avatar en
/// vez de competir por espacio horizontal con la tarjeta.
class _AgentAvatarColumn extends StatelessWidget {
  const _AgentAvatarColumn({required this.hablando, required this.onSpeak});

  final bool hablando;
  final VoidCallback onSpeak;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Image.asset y no CircleAvatar: el recorte circular le cortaba la
        // colita a la mascota.
        const Image(image: AssetImage('assets/icon/icon.png'), width: 32, height: 32),
        const SizedBox(height: 2),
        const Text(
          'Banorberto',
          style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: BrandColors.gris),
        ),
        const SizedBox(height: 2),
        // Accesibilidad: lectura en voz alta de esta respuesta.
        SizedBox(
          width: 28,
          height: 28,
          child: IconButton(
            padding: EdgeInsets.zero,
            iconSize: 16,
            color: hablando ? BrandColors.rojo : BrandColors.gris,
            icon: Icon(hablando ? Icons.stop_circle_outlined : Icons.volume_up_outlined),
            tooltip: hablando ? 'Detener lectura' : 'Escuchar en voz alta',
            onPressed: onSpeak,
          ),
        ),
      ],
    );
  }
}

/// Estado vacío del chat: tres preguntas reales que disparan los flujos
/// de la demo. Tocar una la escribe y la manda.
class _Sugeridas extends StatelessWidget {
  const _Sugeridas({required this.onPick});

  final void Function(String) onPick;

  static const _preguntas = [
    '¿Me alcanza para el concierto del 13 de octubre?',
    'Deposítale 500 a mi hermano Pepe',
    '¿En qué gasté este mes?',
  ];

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return ListView(
      padding: const EdgeInsets.fromLTRB(Space.m, Space.xl, Space.m, Space.m),
      children: [
        Text('Pregunta y te armo la pantalla', style: texto.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: Space.xs),
        Text(
          'No respondo con texto: te muestro el veredicto, cómo se calculó y el botón para actuar.',
          style: texto.bodyMedium?.copyWith(color: BrandColors.gris),
        ),
        const SizedBox(height: Space.l),
        for (final p in _preguntas)
          Padding(
            padding: const EdgeInsets.only(bottom: Space.s),
            child: OutlinedButton(
              onPressed: () => onPick(p),
              style: OutlinedButton.styleFrom(
                alignment: Alignment.centerLeft,
                padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 14),
              ),
              child: Text(p, style: const TextStyle(fontWeight: FontWeight.w500)),
            ),
          ),
      ],
    );
  }
}

// Tres puntos con opacidad animada en cascada, con la misma composición
// avatar+burbuja que un AgentTurn para que la fila no salte de posición.
class _TypingIndicator extends StatefulWidget {
  const _TypingIndicator();

  @override
  State<_TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<_TypingIndicator> with SingleTickerProviderStateMixin {
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
        const Image(image: AssetImage('assets/icon/icon.png'), width: 32, height: 32),
        const SizedBox(width: Space.s),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 14),
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
                        decoration: const BoxDecoration(color: BrandColors.gris, shape: BoxShape.circle),
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
