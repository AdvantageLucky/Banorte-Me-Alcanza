// flutter_app/lib/yo/sheets/meta_sheet.dart
import 'package:flutter/material.dart';

import '../../models/models.dart';
import '../../shared/formatters.dart';
import '../validators.dart';
import 'form_sheet.dart';

typedef GuardarMetaFn = Future<void> Function({
  required String descripcion,
  required double montoObjetivo,
  required String fechaObjetivo,
});

Future<bool?> mostrarMetaSheet(
  BuildContext context, {
  Meta? existente,
  required GuardarMetaFn onGuardar,
  Future<void> Function()? onEliminar,
}) {
  return mostrarFormSheet<bool>(
    context,
    child: _MetaSheet(existente: existente, onGuardar: onGuardar, onEliminar: onEliminar),
  );
}

class _MetaSheet extends StatefulWidget {
  const _MetaSheet({required this.existente, required this.onGuardar, required this.onEliminar});

  final Meta? existente;
  final GuardarMetaFn onGuardar;
  final Future<void> Function()? onEliminar;

  @override
  State<_MetaSheet> createState() => _MetaSheetState();
}

class _MetaSheetState extends State<_MetaSheet> {
  late final _descripcion = TextEditingController(text: widget.existente?.descripcion ?? '');
  late final _monto = TextEditingController(
    text: widget.existente == null ? '' : _sinCeros(widget.existente!.montoObjetivo),
  );
  late DateTime? _fecha =
      widget.existente == null ? null : parseFechaIso(widget.existente!.fechaObjetivo);

  static String _sinCeros(double v) => v == v.roundToDouble() ? v.toInt().toString() : v.toString();

  bool get _editando => widget.existente != null;

  @override
  void dispose() {
    _descripcion.dispose();
    _monto.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FormSheet(
      titulo: _editando ? 'Editar meta' : 'Nueva meta de ahorro',
      descripcion: 'Con una meta y una fecha podemos decirte si te alcanza y proponerte un apartado.',
      accion: _editando ? 'Guardar cambios' : 'Crear meta',
      destructivo: widget.onEliminar == null
          ? null
          : (texto: 'Eliminar esta meta', onTap: widget.onEliminar!),
      campos: [
        TextFormField(
          controller: _descripcion,
          autofocus: !_editando,
          textCapitalization: TextCapitalization.sentences,
          decoration: const InputDecoration(labelText: '¿Para qué ahorras?', hintText: 'Concierto, viaje, laptop…'),
          validator: (v) => validarTexto(v, campo: 'La descripción'),
        ),
        MontoField(controller: _monto, label: 'Monto objetivo', validator: validarMonto),
        FechaField(
          label: '¿Para cuándo?',
          initial: _fecha,
          validator: (v) => validarFechaFutura(v),
          onChanged: (v) => setState(() => _fecha = v),
          firstDate: DateTime.now().subtract(const Duration(days: 1)),
        ),
      ],
      onSubmit: () => widget.onGuardar(
        descripcion: _descripcion.text.trim(),
        montoObjetivo: parsearMonto(_monto.text)!,
        fechaObjetivo: toFechaIso(_fecha!),
      ),
    );
  }
}
