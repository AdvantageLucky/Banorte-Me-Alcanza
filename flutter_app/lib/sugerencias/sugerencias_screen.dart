// flutter_app/lib/sugerencias/sugerencias_screen.dart
//
// Pestaña Atención: el sistema detecta situaciones de riesgo (reglas
// deterministas en el backend) y las presenta como tarjetas A2UI que
// llegan ya armadas — el usuario no teclea nada para recibir UI. Tocar
// "Atender" pasa por un modal HITL (título/descripción deterministas +
// propuesta del LLM bajo demanda) antes de marcarla, igual que en React
// (ver AtencionView.jsx / AtenderSugerenciaModal.jsx).
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:genui/genui.dart';

import '../a2ui/a2ui_host.dart';
import '../api/api_client.dart';
import '../auth/auth_controller.dart';
import '../models/models.dart';
import '../shared/formatters.dart';
import '../shared/widgets.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import 'atender_sugerencia_modal.dart';
import 'extract_sugerencia_copy.dart';
import 'sugerencia_action_router.dart';
import 'sugerencias_controller.dart';

class SugerenciasScreen extends StatefulWidget {
  const SugerenciasScreen({
    super.key,
    required this.controller,
    required this.authController,
  });

  final SugerenciasController controller;
  final AuthController authController;

  @override
  State<SugerenciasScreen> createState() => _SugerenciasScreenState();
}

class _SugerenciasScreenState extends State<SugerenciasScreen> {
  late final A2uiHost _host;
  late final SugerenciaActionRouter _router;
  late final StreamSubscription<Object> _hostErrors;

  /// surfaceId → id de sugerencia, en el orden en que se pintan.
  final List<({String surfaceId, int sugerenciaId})> _tarjetas = [];
  bool _resolviendo = false;
  bool _historialAbierto = false;

  @override
  void initState() {
    super.initState();
    _host = A2uiHost(onAction: _onAction);
    _hostErrors = _host.errors.listen((_) {
      if (mounted) mostrarAviso(context, 'Una tarjeta no se pudo mostrar.');
    });
    _router = SugerenciaActionRouter(
      atender: widget.controller.atender,
      descartar: widget.controller.descartar,
      requestConfirmacion: _mostrarModalAtender,
      onResuelta: _onResuelta,
      onError: (err) => _onError(err, 'No se pudo actualizar la sugerencia.'),
    );
    widget.controller.addListener(_sincronizarTarjetas);
    if (!widget.controller.primeraCargaHecha) {
      widget.controller.cargar();
    } else {
      _sincronizarTarjetas();
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_sincronizarTarjetas);
    _hostErrors.cancel();
    _host.dispose();
    super.dispose();
  }

  /// Alinea las superficies del motor con las pendientes del controller:
  /// borra las que ya no están y crea las nuevas. El backend genera un
  /// surfaceId distinto en cada GET, así que se compara por sugerencia.
  void _sincronizarTarjetas() {
    final pendientes = widget.controller.pendientes;
    final vigentes = {for (final s in pendientes) s.id};

    for (final t in List.of(_tarjetas)) {
      if (!vigentes.contains(t.sugerenciaId)) {
        _host.deleteSurface(t.surfaceId);
        _tarjetas.remove(t);
      }
    }

    final yaPintadas = {for (final t in _tarjetas) t.sugerenciaId};
    for (final s in pendientes) {
      final bloque = s.a2uiJson;
      if (yaPintadas.contains(s.id) || bloque == null) continue;
      final surfaceId = surfaceIdOf(bloque);
      if (surfaceId == null) continue;
      _host.feed(bloque);
      _tarjetas.add((surfaceId: surfaceId, sugerenciaId: s.id));
    }

    // Respetar el orden del backend (created_at DESC).
    final orden = {for (var i = 0; i < pendientes.length; i++) pendientes[i].id: i};
    _tarjetas.sort((a, b) => (orden[a.sugerenciaId] ?? 0).compareTo(orden[b.sugerenciaId] ?? 0));

    if (mounted) setState(() {});
  }

  Sugerencia? _buscarSugerencia(int id) {
    for (final s in widget.controller.pendientes) {
      if (s.id == id) return s;
    }
    return null;
  }

  /// requestConfirmacion del router: modal HITL con título/descripción
  /// deterministas + "Ver propuesta del asistente" bajo demanda. Solo
  /// ejecuta `onConfirm` (la acción real) si el usuario toca "Marcar como
  /// atendida"; si cancela o cierra el modal, no pasa nada.
  Future<void> _mostrarModalAtender(int sugerenciaId, Future<void> Function() onConfirm) async {
    final sugerencia = _buscarSugerencia(sugerenciaId);
    final copy = extraerTituloDescripcion(sugerencia?.a2uiJson);
    if (!mounted) return;
    final confirmado = await showDialog<bool>(
      context: context,
      builder: (_) => AtenderSugerenciaModal(
        titulo: copy.titulo,
        descripcion: copy.descripcion,
        onGenerarPropuesta: () => widget.controller.generarPropuesta(sugerenciaId),
      ),
    );
    if (confirmado == true) {
      await onConfirm();
    }
  }

  Future<void> _onAction(Map<String, dynamic> action) async {
    if (mounted) setState(() => _resolviendo = true);
    try {
      await _router.handle(action);
    } finally {
      if (mounted) setState(() => _resolviendo = false);
    }
  }

  void _onResuelta(Sugerencia s) {
    mostrarAviso(context, s.estado == 'atendida' ? 'Marcada como atendida.' : 'Sugerencia descartada.');
  }

  void _onError(Object err, String fallback) {
    if (err is ApiException && err.statusCode == 401) {
      widget.authController.logout();
      return;
    }
    mostrarAviso(context, describirError(err, fallback: fallback));
  }

  @override
  Widget build(BuildContext context) {
    final controller = widget.controller;
    return Scaffold(
      appBar: BrandAppBar(seccion: 'Atención', onLogout: widget.authController.logout),
      body: ListenableBuilder(
        listenable: controller,
        builder: (context, _) {
          return RefreshIndicator(
            onRefresh: controller.cargar,
            child: ListView(
              padding: const EdgeInsets.only(bottom: Space.xxl),
              children: [
                _Encabezado(pendientes: controller.pendientesCount, cargando: controller.cargando),
                if (_resolviendo) const LinearProgressIndicator(minHeight: 2),
                if (controller.error != null)
                  ErrorRetry(error: controller.error!, onRetry: controller.cargar),
                if (controller.primeraCargaHecha && _tarjetas.isEmpty && controller.error == null)
                  const _TodoEnOrden(),
                for (final t in _tarjetas)
                  _PendienteTile(
                    key: ValueKey('sugerencia-${t.sugerenciaId}'),
                    surface: Surface(surfaceContext: _host.contextFor(t.surfaceId)),
                  ),
                if (controller.historial.isNotEmpty)
                  _Historial(
                    items: controller.historial,
                    abierto: _historialAbierto,
                    onToggle: () => setState(() => _historialAbierto = !_historialAbierto),
                  ),
              ],
            ),
          );
        },
      ),
    );
  }
}

class _Encabezado extends StatelessWidget {
  const _Encabezado({required this.pendientes, required this.cargando});

  final int pendientes;
  final bool cargando;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(Space.m, Space.l, Space.m, Space.s),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Lo que detectamos hoy', style: DisplayText.seccion),
                const SizedBox(height: Space.xs),
                Text(
                  'Revisamos tu saldo, tus pagos y tus metas. No tienes que preguntar nada.',
                  style: texto.bodySmall,
                ),
              ],
            ),
          ),
          const SizedBox(width: Space.m),
          if (cargando)
            const Padding(
              padding: EdgeInsets.only(top: 4),
              child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)),
            )
          // Con 0 pendientes, "Todo en orden" (abajo) ya lo dice: un "0"
          // gigante aquí es ruido, no información — antes además se
          // renderizaba en BankGothic, donde el glifo del cero se ve como
          // un recuadro hueco sin nada adentro.
          else if (pendientes > 0)
            Text('$pendientes', style: DisplayText.saldo.copyWith(fontSize: 36, color: BrandColors.rojo)),
        ],
      ),
    );
  }
}

class _TodoEnOrden extends StatelessWidget {
  const _TodoEnOrden();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Space.m, Space.xl, Space.m, Space.m),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.check_circle_outline, color: BrandColors.exito, size: 28),
          const SizedBox(width: Space.m),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Todo en orden', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(
                  'No hay nada que requiera tu atención hoy. Desliza hacia abajo para volver a revisar.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: BrandColors.gris),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Una sugerencia pendiente: la tarjeta A2UI determinista del backend.
/// "Atender" abre el modal HITL (ver _mostrarModalAtender) con la
/// propuesta del LLM bajo demanda, no la muestra aquí.
class _PendienteTile extends StatelessWidget {
  const _PendienteTile({super.key, required this.surface});

  final Widget surface;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Space.m, Space.s, Space.m, Space.s),
      child: surface,
    );
  }
}

class _Historial extends StatelessWidget {
  const _Historial({required this.items, required this.abierto, required this.onToggle});

  final List<Sugerencia> items;
  final bool abierto;
  final VoidCallback onToggle;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        InkWell(
          onTap: onToggle,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(Space.m, Space.l, Space.m, Space.s),
            child: Row(
              children: [
                Text('Historial', style: DisplayText.seccion.copyWith(color: BrandColors.gris)),
                const SizedBox(width: Space.s),
                Text('${items.length}', style: texto.bodySmall),
                const Spacer(),
                Icon(abierto ? Icons.expand_less : Icons.expand_more, color: BrandColors.gris),
              ],
            ),
          ),
        ),
        AnimatedSize(
          duration: const Duration(milliseconds: 220),
          curve: Curves.easeOut,
          alignment: Alignment.topCenter,
          child: abierto
              ? Column(
                  children: [
                    for (final s in items)
                      HairlineRow(
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(s.titulo, style: texto.bodyMedium),
                                  const SizedBox(height: 2),
                                  Text(
                                    s.resueltaAt != null
                                        ? 'Resuelta el ${formatFecha(s.resueltaAt!.substring(0, 10))}'
                                        : 'Detectada el ${formatFecha(s.createdAt.substring(0, 10))}',
                                    style: texto.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            _EstadoChip(estado: s.estado),
                          ],
                        ),
                      ),
                  ],
                )
              : const SizedBox.shrink(),
        ),
      ],
    );
  }
}

class _EstadoChip extends StatelessWidget {
  const _EstadoChip({required this.estado});

  final String estado;

  @override
  Widget build(BuildContext context) {
    final (color, texto) = switch (estado) {
      'atendida' => (BrandColors.exito, 'Atendida'),
      'descartada' => (BrandColors.gris, 'Descartada'),
      _ => (BrandColors.rojo, 'Pendiente'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: color),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(texto, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
    );
  }
}
