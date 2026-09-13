// flutter_app/lib/sugerencias/atender_sugerencia_modal.dart
//
// Modal HITL antes de marcar una sugerencia como atendida — espejo de
// frontend/src/components/AtenderSugerenciaModal.jsx. Título/descripción
// son deterministas (ya se le mostraron al usuario en la tarjeta); la
// "propuesta del asistente" es texto del LLM que solo se genera si el
// usuario lo pide explícitamente, nunca automático — así nunca hay una
// alerta fantasma esperando a que alguien la lea.
import 'package:flutter/material.dart';

import '../theme/tokens.dart';

enum _EstadoPropuesta { idle, cargando, lista, error }

class AtenderSugerenciaModal extends StatefulWidget {
  const AtenderSugerenciaModal({
    super.key,
    required this.titulo,
    required this.descripcion,
    required this.onGenerarPropuesta,
  });

  final String titulo;
  final String descripcion;
  final Future<String> Function() onGenerarPropuesta;

  @override
  State<AtenderSugerenciaModal> createState() => _AtenderSugerenciaModalState();
}

class _AtenderSugerenciaModalState extends State<AtenderSugerenciaModal> {
  _EstadoPropuesta _estado = _EstadoPropuesta.idle;
  String? _propuesta;

  Future<void> _generar() async {
    setState(() => _estado = _EstadoPropuesta.cargando);
    try {
      final texto = await widget.onGenerarPropuesta();
      if (!mounted) return;
      setState(() {
        _propuesta = texto;
        _estado = _EstadoPropuesta.lista;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _estado = _EstadoPropuesta.error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return AlertDialog(
      title: const Text('¿Atender esta notificación?'),
      content: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(widget.titulo, style: texto.bodyMedium?.copyWith(fontWeight: FontWeight.w700)),
            if (widget.descripcion.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(widget.descripcion, style: texto.bodyMedium),
            ],
            const SizedBox(height: Space.m),
            switch (_estado) {
              _EstadoPropuesta.idle => Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton(
                    onPressed: _generar,
                    child: const Text('Ver propuesta del asistente'),
                  ),
                ),
              _EstadoPropuesta.cargando => Row(
                  children: [
                    const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                    const SizedBox(width: Space.s),
                    Text('Generando propuesta…', style: texto.bodySmall),
                  ],
                ),
              _EstadoPropuesta.lista => Container(
                  padding: const EdgeInsets.all(Space.s),
                  decoration: BoxDecoration(
                    color: BrandColors.fondo,
                    borderRadius: BorderRadius.circular(Radii.control),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Propuesta del asistente',
                        style: texto.bodySmall?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const SizedBox(height: 4),
                      Text(_propuesta ?? '', style: texto.bodyMedium),
                    ],
                  ),
                ),
              _EstadoPropuesta.error => Text(
                  'No se pudo generar la propuesta, intenta de nuevo.',
                  style: texto.bodySmall?.copyWith(color: BrandColors.error),
                ),
            },
            const SizedBox(height: Space.m),
            Text(
              'La detección de este aviso es determinista (reglas sobre tus datos reales); '
              'la propuesta de arriba, si la pides, la elabora el modelo de IA a partir de '
              'esos mismos hechos.',
              style: texto.bodySmall?.copyWith(color: BrandColors.gris),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop(true),
          child: const Text('Marcar como atendida'),
        ),
      ],
    );
  }
}
