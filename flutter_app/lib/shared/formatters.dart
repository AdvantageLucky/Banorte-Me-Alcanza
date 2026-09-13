// flutter_app/lib/shared/formatters.dart
//
// Formateo de dinero y fechas en español de México. Funciones puras, sin
// dependencias: lo suficiente para la app sin cargar `intl`.

const _meses = [
  'ene', 'feb', 'mar', 'abr', 'may', 'jun',
  'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
];

/// `1234.5` → `$1,234.50`. Negativos con signo al frente: `-$570.00`.
String formatMonto(num monto) {
  final negativo = monto < 0;
  final absoluto = monto.abs();
  final entero = absoluto.floor();
  final centavos = ((absoluto - entero) * 100).round();
  // Redondear centavos puede desbordar a 100 (ej. 0.999).
  final enteroAjustado = centavos == 100 ? entero + 1 : entero;
  final centavosAjustados = centavos == 100 ? 0 : centavos;

  final digitos = enteroAjustado.toString();
  final buffer = StringBuffer();
  for (var i = 0; i < digitos.length; i++) {
    final desdeFinal = digitos.length - i;
    buffer.write(digitos[i]);
    if (desdeFinal > 1 && desdeFinal % 3 == 1) buffer.write(',');
  }
  final signo = negativo ? '-' : '';
  return '$signo\$$buffer.${centavosAjustados.toString().padLeft(2, '0')}';
}

/// Versión sin centavos para etiquetas apretadas: `1234.5` → `$1,235`.
String formatMontoCorto(num monto) {
  final conCentavos = formatMonto(monto.round());
  return conCentavos.substring(0, conCentavos.length - 3);
}

DateTime parseFechaIso(String iso) => DateTime.parse(iso);

/// `2026-09-15` → `15 sep`.
String formatFecha(String iso) {
  final fecha = parseFechaIso(iso);
  return '${fecha.day} ${_meses[fecha.month - 1]}';
}

/// `2026-09-15` → `15 sep 2026`.
String formatFechaLarga(String iso) {
  final fecha = parseFechaIso(iso);
  return '${fecha.day} ${_meses[fecha.month - 1]} ${fecha.year}';
}

/// `DateTime` → `2026-09-15`, lo que espera el backend.
String toFechaIso(DateTime fecha) {
  final mes = fecha.month.toString().padLeft(2, '0');
  final dia = fecha.day.toString().padLeft(2, '0');
  return '${fecha.year}-$mes-$dia';
}

DateTime soloFecha(DateTime fecha) => DateTime(fecha.year, fecha.month, fecha.day);

/// Días completos desde [hoy] hasta [iso]. Negativo si ya pasó.
int diasHasta(String iso, {DateTime? hoy}) {
  final base = soloFecha(hoy ?? DateTime.now());
  return soloFecha(parseFechaIso(iso)).difference(base).inDays;
}

/// `0` → `hoy`, `1` → `mañana`, `3` → `en 3 días`, `-2` → `hace 2 días`.
String describirDias(int dias) {
  if (dias == 0) return 'hoy';
  if (dias == 1) return 'mañana';
  if (dias == -1) return 'ayer';
  if (dias < 0) return 'hace ${-dias} días';
  return 'en $dias días';
}

const _frecuencias = {
  'semanal': 'cada semana',
  'quincenal': 'cada quincena',
  'mensual': 'cada mes',
  'anual': 'cada año',
};

String describirFrecuencia(String frecuencia) =>
    _frecuencias[frecuencia] ?? frecuencia;
