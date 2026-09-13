// flutter_app/lib/yo/quincena.dart
//
// Modelo puro del riel de la quincena: de hoy a la próxima nómina, con
// los pagos fijos que caen en medio. Sin Flutter, para poder probarlo.
import '../models/models.dart';
import '../shared/formatters.dart';

class EventoRiel {
  const EventoRiel({
    required this.dia,
    required this.etiqueta,
    required this.monto,
    required this.esIngreso,
  });

  /// Días desde hoy (0 = hoy).
  final int dia;
  final String etiqueta;
  final double monto;
  final bool esIngreso;
}

class RielQuincena {
  const RielQuincena({
    required this.diasTotales,
    required this.nomina,
    required this.pagos,
    required this.totalPagos,
  });

  /// Longitud del riel en días (hasta la nómina, o 14 si no hay).
  final int diasTotales;

  /// La próxima nómina, si hay una programada.
  final EventoRiel? nomina;

  /// Pagos fijos entre hoy y el final del riel, ordenados por fecha.
  final List<EventoRiel> pagos;

  final double totalPagos;

  bool get tieneNomina => nomina != null;

  /// Fracción horizontal (0..1) de un evento sobre el riel.
  double posicion(EventoRiel e) =>
      diasTotales == 0 ? 1 : (e.dia / diasTotales).clamp(0.0, 1.0);

  /// Lo que quedaría si se pagara todo lo del riel antes de cobrar.
  double saldoProyectado(double saldoActual) => saldoActual - totalPagos;
}

/// Construye el riel. Toma el ingreso programado más cercano (hoy o
/// después) como nómina; los pagos son los gastos fijos con fecha entre
/// hoy y esa nómina inclusive. Sin nómina, el riel mide 14 días.
RielQuincena construirRiel({
  required List<Recurrente> ingresos,
  required List<Recurrente> gastosFijos,
  DateTime? hoy,
}) {
  final base = hoy ?? DateTime.now();

  Recurrente? proximo;
  var proximoDias = 1 << 30;
  for (final i in ingresos) {
    final d = diasHasta(i.proximaFecha, hoy: base);
    if (d >= 0 && d < proximoDias) {
      proximo = i;
      proximoDias = d;
    }
  }

  final diasTotales = proximo != null ? (proximoDias == 0 ? 1 : proximoDias) : 14;

  final pagos = <EventoRiel>[];
  for (final g in gastosFijos) {
    final d = diasHasta(g.proximaFecha, hoy: base);
    if (d < 0 || d > diasTotales) continue;
    pagos.add(EventoRiel(dia: d, etiqueta: g.etiqueta, monto: g.monto, esIngreso: false));
  }
  pagos.sort((a, b) => a.dia.compareTo(b.dia));

  return RielQuincena(
    diasTotales: diasTotales,
    nomina: proximo == null
        ? null
        : EventoRiel(
            dia: proximoDias,
            etiqueta: proximo.etiqueta,
            monto: proximo.monto,
            esIngreso: true,
          ),
    pagos: pagos,
    totalPagos: pagos.fold(0.0, (s, e) => s + e.monto),
  );
}

/// Frase corta bajo el saldo. Habla de tiempo, no de dinero: el dinero
/// ya está en la cifra grande.
String describirNomina(RielQuincena riel) {
  final n = riel.nomina;
  if (n == null) return 'Sin ingreso programado';
  return switch (n.dia) {
    0 => 'Hoy cobras ${formatMontoCorto(n.monto)}',
    1 => 'Mañana cobras ${formatMontoCorto(n.monto)}',
    final d => '$d días para tu ${n.etiqueta.toLowerCase()}',
  };
}
