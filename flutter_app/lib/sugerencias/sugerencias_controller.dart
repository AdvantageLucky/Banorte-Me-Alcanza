// flutter_app/lib/sugerencias/sugerencias_controller.dart
import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../models/models.dart';

/// Estado de la pestaña Sugerencias. Vive en el shell (no en la pantalla)
/// para que la barra de navegación pueda mostrar el conteo de pendientes
/// aunque el usuario nunca haya abierto la pestaña.
class SugerenciasController extends ChangeNotifier {
  SugerenciasController({
    required ApiClient apiClient,
    required String Function() tokenProvider,
  })  : _api = apiClient,
        _token = tokenProvider;

  final ApiClient _api;
  final String Function() _token;

  List<Sugerencia> _todas = const [];
  bool _cargando = false;
  Object? _error;

  List<Sugerencia> get pendientes => _todas.where((s) => s.pendiente).toList();
  List<Sugerencia> get historial => _todas.where((s) => !s.pendiente).toList();
  int get pendientesCount => pendientes.length;
  bool get cargando => _cargando;
  Object? get error => _error;

  bool _primeraCargaHecha = false;
  bool get primeraCargaHecha => _primeraCargaHecha;

  Future<void> cargar() async {
    // Coalescer: el shell y la pantalla pueden pedirlo casi a la vez.
    if (_cargando) return;
    _cargando = true;
    _error = null;
    notifyListeners();
    try {
      _todas = await _api.getSugerencias(_token());
      _primeraCargaHecha = true;
    } catch (err) {
      _error = err;
    } finally {
      _cargando = false;
      notifyListeners();
    }
  }

  Future<Sugerencia> atender(int id) async {
    final actualizada = await _api.atenderSugerencia(_token(), id);
    _reemplazar(actualizada);
    return actualizada;
  }

  Future<Sugerencia> descartar(int id) async {
    final actualizada = await _api.descartarSugerencia(_token(), id);
    _reemplazar(actualizada);
    return actualizada;
  }

  Future<String> generarPropuesta(int id) => _api.getPropuestaSugerencia(_token(), id);

  void _reemplazar(Sugerencia actualizada) {
    _todas = [
      for (final s in _todas) s.id == actualizada.id ? actualizada : s,
    ];
    notifyListeners();
  }
}
