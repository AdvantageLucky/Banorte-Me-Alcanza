// flutter_app/lib/chat/speech_service.dart
//
// Wrapper delgado sobre speech_to_text (dictado, STT) y flutter_tts
// (lectura en voz alta, TTS) para accesibilidad del chat. Ambos motores son
// nativos del OS (sin backend, sin claves de API) — mismo enfoque que el
// lado React (Web Speech API, ver useSpeechRecognition.js/
// useSpeechSynthesis.js). `SpeechService` no sabe nada de ChatScreen: solo
// expone dictado y lectura como callbacks simples.
import 'package:flutter_tts/flutter_tts.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

class SpeechService {
  SpeechService() : _speechToText = stt.SpeechToText(), _tts = FlutterTts();

  final stt.SpeechToText _speechToText;
  final FlutterTts _tts;
  bool _sttInitialized = false;
  bool _sttAvailable = false;

  // El dispositivo puede no traer reconocimiento de voz (falta el servicio
  // de Google en Android, permiso denegado, etc.) — se verifica una sola
  // vez, no en cada intento de escuchar.
  Future<bool> get sttAvailable async {
    if (!_sttInitialized) {
      _sttAvailable = await _speechToText.initialize(
        // 'done'/'notListening' cubre tanto el fin normal (silencio
        // detectado) como un stop manual o un error — sin esto la UI puede
        // quedarse mostrando "Escuchando…" si el motor corta sin mandar un
        // resultado final (p.ej. timeout sin haber dicho nada).
        onStatus: (status) {
          if (status == 'done' || status == 'notListening') {
            _onListeningEnded?.call();
          }
        },
        onError: (_) => _onListeningEnded?.call(),
      );
      _sttInitialized = true;
    }
    return _sttAvailable;
  }

  bool get isListening => _speechToText.isListening;

  void Function()? _onListeningEnded;

  /// Empieza a escuchar. `onFinalResult` se dispara una sola vez, cuando el
  /// usuario termina de hablar (silencio detectado por el propio motor),
  /// con el texto ya transcrito — para que el caller pueda autoenviarlo.
  /// `onPartialResult` se dispara en cada actualización intermedia (para un
  /// indicador de "Escuchando... {texto}"). `onListeningEnded` se dispara
  /// siempre que el motor deja de escuchar, con o sin resultado, para que
  /// la UI pueda limpiar el estado aunque no se haya dicho nada.
  Future<void> startListening({
    required String localeId,
    required void Function(String text) onFinalResult,
    void Function(String text)? onPartialResult,
    void Function()? onListeningEnded,
  }) async {
    if (!await sttAvailable || isListening) {
      return;
    }
    _onListeningEnded = onListeningEnded;
    await _speechToText.listen(
      listenOptions: stt.SpeechListenOptions(localeId: localeId),
      onResult: (result) {
        if (result.finalResult) {
          onFinalResult(result.recognizedWords.trim());
        } else {
          onPartialResult?.call(result.recognizedWords);
        }
      },
    );
  }

  Future<void> stopListening() => _speechToText.stop();

  Future<void> speak(String text, {required String lang}) async {
    if (text.trim().isEmpty) return;
    await _tts.stop();
    await _tts.setLanguage(lang);
    await _tts.speak(text);
  }

  Future<void> stopSpeaking() => _tts.stop();

  /// Se dispara cuando el TTS termina de leer por su cuenta (no por un stop
  /// manual), para que la UI pueda limpiar el estado de "hablando".
  set onSpeakComplete(void Function() callback) {
    _tts.setCompletionHandler(callback);
    _tts.setCancelHandler(callback);
    _tts.setErrorHandler((_) => callback());
  }

  void dispose() {
    _onListeningEnded = null;
    _speechToText.cancel();
    _tts.stop();
  }
}
