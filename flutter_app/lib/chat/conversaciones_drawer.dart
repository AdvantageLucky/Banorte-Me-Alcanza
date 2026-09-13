// flutter_app/lib/chat/conversaciones_drawer.dart
//
// Historial de hilos del Asistente — equivalente móvil del
// ConversationSidebar.jsx del frontend web (ver GET /api/conversaciones).
// En web vive fijo al lado del chat; en teléfono no hay ancho para eso, así
// que aquí es un Drawer que se recarga cada vez que se abre.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../shared/formatters.dart';
import '../theme/tokens.dart';

class ConversacionesDrawer extends StatelessWidget {
  const ConversacionesDrawer({
    super.key,
    required this.future,
    required this.activeId,
    required this.onSelect,
    required this.onNueva,
  });

  final Future<List<Conversacion>> future;
  final int? activeId;
  final ValueChanged<int> onSelect;
  final VoidCallback onNueva;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return Drawer(
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(Space.m, Space.m, Space.m, Space.s),
              child: Text('Conversaciones', style: texto.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: Space.m),
              child: OutlinedButton.icon(
                icon: const Icon(Icons.add_comment_outlined),
                label: const Text('Nueva conversación'),
                onPressed: () {
                  Navigator.of(context).pop();
                  onNueva();
                },
              ),
            ),
            const Padding(
              padding: EdgeInsets.symmetric(vertical: Space.s),
              child: Divider(height: 1),
            ),
            Expanded(
              child: FutureBuilder<List<Conversacion>>(
                future: future,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return const Padding(
                      padding: EdgeInsets.all(Space.m),
                      child: Text('No se pudo cargar el historial. Desliza para reintentar.'),
                    );
                  }
                  final conversaciones = snapshot.data ?? const [];
                  if (conversaciones.isEmpty) {
                    return const Padding(
                      padding: EdgeInsets.all(Space.m),
                      child: Text('Todavía no tienes conversaciones guardadas.'),
                    );
                  }
                  return ListView.builder(
                    itemCount: conversaciones.length,
                    itemBuilder: (context, index) {
                      final c = conversaciones[index];
                      final activa = c.id == activeId;
                      return ListTile(
                        selected: activa,
                        selectedTileColor: BrandColors.rojo.withValues(alpha: 0.08),
                        title: Text(c.titulo, maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text(
                          c.updatedAt.length >= 10
                              ? formatFecha(c.updatedAt.substring(0, 10))
                              : c.updatedAt,
                        ),
                        onTap: () {
                          Navigator.of(context).pop();
                          if (!activa) onSelect(c.id);
                        },
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
