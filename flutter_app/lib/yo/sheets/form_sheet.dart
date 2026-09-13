// flutter_app/lib/yo/sheets/form_sheet.dart
//
// Esqueleto común de los formularios en bottom sheet: título, campos,
// error del backend y un solo botón primario que dice exactamente lo que
// hace. Los sheets concretos solo aportan campos y el `onSubmit`.
import 'package:flutter/material.dart';

import '../../shared/formatters.dart';
import '../../shared/widgets.dart';
import '../../theme/app_theme.dart';
import '../../theme/tokens.dart';

Future<T?> mostrarFormSheet<T>(BuildContext context, {required Widget child}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (ctx) => Padding(
      // Deja espacio al teclado para que el botón no quede tapado.
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(ctx).bottom),
      child: child,
    ),
  );
}

class FormSheet extends StatefulWidget {
  const FormSheet({
    super.key,
    required this.titulo,
    required this.accion,
    required this.campos,
    required this.onSubmit,
    this.descripcion,
    this.destructivo,
  });

  final String titulo;
  final String? descripcion;

  /// Texto del botón primario: "Agregar pago fijo", "Guardar cambios"…
  final String accion;

  /// Campos del formulario, ya construidos por el sheet concreto.
  final List<Widget> campos;

  /// Se llama solo si `Form.validate()` pasó. Lanza para mostrar error.
  final Future<void> Function() onSubmit;

  /// Acción secundaria destructiva opcional (p. ej. "Eliminar").
  final ({String texto, Future<void> Function() onTap})? destructivo;

  @override
  State<FormSheet> createState() => FormSheetState();
}

class FormSheetState extends State<FormSheet> {
  final formKey = GlobalKey<FormState>();
  bool _enviando = false;
  String? _error;

  Future<void> _submit() async {
    if (!(formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _enviando = true;
      _error = null;
    });
    try {
      await widget.onSubmit();
      if (mounted) Navigator.of(context).pop(true);
    } catch (err) {
      if (mounted) {
        setState(() => _error = describirError(err, fallback: 'No se pudo guardar. Intenta de nuevo.'));
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _destructivo() async {
    final d = widget.destructivo;
    if (d == null) return;
    setState(() {
      _enviando = true;
      _error = null;
    });
    try {
      await d.onTap();
      if (mounted) Navigator.of(context).pop(true);
    } catch (err) {
      if (mounted) {
        setState(() => _error = describirError(err, fallback: 'No se pudo completar la acción.'));
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(Space.l, Space.s, Space.l, Space.l),
      child: Form(
        key: formKey,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(widget.titulo, style: DisplayText.seccion.copyWith(fontSize: 20)),
            if (widget.descripcion != null) ...[
              const SizedBox(height: Space.xs),
              Text(widget.descripcion!, style: texto.bodySmall),
            ],
            const SizedBox(height: Space.l),
            for (final campo in widget.campos) ...[campo, const SizedBox(height: Space.m)],
            if (_error != null) ...[
              Text(_error!, style: const TextStyle(color: BrandColors.error)),
              const SizedBox(height: Space.m),
            ],
            FilledButton(
              onPressed: _enviando ? null : _submit,
              child: Text(_enviando ? 'Guardando…' : widget.accion),
            ),
            if (widget.destructivo != null) ...[
              const SizedBox(height: Space.s),
              TextButton(
                onPressed: _enviando ? null : _destructivo,
                style: TextButton.styleFrom(foregroundColor: BrandColors.error),
                child: Text(widget.destructivo!.texto),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Campo de monto con el `$` fijo a la izquierda y teclado numérico.
class MontoField extends StatelessWidget {
  const MontoField({super.key, required this.controller, required this.label, this.validator, this.autofocus = false});

  final TextEditingController controller;
  final String label;
  final String? Function(String?)? validator;
  final bool autofocus;

  @override
  Widget build(BuildContext context) {
    return TextFormField(
      controller: controller,
      autofocus: autofocus,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
      style: DisplayText.cifra.copyWith(fontSize: 20),
      decoration: InputDecoration(
        labelText: label,
        prefixText: r'$ ',
        prefixStyle: DisplayText.cifra.copyWith(fontSize: 20, color: BrandColors.gris),
      ),
      validator: validator,
    );
  }
}

/// Selector de fecha como campo de formulario (abre el DatePicker).
class FechaField extends FormField<DateTime> {
  FechaField({
    super.key,
    required String label,
    required DateTime? initial,
    required super.validator,
    required void Function(DateTime) onChanged,
    DateTime? firstDate,
  }) : super(
          initialValue: initial,
          builder: (state) {
            final valor = state.value;
            return InkWell(
              borderRadius: BorderRadius.circular(Radii.control),
              onTap: () async {
                final hoy = DateTime.now();
                final elegida = await showDatePicker(
                  context: state.context,
                  initialDate: valor ?? hoy,
                  firstDate: firstDate ?? DateTime(hoy.year - 1),
                  lastDate: DateTime(hoy.year + 5),
                );
                if (elegida != null) {
                  state.didChange(elegida);
                  onChanged(elegida);
                }
              },
              child: InputDecorator(
                decoration: InputDecoration(
                  labelText: label,
                  errorText: state.errorText,
                  suffixIcon: const Icon(Icons.calendar_today_outlined, size: 20),
                ),
                child: Text(
                  valor == null ? 'Elegir fecha' : formatFechaLarga(toFechaIso(valor)),
                  style: TextStyle(color: valor == null ? BrandColors.gris : BrandColors.tinta),
                ),
              ),
            );
          },
        );
}

/// Frecuencia como segmentos, no dropdown: cuatro opciones caben y se
/// ven de un vistazo.
class FrecuenciaField extends StatelessWidget {
  const FrecuenciaField({super.key, required this.valor, required this.onChanged, required this.opciones});

  final String valor;
  final List<String> opciones;
  final void Function(String) onChanged;

  static const _etiquetas = {
    'semanal': 'Semanal',
    'quincenal': 'Quincenal',
    'mensual': 'Mensual',
    'anual': 'Anual',
  };

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<String>(
      showSelectedIcon: false,
      style: SegmentedButton.styleFrom(
        selectedBackgroundColor: BrandColors.tinta,
        selectedForegroundColor: Colors.white,
        foregroundColor: BrandColors.tinta,
        side: const BorderSide(color: BrandColors.plata),
        textStyle: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
      ),
      segments: [
        for (final o in opciones) ButtonSegment(value: o, label: Text(_etiquetas[o] ?? o)),
      ],
      selected: {valor},
      onSelectionChanged: (s) => onChanged(s.first),
    );
  }
}
