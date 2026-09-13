// flutter_app/lib/yo/validators.dart
//
// Validadores de formulario: devuelven el mensaje de error o null.
// Mismas reglas que impone el backend (monto > 0, fechas ISO) para que el
// usuario no descubra el error después del round-trip.

String? validarTexto(String? valor, {String campo = 'Este campo'}) {
  if (valor == null || valor.trim().isEmpty) return '$campo no puede quedar vacío.';
  return null;
}

/// Acepta `1234`, `1,234.50`, `$1234.5`. Rechaza cero y negativos.
String? validarMonto(String? valor) {
  final monto = parsearMonto(valor);
  if (monto == null) return 'Escribe un monto válido.';
  if (monto <= 0) return 'El monto debe ser mayor a cero.';
  return null;
}

double? parsearMonto(String? valor) {
  if (valor == null) return null;
  final limpio = valor.replaceAll(RegExp(r'[\s\$,]'), '');
  if (limpio.isEmpty) return null;
  return double.tryParse(limpio);
}

/// La fecha no puede ser anterior a hoy (misma regla que `simular_flujo_de_caja`).
String? validarFechaFutura(DateTime? fecha, {DateTime? hoy}) {
  if (fecha == null) return 'Elige una fecha.';
  final base = hoy ?? DateTime.now();
  final hoySolo = DateTime(base.year, base.month, base.day);
  final fechaSolo = DateTime(fecha.year, fecha.month, fecha.day);
  if (fechaSolo.isBefore(hoySolo)) return 'La fecha no puede ser anterior a hoy.';
  return null;
}

/// Cuentas destino: solo dígitos, entre 6 y 18 (CLABE tiene 18).
String? validarCuentaDestino(String? valor) {
  final limpio = (valor ?? '').replaceAll(' ', '');
  if (limpio.isEmpty) return 'Escribe el número de cuenta.';
  if (!RegExp(r'^\d{6,18}$').hasMatch(limpio)) {
    return 'Solo dígitos, entre 6 y 18.';
  }
  return null;
}

const frecuencias = ['semanal', 'quincenal', 'mensual', 'anual'];
