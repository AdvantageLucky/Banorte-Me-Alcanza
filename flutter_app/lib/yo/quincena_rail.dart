// flutter_app/lib/yo/quincena_rail.dart
//
// El riel de la quincena: una línea de hoy a la próxima nómina con los
// pagos fijos marcados donde caen. Es el único elemento "bold" de la
// pantalla; todo lo demás queda quieto para que esto respire.
import 'package:flutter/material.dart';

import '../shared/formatters.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import 'quincena.dart';

class QuincenaRail extends StatelessWidget {
  const QuincenaRail({super.key, required this.riel});

  final RielQuincena riel;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: _descripcionAccesible(),
      child: SizedBox(
        height: 92,
        width: double.infinity,
        child: CustomPaint(painter: _RielPainter(riel)),
      ),
    );
  }

  String _descripcionAccesible() {
    final partes = <String>[];
    if (riel.tieneNomina) {
      partes.add('Nómina de ${formatMonto(riel.nomina!.monto)} ${describirDias(riel.nomina!.dia)}');
    }
    for (final p in riel.pagos) {
      partes.add('${p.etiqueta} ${formatMonto(p.monto)} ${describirDias(p.dia)}');
    }
    return partes.isEmpty ? 'Sin pagos ni ingresos próximos' : partes.join('. ');
  }
}

class _Cluster {
  _Cluster(this.dia);
  final int dia;
  final etiquetas = <String>[];
  double total = 0;
}

class _RielPainter extends CustomPainter {
  _RielPainter(this.riel);

  final RielQuincena riel;

  static const _baseY = 40.0;
  static const _margen = 8.0;

  @override
  void paint(Canvas canvas, Size size) {
    final x0 = _margen;
    final x1 = size.width - _margen;
    final ancho = x1 - x0;

    final linea = Paint()
      ..color = BrandColors.plata
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(x0, _baseY), Offset(x1, _baseY), linea);

    // Pagos agrupados por día: dos pagos el mismo día son una sola marca.
    final clusters = <int, _Cluster>{};
    for (final p in riel.pagos) {
      final c = clusters.putIfAbsent(p.dia, () => _Cluster(p.dia));
      c.etiquetas.add(p.etiqueta);
      c.total += p.monto;
    }
    final tick = Paint()
      ..color = BrandColors.rojo
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;
    var i = 0;
    for (final c in clusters.values.toList()..sort((a, b) => a.dia.compareTo(b.dia))) {
      final x = x0 + ancho * (riel.diasTotales == 0 ? 1 : c.dia / riel.diasTotales);
      canvas.drawLine(Offset(x, _baseY - 9), Offset(x, _baseY + 9), tick);
      // Alternar arriba/abajo para que etiquetas vecinas no se pisen.
      final arriba = i.isEven;
      final nombre = c.etiquetas.length == 1
          ? c.etiquetas.first
          : '${c.etiquetas.first} +${c.etiquetas.length - 1}';
      _texto(canvas, nombre, DisplayText.etiquetaRiel,
          x, arriba ? _baseY - 30 : _baseY + 14, ancho: ancho, alinear: _Alinear.centro);
      _texto(
        canvas,
        '-${formatMontoCorto(c.total)}',
        const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: BrandColors.tinta),
        x,
        arriba ? _baseY - 18 : _baseY + 26,
        ancho: ancho,
        alinear: _Alinear.centro,
      );
      i++;
    }

    // Hoy: punto rojo sólido al inicio.
    canvas.drawCircle(Offset(x0, _baseY), 6, Paint()..color = BrandColors.rojo);
    _texto(canvas, 'hoy', DisplayText.etiquetaRiel, x0, _baseY + 14, ancho: ancho, alinear: _Alinear.izq);

    // Nómina: círculo hueco al final con el monto encima.
    if (riel.tieneNomina) {
      final n = riel.nomina!;
      canvas.drawCircle(Offset(x1, _baseY), 6, Paint()..color = BrandColors.superficie);
      canvas.drawCircle(
        Offset(x1, _baseY),
        6,
        Paint()
          ..color = BrandColors.tinta
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
      _texto(
        canvas,
        '+${formatMontoCorto(n.monto)}',
        const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: BrandColors.exito),
        x1,
        _baseY - 24,
        ancho: ancho,
        alinear: _Alinear.der,
      );
      _texto(canvas, n.dia == 0 ? 'hoy' : formatFecha(toFechaIso(DateTime.now().add(Duration(days: n.dia)))),
          DisplayText.etiquetaRiel, x1, _baseY + 14, ancho: ancho, alinear: _Alinear.der);
    } else {
      _texto(canvas, '14 días', DisplayText.etiquetaRiel, x1, _baseY + 14, ancho: ancho, alinear: _Alinear.der);
    }
  }

  void _texto(
    Canvas canvas,
    String s,
    TextStyle estilo,
    double x,
    double y, {
    required double ancho,
    required _Alinear alinear,
  }) {
    final tp = TextPainter(
      text: TextSpan(text: s, style: estilo),
      textDirection: TextDirection.ltr,
      maxLines: 1,
      ellipsis: '…',
    )..layout(maxWidth: 96);
    final dx = switch (alinear) {
      _Alinear.izq => x,
      _Alinear.der => x - tp.width,
      _Alinear.centro => (x - tp.width / 2).clamp(_margen, _margen + ancho - tp.width),
    };
    tp.paint(canvas, Offset(dx, y));
  }

  @override
  bool shouldRepaint(covariant _RielPainter old) => old.riel != riel;
}

enum _Alinear { izq, der, centro }
