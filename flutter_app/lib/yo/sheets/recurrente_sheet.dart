// flutter_app/lib/yo/sheets/recurrente_sheet.dart
//
// Alta y edición de pagos fijos e ingresos programados. Comparten forma;
// cambia el vocabulario ("pago"/"ingreso", "concepto"/"descripción").
import 'package:flutter/material.dart';

import '../../models/models.dart';
import '../../shared/formatters.dart';
import '../validators.dart';
import 'form_sheet.dart';

enum TipoRecurrente { gasto, ingreso }

typedef GuardarRecurrenteFn = Future<void> Function({
  required String etiqueta,
  required double monto,
  required String frecuencia,
  required String proximaFecha,
});

Future<bool?> mostrarRecurrenteSheet(
  BuildContext context, {
  required TipoRecurrente tipo,
  Recurrente? existente,
  required GuardarRecurrenteFn onGuardar,
  Future<void> Function()? onEliminar,
}) {
  return mostrarFormSheet<bool>(
    context,
    child: _RecurrenteSheet(
      tipo: tipo,
      existente: existente,
      onGuardar: onGuardar,
      onEliminar: onEliminar,
    ),
  );
}

class _RecurrenteSheet extends StatefulWidget {
  const _RecurrenteSheet({
    required this.tipo,
    required this.existente,
    required this.onGuardar,
    required this.onEliminar,
  });

  final TipoRecurrente tipo;
  final Recurrente? existente;
  final GuardarRecurrenteFn onGuardar;
  final Future<void> Function()? onEliminar;

  @override
  State<_RecurrenteSheet> createState() => _RecurrenteSheetState();
}

class _RecurrenteSheetState extends State<_RecurrenteSheet> {
  late final _etiqueta = TextEditingController(text: widget.existente?.etiqueta ?? '');
  late final _monto = TextEditingController(
    text: widget.existente == null ? '' : _sinCeros(widget.existente!.monto),
  );
  late String _frecuencia = widget.existente?.frecuencia ?? 'mensual';
  late DateTime? _fecha =
      widget.existente == null ? null : parseFechaIso(widget.existente!.proximaFecha);

  static String _sinCeros(double v) => v == v.roundToDouble() ? v.toInt().toString() : v.toString();

  bool get _esGasto => widget.tipo == TipoRecurrente.gasto;
  bool get _editando => widget.existente != null;

  @override
  void dispose() {
    _etiqueta.dispose();
    _monto.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cosa = _esGasto ? 'pago fijo' : 'ingreso';
    final campoTexto = _esGasto ? 'Concepto' : 'Descripción';
    return FormSheet(
      titulo: _editando ? 'Editar $cosa' : 'Nuevo $cosa',
      descripcion: _esGasto
          ? 'Lo usamos para proyectar tu saldo y avisarte antes de que venza.'
          : 'Lo usamos para saber hasta cuándo te tiene que alcanzar.',
      accion: _editando ? 'Guardar cambios' : (_esGasto ? 'Agregar pago fijo' : 'Agregar ingreso'),
      destructivo: widget.onEliminar == null
          ? null
          : (texto: _esGasto ? 'Eliminar este pago' : 'Eliminar este ingreso', onTap: widget.onEliminar!),
      campos: [
        TextFormField(
          controller: _etiqueta,
          autofocus: !_editando,
          textCapitalization: TextCapitalization.sentences,
          decoration: InputDecoration(labelText: campoTexto, hintText: _esGasto ? 'Renta, luz, colegiatura…' : 'Nómina, honorarios…'),
          validator: (v) => validarTexto(v, campo: campoTexto),
        ),
        MontoField(controller: _monto, label: 'Monto', validator: validarMonto),
        FrecuenciaField(
          valor: _frecuencia,
          opciones: frecuencias,
          onChanged: (v) => setState(() => _frecuencia = v),
        ),
        FechaField(
          label: _esGasto ? 'Próximo vencimiento' : 'Próximo cobro',
          initial: _fecha,
          validator: (v) => validarFechaFutura(v),
          onChanged: (v) => setState(() => _fecha = v),
          firstDate: DateTime.now().subtract(const Duration(days: 1)),
        ),
      ],
      onSubmit: () => widget.onGuardar(
        etiqueta: _etiqueta.text.trim(),
        monto: parsearMonto(_monto.text)!,
        frecuencia: _frecuencia,
        proximaFecha: toFechaIso(_fecha!),
      ),
    );
  }
}
