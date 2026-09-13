// flutter_app/lib/sugerencias/extract_sugerencia_copy.dart
//
// Extrae título y un resumen de texto de la tarjeta A2UI que el backend
// arma para una sugerencia (ver sugerencias_a2ui.py). Espejo exacto de
// frontend/src/chat/extractSugerenciaCopy.js: no duplica el copy, lo
// recombina del mismo StatCard (id 'stat') que ya se le muestra al usuario
// en la tarjeta del feed, para que el modal de "Atender" nunca diga algo
// distinto a lo que la tarjeta ya mostró.
({String titulo, String descripcion}) extraerTituloDescripcion(List<Map<String, dynamic>>? a2uiJson) {
  if (a2uiJson == null) return (titulo: '', descripcion: '');

  final mensaje = a2uiJson.firstWhere(
    (m) => m.containsKey('updateComponents'),
    orElse: () => const {},
  );
  final componentes = ((mensaje['updateComponents'] as Map?)?['components'] as List?)
          ?.map((c) => (c as Map).cast<String, dynamic>())
          .toList() ??
      const <Map<String, dynamic>>[];

  final titulo = componentes
      .firstWhere((c) => c['id'] == 'titulo', orElse: () => const {})['text'] as String? ??
      '';

  final stat = componentes.firstWhere(
    (c) => c['id'] == 'stat' && c['component'] == 'StatCard',
    orElse: () => const {},
  );
  if (stat.isNotEmpty) {
    final partes = [stat['value'], stat['trendLabel']].whereType<String>().where((s) => s.isNotEmpty);
    return (titulo: titulo, descripcion: partes.join(' — '));
  }

  final descripcion = componentes
      .firstWhere((c) => c['id'] == 'descripcion', orElse: () => const {})['text'] as String? ??
      '';
  return (titulo: titulo, descripcion: descripcion);
}
