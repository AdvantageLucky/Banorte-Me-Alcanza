// flutter_app/lib/yo/yo_controller.dart
import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../models/models.dart';

/// Estado de la pestaña Yo: todos los recursos de la cuenta y las
/// operaciones CRUD sobre ellos. Cada recurso se carga por separado para
/// que un fallo en uno no tumbe la pantalla entera.
class YoController extends ChangeNotifier {
  YoController({
    required ApiClient apiClient,
    required String Function() tokenProvider,
    required this._onUnauthorized,
  })  : _api = apiClient,
        _token = tokenProvider;

  final ApiClient _api;
  final String Function() _token;
  final VoidCallback _onUnauthorized;

  Cuenta? cuenta;
  ScoreSalud? score;
  List<Movimiento> movimientos = const [];
  List<Recurrente> ingresos = const [];
  List<Recurrente> gastosFijos = const [];
  List<Meta> metas = const [];
  List<Apartado> apartados = const [];
  List<Contacto> contactos = const [];

  bool cargando = false;
  Object? errorGeneral;

  bool _primeraCargaHecha = false;
  bool get primeraCargaHecha => _primeraCargaHecha;

  Future<void> cargarTodo() async {
    if (cargando) return;
    cargando = true;
    errorGeneral = null;
    notifyListeners();
    final t = _token();
    try {
      final resultados = await Future.wait<Object?>([
        _seguro(() => _api.getCuenta(t)),
        _seguro(() => _api.getScoreSalud(t)),
        _seguro(() => _api.getMovimientos(t)),
        _seguro(() => _api.getIngresos(t)),
        _seguro(() => _api.getGastosFijos(t)),
        _seguro(() => _api.getMetas(t)),
        _seguro(() => _api.getApartados(t)),
        _seguro(() => _api.getContactos(t)),
      ]);
      cuenta = resultados[0] as Cuenta? ?? cuenta;
      score = resultados[1] as ScoreSalud? ?? score;
      movimientos = resultados[2] as List<Movimiento>? ?? movimientos;
      ingresos = resultados[3] as List<Recurrente>? ?? ingresos;
      gastosFijos = resultados[4] as List<Recurrente>? ?? gastosFijos;
      metas = resultados[5] as List<Meta>? ?? metas;
      apartados = resultados[6] as List<Apartado>? ?? apartados;
      contactos = resultados[7] as List<Contacto>? ?? contactos;
      // Si ni la cuenta llegó, no hay nada útil que pintar.
      if (cuenta == null) errorGeneral = _ultimoError ?? StateError('sin datos');
      _primeraCargaHecha = true;
    } finally {
      cargando = false;
      notifyListeners();
    }
  }

  Object? _ultimoError;

  /// Ejecuta una carga; devuelve null si falla (y recuerda el error). Un
  /// 401 cierra la sesión de inmediato.
  Future<T?> _seguro<T>(Future<T> Function() fn) async {
    try {
      return await fn();
    } on ApiException catch (err) {
      if (err.statusCode == 401) _onUnauthorized();
      _ultimoError = err;
      return null;
    } catch (err) {
      _ultimoError = err;
      return null;
    }
  }

  /// Envuelve una mutación: la ejecuta, recarga lo afectado y propaga el
  /// error al llamador (la UI decide cómo mostrarlo). El 401 se maneja aquí.
  Future<void> _mutar(Future<void> Function(String token) fn, {bool tocaSaldo = false}) async {
    try {
      await fn(_token());
      if (tocaSaldo) {
        cuenta = await _seguro(() => _api.getCuenta(_token())) ?? cuenta;
        movimientos = await _seguro(() => _api.getMovimientos(_token())) ?? movimientos;
        score = await _seguro(() => _api.getScoreSalud(_token())) ?? score;
      }
      notifyListeners();
    } on ApiException catch (err) {
      if (err.statusCode == 401) _onUnauthorized();
      rethrow;
    }
  }

  // --------------------------------------------------------- pagos fijos

  Future<void> crearGastoFijo({
    required String concepto,
    required double monto,
    required String frecuencia,
    required String proximaFecha,
  }) =>
      _mutar((t) async {
        final creado = await _api.createGastoFijo(t,
            concepto: concepto, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha);
        gastosFijos = [...gastosFijos, creado];
        score = await _seguro(() => _api.getScoreSalud(t)) ?? score;
      });

  Future<void> actualizarGastoFijo(
    int id, {
    required String concepto,
    required double monto,
    required String frecuencia,
    required String proximaFecha,
  }) =>
      _mutar((t) async {
        final actualizado = await _api.updateGastoFijo(t, id,
            concepto: concepto, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha);
        gastosFijos = [for (final g in gastosFijos) g.id == id ? actualizado : g];
      });

  Future<void> eliminarGastoFijo(int id) => _mutar((t) async {
        await _api.deleteGastoFijo(t, id);
        gastosFijos = gastosFijos.where((g) => g.id != id).toList();
      });

  // ------------------------------------------------------------ ingresos

  Future<void> crearIngreso({
    required String descripcion,
    required double monto,
    required String frecuencia,
    required String proximaFecha,
  }) =>
      _mutar((t) async {
        final creado = await _api.createIngreso(t,
            descripcion: descripcion, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha);
        ingresos = [...ingresos, creado];
        score = await _seguro(() => _api.getScoreSalud(t)) ?? score;
      });

  Future<void> actualizarIngreso(
    int id, {
    required String descripcion,
    required double monto,
    required String frecuencia,
    required String proximaFecha,
  }) =>
      _mutar((t) async {
        final actualizado = await _api.updateIngreso(t, id,
            descripcion: descripcion, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha);
        ingresos = [for (final i in ingresos) i.id == id ? actualizado : i];
      });

  Future<void> eliminarIngreso(int id) => _mutar((t) async {
        await _api.deleteIngreso(t, id);
        ingresos = ingresos.where((i) => i.id != id).toList();
      });

  // --------------------------------------------------------------- metas

  Future<void> crearMeta({
    required String descripcion,
    required double montoObjetivo,
    required String fechaObjetivo,
  }) =>
      _mutar((t) async {
        final creada = await _api.createMeta(t,
            descripcion: descripcion, montoObjetivo: montoObjetivo, fechaObjetivo: fechaObjetivo);
        metas = [...metas, creada];
      });

  Future<void> actualizarMeta(
    int id, {
    required String descripcion,
    required double montoObjetivo,
    required String fechaObjetivo,
  }) =>
      _mutar((t) async {
        final actualizada = await _api.updateMeta(t, id,
            descripcion: descripcion, montoObjetivo: montoObjetivo, fechaObjetivo: fechaObjetivo);
        metas = [for (final m in metas) m.id == id ? actualizada : m];
      });

  /// Falla con el mensaje del backend si la meta tiene apartados activos.
  Future<void> eliminarMeta(int id) => _mutar((t) async {
        await _api.deleteMeta(t, id);
        metas = metas.where((m) => m.id != id).toList();
      });

  // ----------------------------------------------------------- apartados

  List<Apartado> apartadosDe(Meta meta) =>
      apartados.where((a) => a.metaId == meta.id).toList();

  Apartado? apartadoActivoDe(Meta meta) =>
      apartadosDe(meta).where((a) => a.activo).firstOrNull;

  Future<void> crearApartado({
    required int metaId,
    required double montoPorPeriodo,
    required String periodicidad,
  }) =>
      _mutar(
        (t) async {
          final creado = await _api.createApartado(t,
              metaId: metaId, montoPorPeriodo: montoPorPeriodo, periodicidad: periodicidad);
          apartados = [...apartados, creado];
          // El primer periodo se descuenta ya: la meta cambia de monto ahorrado.
          metas = await _seguro(() => _api.getMetas(t)) ?? metas;
        },
        tocaSaldo: true,
      );

  Future<void> cancelarApartado(int id) => _mutar((t) async {
        final cancelado = await _api.cancelarApartado(t, id);
        apartados = [for (final a in apartados) a.id == id ? cancelado : a];
      });

  // ----------------------------------------------------------- contactos

  Future<void> crearContacto({
    required String nombre,
    required String alias,
    required String cuentaDestino,
    required String relacion,
  }) =>
      _mutar((t) async {
        final creado = await _api.createContacto(t,
            nombre: nombre, alias: alias, cuentaDestino: cuentaDestino, relacion: relacion);
        contactos = [...contactos, creado];
      });

  Future<void> actualizarContacto(
    int id, {
    required String nombre,
    required String alias,
    required String cuentaDestino,
    required String relacion,
  }) =>
      _mutar((t) async {
        final actualizado = await _api.updateContacto(t, id,
            nombre: nombre, alias: alias, cuentaDestino: cuentaDestino, relacion: relacion);
        contactos = [for (final c in contactos) c.id == id ? actualizado : c];
      });

  Future<void> eliminarContacto(int id) => _mutar((t) async {
        await _api.deleteContacto(t, id);
        contactos = contactos.where((c) => c.id != id).toList();
      });
}
