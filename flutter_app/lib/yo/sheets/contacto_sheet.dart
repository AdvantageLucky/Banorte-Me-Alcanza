// flutter_app/lib/yo/sheets/contacto_sheet.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../models/models.dart';
import '../validators.dart';
import 'form_sheet.dart';

typedef GuardarContactoFn = Future<void> Function({
  required String nombre,
  required String alias,
  required String cuentaDestino,
  required String relacion,
});

Future<bool?> mostrarContactoSheet(
  BuildContext context, {
  Contacto? existente,
  required GuardarContactoFn onGuardar,
  Future<void> Function()? onEliminar,
}) {
  return mostrarFormSheet<bool>(
    context,
    child: _ContactoSheet(existente: existente, onGuardar: onGuardar, onEliminar: onEliminar),
  );
}

class _ContactoSheet extends StatefulWidget {
  const _ContactoSheet({required this.existente, required this.onGuardar, required this.onEliminar});

  final Contacto? existente;
  final GuardarContactoFn onGuardar;
  final Future<void> Function()? onEliminar;

  @override
  State<_ContactoSheet> createState() => _ContactoSheetState();
}

class _ContactoSheetState extends State<_ContactoSheet> {
  late final _nombre = TextEditingController(text: widget.existente?.nombre ?? '');
  late final _alias = TextEditingController(text: widget.existente?.alias ?? '');
  late final _cuenta = TextEditingController(text: widget.existente?.cuentaDestino ?? '');
  late final _relacion = TextEditingController(text: widget.existente?.relacion ?? '');

  bool get _editando => widget.existente != null;

  @override
  void dispose() {
    _nombre.dispose();
    _alias.dispose();
    _cuenta.dispose();
    _relacion.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FormSheet(
      titulo: _editando ? 'Editar contacto' : 'Nuevo contacto',
      descripcion: 'El alias es como le dirás al asistente: "deposítale 500 a Pepe".',
      accion: _editando ? 'Guardar cambios' : 'Agregar contacto',
      destructivo: widget.onEliminar == null
          ? null
          : (texto: 'Eliminar este contacto', onTap: widget.onEliminar!),
      campos: [
        TextFormField(
          controller: _nombre,
          autofocus: !_editando,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(labelText: 'Nombre completo'),
          validator: (v) => validarTexto(v, campo: 'El nombre'),
        ),
        TextFormField(
          controller: _alias,
          textCapitalization: TextCapitalization.words,
          decoration: const InputDecoration(labelText: 'Alias', hintText: 'Pepe, mamá, casero…'),
          validator: (v) => validarTexto(v, campo: 'El alias'),
        ),
        TextFormField(
          controller: _cuenta,
          keyboardType: TextInputType.number,
          inputFormatters: [FilteringTextInputFormatter.digitsOnly],
          decoration: const InputDecoration(labelText: 'Cuenta o CLABE destino'),
          validator: validarCuentaDestino,
        ),
        TextFormField(
          controller: _relacion,
          decoration: const InputDecoration(labelText: 'Relación', hintText: 'hermano, amiga, arrendador…'),
          validator: (v) => validarTexto(v, campo: 'La relación'),
        ),
      ],
      onSubmit: () => widget.onGuardar(
        nombre: _nombre.text.trim(),
        alias: _alias.text.trim(),
        cuentaDestino: _cuenta.text.trim(),
        relacion: _relacion.text.trim(),
      ),
    );
  }
}
