// flutter_app/lib/shared/widgets.dart
//
// Piezas compartidas por las tres pestañas. Pocas y quietas: la
// personalidad la llevan las cifras en BankGothic y el riel de la
// quincena, no la decoración.
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';

/// Barra superior con el wordmark y el nombre de la pestaña.
class BrandAppBar extends StatelessWidget implements PreferredSizeWidget {
  const BrandAppBar({super.key, required this.seccion, this.onLogout, this.actions = const []});

  final String seccion;
  final VoidCallback? onLogout;
  final List<Widget> actions;

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      titleSpacing: Space.m,
      title: Row(
        crossAxisAlignment: CrossAxisAlignment.baseline,
        textBaseline: TextBaseline.alphabetic,
        children: [
          const Text('Banorte', style: DisplayText.marca),
          const SizedBox(width: Space.s),
          Text(
            seccion,
            style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w400, color: Color(0xFFFFD6DE)),
          ),
        ],
      ),
      actions: [
        ...actions,
        if (onLogout != null)
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: const Icon(Icons.logout),
            onPressed: onLogout,
          ),
      ],
    );
  }
}

/// Título de sección en BankGothic con una acción opcional a la derecha.
class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.titulo, this.trailing, this.subtitulo});

  final String titulo;
  final String? subtitulo;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Space.m, Space.l, Space.s, Space.s),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(titulo, style: DisplayText.seccion),
                if (subtitulo case final sub?) ...[
                  const SizedBox(height: 2),
                  Text(sub, style: Theme.of(context).textTheme.bodySmall),
                ],
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}

/// Botón redondo de "agregar" para las cabeceras de sección.
class AddButton extends StatelessWidget {
  const AddButton({super.key, required this.onPressed, required this.tooltip});

  final VoidCallback onPressed;
  final String tooltip;

  @override
  Widget build(BuildContext context) {
    return IconButton.filledTonal(
      tooltip: tooltip,
      onPressed: onPressed,
      style: IconButton.styleFrom(
        backgroundColor: const Color(0xFFFCE4E9),
        foregroundColor: BrandColors.rojo,
      ),
      icon: const Icon(Icons.add, size: 22),
    );
  }
}

/// Estado vacío: una invitación a actuar, no un lamento.
class EmptyHint extends StatelessWidget {
  const EmptyHint({super.key, required this.texto, this.accion});

  final String texto;
  final Widget? accion;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(Space.m, Space.s, Space.m, Space.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(texto, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: BrandColors.gris)),
          if (accion != null) ...[const SizedBox(height: Space.s), accion!],
        ],
      ),
    );
  }
}

/// Fila de lista con hairline inferior. Sin tarjeta: el fondo técnico
/// y la línea de plata ya separan lo suficiente.
class HairlineRow extends StatelessWidget {
  const HairlineRow({
    super.key,
    required this.child,
    this.onTap,
    this.padding = const EdgeInsets.symmetric(horizontal: Space.m, vertical: 14),
  });

  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: padding,
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: BrandColors.plata, width: 1)),
        ),
        child: child,
      ),
    );
  }
}

/// Mensaje de error con reintento. Explica qué pasó, no pide perdón.
class ErrorRetry extends StatelessWidget {
  const ErrorRetry({super.key, required this.error, required this.onRetry});

  final Object error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final texto = error is ApiException
        ? (error as ApiException).detail ?? 'El servidor respondió con un error.'
        : 'No se pudo contactar el servidor. Revisa la conexión.';
    return Padding(
      padding: const EdgeInsets.all(Space.m),
      child: Row(
        children: [
          const Icon(Icons.error_outline, color: BrandColors.error),
          const SizedBox(width: Space.s),
          Expanded(child: Text(texto)),
          TextButton(onPressed: onRetry, child: const Text('Reintentar')),
        ],
      ),
    );
  }
}

/// Confirmación destructiva. Devuelve `true` si el usuario confirma.
Future<bool> confirmarAccion(
  BuildContext context, {
  required String titulo,
  required String mensaje,
  String confirmar = 'Eliminar',
}) async {
  final resultado = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(titulo),
      content: Text(mensaje),
      actions: [
        TextButton(onPressed: () => Navigator.of(ctx).pop(false), child: const Text('Cancelar')),
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(true),
          style: TextButton.styleFrom(foregroundColor: BrandColors.error),
          child: Text(confirmar),
        ),
      ],
    ),
  );
  return resultado ?? false;
}

void mostrarAviso(BuildContext context, String texto) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(texto)));
}

String describirError(Object error, {required String fallback}) {
  if (error is ApiException) return error.detail ?? fallback;
  return fallback;
}
