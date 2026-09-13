// flutter_app/lib/yo/sheets/apartado_sheet.dart
//
// Crear un apartado hacia una meta. Muestra en vivo cuánto se llegaría a
// juntar con el monto y la periodicidad elegidos antes de la fecha de la
// meta — el mismo cálculo que hace el simulador del backend, para que el
// usuario ajuste sin adivinar.
import 'package:flutter/material.dart';

import '../../models/models.dart';
import '../../shared/formatters.dart';
import '../../theme/app_theme.dart';
import '../../theme/tokens.dart';
import '../validators.dart';
import 'form_sheet.dart';

typedef CrearApartadoFn = Future<void> Function({
  required double montoPorPeriodo,
  required String periodicidad,
});

Future<bool?> mostrarApartadoSheet(
  BuildContext context, {
  required Meta meta,
  required double saldoActual,
  required CrearApartadoFn onCrear,
}) {
  return mostrarFormSheet<bool>(
    context,
    child: _ApartadoSheet(meta: meta, saldoActual: saldoActual, onCrear: onCrear),
  );
}

/// Periodos completos entre hoy y la fecha objetivo, mínimo 1.
int periodosHasta(String fechaObjetivoIso, String periodicidad, {DateTime? hoy}) {
  final dias = diasHasta(fechaObjetivoIso, hoy: hoy);
  final tamano = switch (periodicidad) {
    'semanal' => 7,
    'quincenal' => 15,
    'mensual' => 30,
    _ => 365,
  };
  final periodos = dias ~/ tamano;
  return periodos < 1 ? 1 : periodos;
}

class _ApartadoSheet extends StatefulWidget {
  const _ApartadoSheet({required this.meta, required this.saldoActual, required this.onCrear});

  final Meta meta;
  final double saldoActual;
  final CrearApartadoFn onCrear;

  @override
  State<_ApartadoSheet> createState() => _ApartadoSheetState();
}

class _ApartadoSheetState extends State<_ApartadoSheet> {
  late final _monto = TextEditingController(text: _sugerido());
  String _periodicidad = 'semanal';

  /// Punto de partida: lo que falta, repartido en semanas hasta la fecha.
  String _sugerido() {
    final falta = widget.meta.montoObjetivo - widget.meta.montoAhorrado;
    final periodos = periodosHasta(widget.meta.fechaObjetivo, 'semanal');
    final porPeriodo = falta / periodos;
    return porPeriodo <= 0 ? '' : porPeriodo.toStringAsFixed(2);
  }

  @override
  void dispose() {
    _monto.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final meta = widget.meta;

    return FormSheet(
      titulo: 'Apartar para ${meta.descripcion}',
      descripcion: 'El primer periodo se descuenta hoy de tu saldo (${formatMonto(widget.saldoActual)}).',
      accion: 'Activar apartado',
      campos: [
        MontoField(
          controller: _monto,
          label: 'Monto por periodo',
          autofocus: true,
          validator: (v) {
            final base = validarMonto(v);
            if (base != null) return base;
            if ((parsearMonto(v) ?? 0) > widget.saldoActual) {
              return 'Tu saldo no cubre el primer periodo.';
            }
            return null;
          },
        ),
        FrecuenciaField(
          valor: _periodicidad,
          opciones: const ['semanal', 'quincenal', 'mensual'],
          onChanged: (v) => setState(() => _periodicidad = v),
        ),
        // Proyección en vivo: se reconstruye con cada tecla.
        ListenableBuilder(
          listenable: _monto,
          builder: (context, _) {
            final m = parsearMonto(_monto.text) ?? 0;
            final p = periodosHasta(meta.fechaObjetivo, _periodicidad);
            final total = m * p + meta.montoAhorrado;
            final ok = total >= meta.montoObjetivo;
            return _Proyeccion(
              periodos: p,
              periodicidad: _periodicidad,
              total: total,
              objetivo: meta.montoObjetivo,
              fecha: meta.fechaObjetivo,
              alcanza: ok,
            );
          },
        ),
      ],
      onSubmit: () => widget.onCrear(
        montoPorPeriodo: parsearMonto(_monto.text)!,
        periodicidad: _periodicidad,
      ),
    );
  }
}

class _Proyeccion extends StatelessWidget {
  const _Proyeccion({
    required this.periodos,
    required this.periodicidad,
    required this.total,
    required this.objetivo,
    required this.fecha,
    required this.alcanza,
  });

  final int periodos;
  final String periodicidad;
  final double total;
  final double objetivo;
  final String fecha;
  final bool alcanza;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    final unidad = switch (periodicidad) {
      'semanal' => periodos == 1 ? 'semana' : 'semanas',
      'quincenal' => periodos == 1 ? 'quincena' : 'quincenas',
      _ => periodos == 1 ? 'mes' : 'meses',
    };
    return Container(
      padding: const EdgeInsets.all(Space.m),
      decoration: BoxDecoration(
        color: BrandColors.fondo,
        borderRadius: BorderRadius.circular(Radii.control),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('En $periodos $unidad, para el ${formatFecha(fecha)}', style: texto.bodySmall),
                const SizedBox(height: 4),
                Text(formatMonto(total), style: DisplayText.cifra),
                Text('de ${formatMonto(objetivo)}', style: texto.bodySmall),
              ],
            ),
          ),
          Icon(
            alcanza ? Icons.check_circle : Icons.remove_circle_outline,
            color: alcanza ? BrandColors.exito : BrandColors.gris,
          ),
        ],
      ),
    );
  }
}
