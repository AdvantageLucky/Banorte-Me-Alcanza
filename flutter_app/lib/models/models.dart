// flutter_app/lib/models/models.dart
//
// Formas de los recursos REST del backend (src/me_alcanza/backend/dtos.py).
// Solo lo que la app lee; los payloads de escritura se arman en ApiClient.

double _num(Object? v) => (v as num).toDouble();

class Cuenta {
  const Cuenta({
    required this.titular,
    required this.numeroCuenta,
    required this.saldo,
    required this.moneda,
  });

  final String titular;
  final String numeroCuenta;
  final double saldo;
  final String moneda;

  factory Cuenta.fromJson(Map<String, dynamic> json) => Cuenta(
        titular: json['titular'] as String,
        numeroCuenta: json['numero_cuenta'] as String,
        saldo: _num(json['saldo']),
        moneda: json['moneda'] as String,
      );

  /// `001122` → `····1122`.
  String get numeroEnmascarado {
    if (numeroCuenta.length <= 4) return numeroCuenta;
    return '····${numeroCuenta.substring(numeroCuenta.length - 4)}';
  }
}

class Movimiento {
  const Movimiento({required this.fecha, required this.concepto, required this.monto});

  final String fecha;
  final String concepto;
  final double monto;

  factory Movimiento.fromJson(Map<String, dynamic> json) => Movimiento(
        fecha: json['fecha'] as String,
        concepto: json['concepto'] as String,
        monto: _num(json['monto']),
      );
}

class Contacto {
  const Contacto({
    required this.id,
    required this.nombre,
    required this.alias,
    required this.cuentaDestino,
    required this.relacion,
  });

  final int id;
  final String nombre;
  final String alias;
  final String cuentaDestino;
  final String relacion;

  factory Contacto.fromJson(Map<String, dynamic> json) => Contacto(
        id: json['id'] as int,
        nombre: json['nombre'] as String,
        alias: json['alias'] as String,
        cuentaDestino: json['cuenta_destino'] as String,
        relacion: json['relacion'] as String,
      );
}

/// Pagos fijos e ingresos programados comparten forma; solo cambia el
/// nombre del campo de texto (`concepto` vs `descripcion`) y el signo.
class Recurrente {
  const Recurrente({
    required this.id,
    required this.etiqueta,
    required this.monto,
    required this.frecuencia,
    required this.proximaFecha,
  });

  final int id;
  final String etiqueta;
  final double monto;
  final String frecuencia;
  final String proximaFecha;

  factory Recurrente.gastoFijo(Map<String, dynamic> json) => Recurrente(
        id: json['id'] as int,
        etiqueta: json['concepto'] as String,
        monto: _num(json['monto']),
        frecuencia: json['frecuencia'] as String,
        proximaFecha: json['proxima_fecha'] as String,
      );

  factory Recurrente.ingreso(Map<String, dynamic> json) => Recurrente(
        id: json['id'] as int,
        etiqueta: json['descripcion'] as String,
        monto: _num(json['monto']),
        frecuencia: json['frecuencia'] as String,
        proximaFecha: json['proxima_fecha'] as String,
      );
}

class Meta {
  const Meta({
    required this.id,
    required this.descripcion,
    required this.montoObjetivo,
    required this.fechaObjetivo,
    required this.montoAhorrado,
  });

  final int id;
  final String descripcion;
  final double montoObjetivo;
  final String fechaObjetivo;
  final double montoAhorrado;

  factory Meta.fromJson(Map<String, dynamic> json) => Meta(
        id: json['id'] as int,
        descripcion: json['descripcion'] as String,
        montoObjetivo: _num(json['monto_objetivo']),
        fechaObjetivo: json['fecha_objetivo'] as String,
        montoAhorrado: _num(json['monto_ahorrado']),
      );

  double get progreso =>
      montoObjetivo <= 0 ? 0 : (montoAhorrado / montoObjetivo).clamp(0.0, 1.0);

  bool get completada => montoAhorrado >= montoObjetivo;
}

class Apartado {
  const Apartado({
    required this.id,
    required this.metaId,
    required this.montoPorPeriodo,
    required this.periodicidad,
    required this.fechaInicio,
    required this.estado,
  });

  final int id;
  final int metaId;
  final double montoPorPeriodo;
  final String periodicidad;
  final String fechaInicio;
  final String estado;

  bool get activo => estado == 'activo';

  factory Apartado.fromJson(Map<String, dynamic> json) => Apartado(
        id: json['id'] as int,
        metaId: json['meta_id'] as int,
        montoPorPeriodo: _num(json['monto_por_periodo']),
        periodicidad: json['periodicidad'] as String,
        fechaInicio: json['fecha_inicio'] as String,
        estado: json['estado'] as String,
      );
}

class Sugerencia {
  const Sugerencia({
    required this.id,
    required this.tipo,
    required this.entidadId,
    required this.detalle,
    required this.estado,
    required this.createdAt,
    required this.resueltaAt,
    required this.a2uiJson,
  });

  final int id;
  final String tipo;
  final String entidadId;
  final Map<String, dynamic> detalle;
  final String estado;
  final String createdAt;
  final String? resueltaAt;

  /// Tarjeta A2UI ya armada por el backend. Solo viene para pendientes.
  final List<Map<String, dynamic>>? a2uiJson;

  bool get pendiente => estado == 'pendiente';

  factory Sugerencia.fromJson(Map<String, dynamic> json) => Sugerencia(
        id: json['id'] as int,
        tipo: json['tipo'] as String,
        entidadId: json['entidad_id'] as String,
        detalle: (json['detalle'] as Map).cast<String, dynamic>(),
        estado: json['estado'] as String,
        createdAt: json['created_at'] as String,
        resueltaAt: json['resuelta_at'] as String?,
        a2uiJson: (json['a2ui_json'] as List?)
            ?.map((m) => (m as Map).cast<String, dynamic>())
            .toList(),
      );

  /// Título corto para el historial, donde ya no hay tarjeta A2UI.
  String get titulo => switch (tipo) {
        'riesgo_liquidez' => 'Riesgo de saldo negativo',
        'gasto_fijo_proximo' => 'Pago próximo: ${detalle['concepto']}',
        'meta_en_riesgo' => 'Meta en riesgo: ${detalle['descripcion']}',
        _ => 'Sugerencia',
      };
}

class ScoreSalud {
  const ScoreSalud({required this.score, required this.categoria, required this.factores});

  final int score;
  final String categoria;
  final List<String> factores;

  factory ScoreSalud.fromJson(Map<String, dynamic> json) => ScoreSalud(
        score: json['score'] as int,
        categoria: json['categoria'] as String,
        factores: (json['factores'] as List).cast<String>(),
      );
}

class ChatTurnResponse {
  const ChatTurnResponse({required this.a2uiMessages, required this.conversacionId});

  final List<dynamic> a2uiMessages;

  /// Id del hilo que el backend usó (o abrió). Nulo solo con backends
  /// anteriores a la memoria de conversación.
  final int? conversacionId;
}

/// Una entrada del historial de hilos (GET /api/conversaciones) — el título
/// y la fecha son lo único que la lista necesita mostrar; el contenido se
/// pide aparte por id (ver [MensajeConversacion]).
class Conversacion {
  const Conversacion({
    required this.id,
    required this.titulo,
    required this.createdAt,
    required this.updatedAt,
  });

  final int id;
  final String titulo;
  final String createdAt;
  final String updatedAt;

  factory Conversacion.fromJson(Map<String, dynamic> json) => Conversacion(
        id: json['id'] as int,
        titulo: json['titulo'] as String,
        createdAt: json['created_at'] as String,
        updatedAt: json['updated_at'] as String,
      );
}

/// Un turno persistido de una conversación (GET
/// /api/conversaciones/{id}/mensajes). Para `rol == "model"`, `a2uiJson` trae
/// la tarjeta reconstruida por el backend (ver
/// `Orchestrator.reparsear_mensaje_modelo`) — null si ese turno es de usuario,
/// o si el texto viejo ya no parsea como A2UI válido.
class MensajeConversacion {
  const MensajeConversacion({
    required this.rol,
    required this.contenido,
    required this.createdAt,
    this.a2uiJson,
  });

  final String rol;
  final String contenido;
  final String createdAt;
  final List<dynamic>? a2uiJson;

  factory MensajeConversacion.fromJson(Map<String, dynamic> json) => MensajeConversacion(
        rol: json['rol'] as String,
        contenido: json['contenido'] as String,
        createdAt: json['created_at'] as String,
        a2uiJson: json['a2ui_json'] as List<dynamic>?,
      );
}
