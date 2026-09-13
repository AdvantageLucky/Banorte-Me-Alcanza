// flutter_app/lib/a2ui/me_alcanza_catalog.dart
//
// Catálogo A2UI propio del equipo para Flutter: los primitivos básicos de
// genui más los componentes de dominio financiero que diseñamos nosotros
// (StatCard, BarChart, PlanDePago, LineChart, ApartadoPlanner, DonutChart,
// BudgetAllocator). Debe mantenerse en sync a mano con
// src/me_alcanza/backend/a2ui_custom_catalog.py (schemas) y con
// frontend/src/a2ui-custom/ (renderer web): mismo catalogId, mismos nombres,
// mismas props.
import 'package:flutter/material.dart';
import 'package:genui/genui.dart';
import 'package:json_schema_builder/json_schema_builder.dart';

import '../shared/formatters.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';

/// IDÉNTICO a `CUSTOM_CATALOG_ID` del backend.
const meAlcanzaCatalogId = 'https://me-alcanza.hackmty.dev/catalogs/v1/catalog.json';

/// Catálogo completo: básico + dominio, bajo el id propio. Se registra junto
/// al básico para que las superficies del modo offline (que declaran el id
/// de a2ui.org) sigan renderizando.
Catalog buildMeAlcanzaCatalog() => BasicCatalogItems.asCatalog().copyWith(
      newItems: [
        statCard,
        barChart,
        planDePago,
        lineChart,
        apartadoPlanner,
        donutChart,
        budgetAllocator,
        rowSinDesborde,
      ],
      catalogId: meAlcanzaCatalogId,
    );

Color _toneColor(String? tone) => switch (tone) {
      'positive' => BrandColors.exito,
      'negative' => BrandColors.error,
      'warning' => const Color(0xFFB8860B),
      _ => BrandColors.tinta,
    };

// ------------------------------------------------------------- StatCard

final statCard = CatalogItem(
  name: 'StatCard',
  dataSchema: S.object(
    description: 'Un dato destacado con etiqueta, tendencia y tono.',
    properties: {
      'label': A2uiSchemas.stringReference(description: 'Etiqueta corta del dato.'),
      'value': A2uiSchemas.stringReference(description: 'Valor ya formateado como texto.'),
      'trend': S.string(enumValues: ['up', 'down', 'flat']),
      'trendLabel': A2uiSchemas.stringReference(description: 'Texto junto a la tendencia.'),
      'tone': S.string(enumValues: ['positive', 'negative', 'neutral', 'warning']),
      'weight': S.number(),
    },
    required: ['label', 'value'],
  ),
  widgetBuilder: (itemContext) {
    final data = itemContext.data as Map<String, Object?>;
    final tone = _toneColor(data['tone'] as String?);
    final trend = data['trend'] as String?;
    return BoundString(
      dataContext: itemContext.dataContext,
      value: data['label'],
      builder: (context, label) => BoundString(
        dataContext: itemContext.dataContext,
        value: data['value'],
        builder: (context, value) => BoundString(
          dataContext: itemContext.dataContext,
          value: data['trendLabel'],
          builder: (context, trendLabel) => _StatCardView(
            label: label ?? '',
            value: value ?? '',
            trend: trend,
            trendLabel: trendLabel,
            tone: tone,
          ),
        ),
      ),
    );
  },
);

class _StatCardView extends StatelessWidget {
  const _StatCardView({
    required this.label,
    required this.value,
    required this.trend,
    required this.trendLabel,
    required this.tone,
  });

  final String label;
  final String value;
  final String? trend;
  final String? trendLabel;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    final IconData? icono = switch (trend) {
      'up' => Icons.north_east,
      'down' => Icons.south_east,
      'flat' => Icons.east,
      _ => null,
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Space.s),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: texto.bodySmall),
          const SizedBox(height: 2),
          Text(value, style: DisplayText.cifra.copyWith(fontSize: 26, color: tone)),
          if (icono != null || (trendLabel != null && trendLabel!.isNotEmpty)) ...[
            const SizedBox(height: 4),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icono != null) Icon(icono, size: 14, color: tone),
                if (icono != null) const SizedBox(width: 4),
                if (trendLabel != null)
                  Flexible(child: Text(trendLabel!, style: texto.bodySmall?.copyWith(color: tone))),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

// ------------------------------------------------------------- BarChart

final barChart = CatalogItem(
  name: 'BarChart',
  isImplicitlyFlexible: true,
  dataSchema: S.object(
    description: 'Gráfica de barras horizontales con datos reales.',
    properties: {
      'title': A2uiSchemas.stringReference(description: 'Título opcional.'),
      'valuePrefix': S.string(description: "Prefijo de cada valor, p. ej. '\$'."),
      'bars': S.list(
        items: S.object(
          properties: {
            'label': S.string(),
            'value': S.number(),
            'tone': S.string(enumValues: ['positive', 'negative', 'neutral', 'warning']),
          },
          required: ['label', 'value'],
        ),
      ),
      'weight': S.number(),
    },
    required: ['bars'],
  ),
  widgetBuilder: (itemContext) {
    final data = itemContext.data as Map<String, Object?>;
    final prefix = data['valuePrefix'] as String? ?? '';
    final bars = (data['bars'] as List? ?? const [])
        .map((b) => (b as Map).cast<String, Object?>())
        .map((b) => _Bar(
              label: b['label'] as String? ?? '',
              value: (b['value'] as num?)?.toDouble() ?? 0,
              tone: _toneColor(b['tone'] as String?),
            ))
        .toList();
    return BoundString(
      dataContext: itemContext.dataContext,
      value: data['title'],
      builder: (context, title) => _BarChartView(title: title, prefix: prefix, bars: bars),
    );
  },
);

class _Bar {
  const _Bar({required this.label, required this.value, required this.tone});
  final String label;
  final double value;
  final Color tone;
}

class _BarChartView extends StatelessWidget {
  const _BarChartView({required this.title, required this.prefix, required this.bars});

  final String? title;
  final String prefix;
  final List<_Bar> bars;

  String _formatear(double v) {
    if (prefix == r'$') return formatMonto(v);
    final entero = v == v.roundToDouble();
    return '$prefix${entero ? v.toInt() : v.toStringAsFixed(2)}';
  }

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    final maximo = bars.fold(0.0, (m, b) => b.value.abs() > m ? b.value.abs() : m);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (title != null && title!.isNotEmpty) ...[
          Text(title!, style: DisplayText.seccion.copyWith(fontSize: 15)),
          const SizedBox(height: Space.s),
        ],
        for (final b in bars)
          Padding(
            padding: const EdgeInsets.only(bottom: Space.s),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Expanded(child: Text(b.label, style: texto.bodyMedium)),
                    Text(_formatear(b.value), style: DisplayText.cifra.copyWith(fontSize: 15)),
                  ],
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: maximo == 0 ? 0 : (b.value.abs() / maximo)),
                    duration: const Duration(milliseconds: 500),
                    curve: Curves.easeOutCubic,
                    builder: (context, fraccion, _) => LinearProgressIndicator(
                      value: fraccion,
                      minHeight: 8,
                      backgroundColor: const Color(0xFFE3E4E4),
                      color: b.tone,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

// ----------------------------------------------------------- PlanDePago

final planDePago = CatalogItem(
  name: 'PlanDePago',
  dataSchema: S.object(
    description: 'Selector de una opción entre varios planes con monto.',
    properties: {
      'title': A2uiSchemas.stringReference(),
      'subtitle': A2uiSchemas.stringReference(),
      'options': S.list(
        items: S.object(
          properties: {
            'id': S.string(),
            'label': S.string(),
            'detail': S.string(),
            'amount': S.string(),
            'highlighted': S.boolean(),
          },
          required: ['id', 'label', 'detail', 'amount'],
        ),
      ),
      'selectedId': A2uiSchemas.stringReference(
        description: 'Id seleccionado, normalmente enlazado a un path del data model.',
      ),
      'weight': S.number(),
    },
    required: ['options', 'selectedId'],
  ),
  widgetBuilder: (itemContext) {
    final data = itemContext.data as Map<String, Object?>;
    final options = (data['options'] as List? ?? const [])
        .map((o) => (o as Map).cast<String, Object?>())
        .map((o) => _PlanOption(
              id: o['id'] as String? ?? '',
              label: o['label'] as String? ?? '',
              detail: o['detail'] as String? ?? '',
              amount: o['amount'] as String? ?? '',
              highlighted: o['highlighted'] == true,
            ))
        .toList();
    final selectedRef = data['selectedId'];
    final String? path =
        (selectedRef is Map && selectedRef['path'] is String) ? selectedRef['path'] as String : null;

    return BoundString(
      dataContext: itemContext.dataContext,
      value: data['title'],
      builder: (context, title) => BoundString(
        dataContext: itemContext.dataContext,
        value: data['subtitle'],
        builder: (context, subtitle) => BoundString(
          dataContext: itemContext.dataContext,
          value: selectedRef,
          builder: (context, selectedId) => _PlanDePagoView(
            title: title,
            subtitle: subtitle,
            options: options,
            selectedId: selectedId,
            onSelect: path == null
                ? null
                : (id) => itemContext.dataContext.update(DataPath(path), id),
          ),
        ),
      ),
    );
  },
);

class _PlanOption {
  const _PlanOption({
    required this.id,
    required this.label,
    required this.detail,
    required this.amount,
    required this.highlighted,
  });
  final String id;
  final String label;
  final String detail;
  final String amount;
  final bool highlighted;
}

class _PlanDePagoView extends StatelessWidget {
  const _PlanDePagoView({
    required this.title,
    required this.subtitle,
    required this.options,
    required this.selectedId,
    required this.onSelect,
  });

  final String? title;
  final String? subtitle;
  final List<_PlanOption> options;
  final String? selectedId;
  final void Function(String id)? onSelect;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (title != null && title!.isNotEmpty) Text(title!, style: DisplayText.seccion.copyWith(fontSize: 16)),
        if (subtitle != null && subtitle!.isNotEmpty) ...[
          const SizedBox(height: 2),
          Text(subtitle!, style: texto.bodySmall),
        ],
        const SizedBox(height: Space.s),
        for (final o in options)
          Padding(
            padding: const EdgeInsets.only(bottom: Space.s),
            child: _PlanOptionTile(
              option: o,
              selected: o.id == selectedId,
              onTap: onSelect == null ? null : () => onSelect!(o.id),
            ),
          ),
      ],
    );
  }
}

class _PlanOptionTile extends StatelessWidget {
  const _PlanOptionTile({required this.option, required this.selected, required this.onTap});

  final _PlanOption option;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return Semantics(
      button: true,
      selected: selected,
      label: '${option.label}, ${option.detail}, ${option.amount}',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(Radii.control),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          padding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 12),
          decoration: BoxDecoration(
            color: selected ? const Color(0xFFFCE4E9) : BrandColors.superficie,
            borderRadius: BorderRadius.circular(Radii.control),
            border: Border.all(
              color: selected ? BrandColors.rojo : BrandColors.plata,
              width: selected ? 2 : 1,
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(option.label, style: texto.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
                        if (option.highlighted) ...[
                          const SizedBox(width: Space.s),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: BrandColors.tinta,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'Recomendado',
                              style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.w700),
                            ),
                          ),
                        ],
                      ],
                    ),
                    const SizedBox(height: 2),
                    Text(option.detail, style: texto.bodySmall),
                  ],
                ),
              ),
              const SizedBox(width: Space.s),
              Text(option.amount, style: DisplayText.cifra.copyWith(fontSize: 17)),
              if (selected) ...[
                const SizedBox(width: Space.s),
                const Icon(Icons.check_circle, color: BrandColors.rojo, size: 20),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

// ------------------------------------------------------------ LineChart

final lineChart = CatalogItem(
  name: 'LineChart',
  isImplicitlyFlexible: true,
  dataSchema: S.object(
    description: 'Serie de puntos conectados por una línea, con línea de referencia opcional.',
    properties: {
      'title': A2uiSchemas.stringReference(description: 'Título opcional.'),
      'valuePrefix': S.string(description: "Prefijo de cada valor, p. ej. '\$'."),
      'points': S.list(
        items: S.object(
          properties: {
            'label': S.string(),
            'value': S.number(),
            'tone': S.string(enumValues: ['positive', 'negative', 'neutral', 'warning']),
          },
          required: ['label', 'value'],
        ),
      ),
      'thresholdValue': S.number(),
      'thresholdLabel': S.string(),
      'weight': S.number(),
    },
    required: ['points'],
  ),
  widgetBuilder: (itemContext) {
    final data = itemContext.data as Map<String, Object?>;
    final prefix = data['valuePrefix'] as String? ?? '';
    final points = (data['points'] as List? ?? const [])
        .map((p) => (p as Map).cast<String, Object?>())
        .map((p) => _LinePoint(
              label: p['label'] as String? ?? '',
              value: (p['value'] as num?)?.toDouble() ?? 0,
              tone: p['tone'] as String?,
            ))
        .toList();
    final thresholdValue = (data['thresholdValue'] as num?)?.toDouble();
    final thresholdLabel = data['thresholdLabel'] as String?;
    return BoundString(
      dataContext: itemContext.dataContext,
      value: data['title'],
      builder: (context, title) => _LineChartView(
        title: title,
        prefix: prefix,
        points: points,
        thresholdValue: thresholdValue,
        thresholdLabel: thresholdLabel,
      ),
    );
  },
);

class _LinePoint {
  const _LinePoint({required this.label, required this.value, required this.tone});
  final String label;
  final double value;
  final String? tone;
}

class _LineChartView extends StatelessWidget {
  const _LineChartView({
    required this.title,
    required this.prefix,
    required this.points,
    required this.thresholdValue,
    required this.thresholdLabel,
  });

  final String? title;
  final String prefix;
  final List<_LinePoint> points;
  final double? thresholdValue;
  final String? thresholdLabel;

  String _formatear(double v) {
    if (prefix == r'$') return formatMonto(v);
    final entero = v == v.roundToDouble();
    return '$prefix${entero ? v.toInt() : v.toStringAsFixed(2)}';
  }

  @override
  Widget build(BuildContext context) {
    if (points.length < 2) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (title != null && title!.isNotEmpty) ...[
          Text(title!, style: DisplayText.seccion.copyWith(fontSize: 15)),
          const SizedBox(height: Space.s),
        ],
        SizedBox(
          height: 200,
          width: double.infinity,
          child: CustomPaint(
            painter: _LineChartPainter(
              points: points,
              thresholdValue: thresholdValue,
              thresholdLabel: thresholdLabel,
              formatValue: _formatear,
            ),
          ),
        ),
      ],
    );
  }
}

class _LineChartPainter extends CustomPainter {
  _LineChartPainter({
    required this.points,
    required this.thresholdValue,
    required this.thresholdLabel,
    required this.formatValue,
  });

  final List<_LinePoint> points;
  final double? thresholdValue;
  final String? thresholdLabel;
  final String Function(double) formatValue;

  @override
  void paint(Canvas canvas, Size size) {
    const padTop = 24.0;
    const padBottom = 24.0;
    final plotHeight = size.height - padTop - padBottom;
    final plotWidth = size.width;

    final values = points.map((p) => p.value).toList();
    final allValues = [...values, ?thresholdValue];
    final rawMin = allValues.reduce((a, b) => a < b ? a : b);
    final rawMax = allValues.reduce((a, b) => a > b ? a : b);
    final span = (rawMax - rawMin) == 0 ? 1.0 : (rawMax - rawMin);
    final min = rawMin - span * 0.1;
    final max = rawMax + span * 0.1;

    double xAt(int i) => points.length == 1 ? 0 : (i / (points.length - 1)) * plotWidth;
    double yAt(double value) => padTop + plotHeight - ((value - min) / (max - min)) * plotHeight;

    final linePath = Path();
    for (var i = 0; i < points.length; i++) {
      final x = xAt(i);
      final y = yAt(points[i].value);
      if (i == 0) {
        linePath.moveTo(x, y);
      } else {
        linePath.lineTo(x, y);
      }
    }

    final areaPath = Path();
    for (var i = 0; i < points.length; i++) {
      final x = xAt(i);
      final y = yAt(points[i].value);
      if (i == 0) {
        areaPath.moveTo(x, y);
      } else {
        areaPath.lineTo(x, y);
      }
    }
    areaPath.lineTo(xAt(points.length - 1), padTop + plotHeight);
    areaPath.lineTo(xAt(0), padTop + plotHeight);
    areaPath.close();

    canvas.drawPath(areaPath, Paint()..color = BrandColors.rojo.withValues(alpha: 0.1));

    if (thresholdValue != null) {
      final y = yAt(thresholdValue!);
      final dashPaint = Paint()
        ..color = BrandColors.gris
        ..strokeWidth = 1;
      const dashWidth = 4.0;
      const dashSpace = 4.0;
      var startX = 0.0;
      while (startX < plotWidth) {
        canvas.drawLine(Offset(startX, y), Offset(startX + dashWidth, y), dashPaint);
        startX += dashWidth + dashSpace;
      }
      if (thresholdLabel != null) {
        final tp = TextPainter(
          text: TextSpan(text: thresholdLabel, style: const TextStyle(color: BrandColors.gris, fontSize: 10)),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(plotWidth - tp.width, y - tp.height - 2));
      }
    }

    canvas.drawPath(
      linePath,
      Paint()
        ..color = BrandColors.rojo
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );

    final criticalIndex = points.indexWhere((p) => p.tone == 'negative' || p.tone == 'warning');

    for (var i = 0; i < points.length; i++) {
      final x = xAt(i);
      final y = yAt(points[i].value);
      final isCritical = i == criticalIndex;
      final dotColor = switch (points[i].tone) {
        'negative' => BrandColors.error,
        'warning' => const Color(0xFFB8860B),
        'positive' => BrandColors.exito,
        _ => BrandColors.rojo,
      };
      canvas.drawCircle(Offset(x, y), isCritical ? 6 : 4, Paint()..color = dotColor);
      canvas.drawCircle(
        Offset(x, y),
        isCritical ? 6 : 4,
        Paint()
          ..color = BrandColors.superficie
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );

      if (isCritical) {
        final tp = TextPainter(
          text: TextSpan(
            text: formatValue(points[i].value),
            style: const TextStyle(color: BrandColors.tinta, fontSize: 12, fontWeight: FontWeight.bold),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(x - tp.width / 2, y - tp.height - 10));
      }

      final labelTp = TextPainter(
        text: TextSpan(text: points[i].label, style: const TextStyle(color: BrandColors.gris, fontSize: 10)),
        textDirection: TextDirection.ltr,
      )..layout();
      labelTp.paint(canvas, Offset(x - labelTp.width / 2, size.height - padBottom + 6));
    }
  }

  @override
  bool shouldRepaint(covariant _LineChartPainter oldDelegate) {
    return oldDelegate.points != points ||
        oldDelegate.thresholdValue != thresholdValue ||
        oldDelegate.thresholdLabel != thresholdLabel;
  }
}

// ------------------------------------------------------ ApartadoPlanner

final apartadoPlanner = CatalogItem(
  name: 'ApartadoPlanner',
  dataSchema: S.object(
    description: 'Slider interactivo que recalcula EN EL CLIENTE cuántos periodos hacen falta.',
    properties: {
      'title': A2uiSchemas.stringReference(),
      'subtitle': A2uiSchemas.stringReference(),
      'montoObjetivo': S.number(),
      'periodicidadLabel': S.string(),
      'minMonto': S.number(),
      'maxMonto': S.number(),
      'montoPorPeriodo': A2uiSchemas.numberReference(),
    },
    required: ['montoObjetivo', 'periodicidadLabel', 'minMonto', 'maxMonto', 'montoPorPeriodo'],
  ),
  widgetBuilder: (itemContext) {
    final data = itemContext.data as Map<String, Object?>;
    final montoObjetivo = (data['montoObjetivo'] as num).toDouble();
    final periodicidadLabel = data['periodicidadLabel'] as String? ?? '';
    final minMonto = (data['minMonto'] as num).toDouble();
    final maxMonto = (data['maxMonto'] as num).toDouble();
    final montoRef = data['montoPorPeriodo'];
    final path = (montoRef is Map && montoRef.containsKey('path'))
        ? montoRef['path'] as String
        : '${itemContext.id}.montoPorPeriodo';

    return BoundString(
      dataContext: itemContext.dataContext,
      value: data['title'],
      builder: (context, title) => BoundString(
        dataContext: itemContext.dataContext,
        value: data['subtitle'],
        builder: (context, subtitle) => BoundNumber(
          dataContext: itemContext.dataContext,
          value: {'path': path},
          builder: (context, value) {
            var monto = value?.toDouble();
            monto ??= (montoRef is num) ? montoRef.toDouble() : minMonto;
            return _ApartadoPlannerView(
              title: title,
              subtitle: subtitle,
              montoObjetivo: montoObjetivo,
              periodicidadLabel: periodicidadLabel,
              minMonto: minMonto,
              maxMonto: maxMonto,
              monto: monto,
              onChanged: (v) => itemContext.dataContext.update(DataPath(path), v),
            );
          },
        ),
      ),
    );
  },
);

class _ApartadoPlannerView extends StatelessWidget {
  const _ApartadoPlannerView({
    required this.title,
    required this.subtitle,
    required this.montoObjetivo,
    required this.periodicidadLabel,
    required this.minMonto,
    required this.maxMonto,
    required this.monto,
    required this.onChanged,
  });

  final String? title;
  final String? subtitle;
  final double montoObjetivo;
  final String periodicidadLabel;
  final double minMonto;
  final double maxMonto;
  final double monto;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    final montoSeguro = monto <= 0 ? 1.0 : monto;
    final periodos = (montoObjetivo / montoSeguro).ceil().clamp(1, 999999);
    final total = periodos * montoSeguro;
    final alcanzaCompleto = total >= montoObjetivo;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (title != null && title!.isNotEmpty)
          Text(title!, style: DisplayText.seccion.copyWith(fontSize: 16)),
        if (subtitle != null && subtitle!.isNotEmpty) ...[
          const SizedBox(height: 2),
          Text(subtitle!, style: texto.bodySmall),
        ],
        const SizedBox(height: Space.s),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text('$periodos', style: DisplayText.cifra.copyWith(fontSize: 32, color: BrandColors.rojo)),
            const SizedBox(width: Space.s),
            Flexible(
              child: Text(
                'pago${periodos == 1 ? '' : 's'} ${periodicidadLabel}es de ${formatMonto(montoSeguro)}',
                style: texto.bodySmall,
              ),
            ),
          ],
        ),
        Slider(
          value: montoSeguro.clamp(minMonto, maxMonto),
          min: minMonto,
          max: maxMonto,
          activeColor: BrandColors.rojo,
          onChanged: onChanged,
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(formatMonto(minMonto), style: texto.bodySmall?.copyWith(fontSize: 11, color: BrandColors.gris)),
              Text(formatMonto(maxMonto), style: texto.bodySmall?.copyWith(fontSize: 11, color: BrandColors.gris)),
            ],
          ),
        ),
        const SizedBox(height: Space.xs),
        Text(
          'Total cubierto: ${formatMonto(total)} de ${formatMonto(montoObjetivo)}',
          style: texto.bodySmall?.copyWith(
            fontWeight: FontWeight.w600,
            color: alcanzaCompleto ? BrandColors.exito : const Color(0xFFB8860B),
          ),
        ),
      ],
    );
  }
}

// -------------------------------------------------------- DonutChart

// Paleta fija asignada por posición, no por nombre: 'label' viene de datos
// reales (get_resumen_movimientos) y es texto libre.
const _donutPalette = [
  BrandColors.rojo,
  BrandColors.exito,
  Color(0xFFB8860B),
  Color(0xFF2F6FED),
  Color(0xFF8A4FD8),
  Color(0xFF0F9AA8),
  BrandColors.gris,
];

final donutChart = CatalogItem(
  name: 'DonutChart',
  isImplicitlyFlexible: true,
  dataSchema: S.object(
    description: 'Dona de proporciones sobre un total, con leyenda y porción resaltable.',
    properties: {
      'title': A2uiSchemas.stringReference(description: 'Título opcional.'),
      'centerLabel': A2uiSchemas.stringReference(description: 'Etiqueta pequeña al centro.'),
      'centerValue': A2uiSchemas.stringReference(description: 'Valor grande al centro, ya formateado.'),
      'slices': S.list(
        items: S.object(
          properties: {
            'id': S.string(),
            'label': S.string(),
            'value': S.number(),
          },
          required: ['id', 'label', 'value'],
        ),
      ),
      'selectedId': A2uiSchemas.stringReference(
        description: 'Id de la porción resaltada, enlazado a un path del data model.',
      ),
      'weight': S.number(),
    },
    required: ['slices'],
  ),
  widgetBuilder: (itemContext) {
    final data = itemContext.data as Map<String, Object?>;
    final slices = (data['slices'] as List? ?? const [])
        .map((s) => (s as Map).cast<String, Object?>())
        .map((s) => _DonutSlice(
              id: s['id'] as String? ?? '',
              label: s['label'] as String? ?? '',
              value: (s['value'] as num?)?.toDouble() ?? 0,
            ))
        .toList();
    final selectedRef = data['selectedId'];
    final String? path =
        (selectedRef is Map && selectedRef['path'] is String) ? selectedRef['path'] as String : null;

    return BoundString(
      dataContext: itemContext.dataContext,
      value: data['title'],
      builder: (context, title) => BoundString(
        dataContext: itemContext.dataContext,
        value: data['centerLabel'],
        builder: (context, centerLabel) => BoundString(
          dataContext: itemContext.dataContext,
          value: data['centerValue'],
          builder: (context, centerValue) => BoundString(
            dataContext: itemContext.dataContext,
            value: selectedRef,
            builder: (context, selectedId) => _DonutChartView(
              title: title,
              centerLabel: centerLabel,
              centerValue: centerValue,
              slices: slices,
              selectedId: selectedId,
              onSelect: path == null ? null : (id) => itemContext.dataContext.update(DataPath(path), id),
            ),
          ),
        ),
      ),
    );
  },
);

class _DonutSlice {
  const _DonutSlice({required this.id, required this.label, required this.value});
  final String id;
  final String label;
  final double value;
}

class _DonutChartView extends StatelessWidget {
  const _DonutChartView({
    required this.title,
    required this.centerLabel,
    required this.centerValue,
    required this.slices,
    required this.selectedId,
    required this.onSelect,
  });

  final String? title;
  final String? centerLabel;
  final String? centerValue;
  final List<_DonutSlice> slices;
  final String? selectedId;
  final void Function(String id)? onSelect;

  @override
  Widget build(BuildContext context) {
    if (slices.length < 2) return const SizedBox.shrink();
    final texto = Theme.of(context).textTheme;
    final total = slices.fold(0.0, (s, e) => s + e.value.abs());
    final divisor = total == 0 ? 1.0 : total;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (title != null && title!.isNotEmpty) ...[
          Text(title!, style: DisplayText.seccion.copyWith(fontSize: 15)),
          const SizedBox(height: Space.s),
        ],
        Wrap(
          spacing: Space.m,
          runSpacing: Space.m,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SizedBox(
              width: 150,
              height: 150,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  CustomPaint(
                    size: const Size(150, 150),
                    painter: _DonutChartPainter(slices: slices, selectedId: selectedId, divisor: divisor),
                  ),
                  if (centerValue != null || centerLabel != null)
                    Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (centerValue != null && centerValue!.isNotEmpty)
                          Text(
                            centerValue!,
                            style: DisplayText.cifra.copyWith(fontSize: 18, color: BrandColors.tinta),
                          ),
                        if (centerLabel != null && centerLabel!.isNotEmpty)
                          Text(centerLabel!, style: texto.bodySmall?.copyWith(fontSize: 11, color: BrandColors.gris)),
                      ],
                    ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: Space.s),
        for (var i = 0; i < slices.length; i++)
          _DonutLegendRow(
            slice: slices[i],
            color: _donutPalette[i % _donutPalette.length],
            pct: slices[i].value.abs() / divisor,
            selected: selectedId != null && slices[i].id == selectedId,
            onTap: onSelect == null ? null : () => onSelect!(slices[i].id),
            style: texto.bodySmall,
          ),
      ],
    );
  }
}

class _DonutLegendRow extends StatelessWidget {
  const _DonutLegendRow({
    required this.slice,
    required this.color,
    required this.pct,
    required this.selected,
    required this.onTap,
    required this.style,
  });

  final _DonutSlice slice;
  final Color color;
  final double pct;
  final bool selected;
  final VoidCallback? onTap;
  final TextStyle? style;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? color.withValues(alpha: 0.08) : null,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Row(
          children: [
            Container(width: 10, height: 10, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
            const SizedBox(width: Space.s),
            Expanded(child: Text(slice.label, style: style, overflow: TextOverflow.ellipsis)),
            Text('${(pct * 100).round()}%', style: style?.copyWith(color: BrandColors.gris)),
            const SizedBox(width: Space.s),
            Text(formatMonto(slice.value), style: style?.copyWith(fontWeight: FontWeight.w600)),
          ],
        ),
      ),
    );
  }
}

class _DonutChartPainter extends CustomPainter {
  _DonutChartPainter({required this.slices, required this.selectedId, required this.divisor});

  final List<_DonutSlice> slices;
  final String? selectedId;
  final double divisor;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    const stroke = 22.0;
    final radius = (size.width - stroke) / 2;
    var startAngle = -3.14159265 / 2;

    for (var i = 0; i < slices.length; i++) {
      final slice = slices[i];
      final sweep = (slice.value.abs() / divisor) * 2 * 3.14159265;
      final isSelected = selectedId != null && slice.id == selectedId;
      final paint = Paint()
        ..color = _donutPalette[i % _donutPalette.length]
            .withValues(alpha: selectedId != null && !isSelected ? 0.45 : 1)
        ..style = PaintingStyle.stroke
        ..strokeWidth = isSelected ? stroke + 6 : stroke
        ..strokeCap = StrokeCap.butt;
      canvas.drawArc(Rect.fromCircle(center: center, radius: radius), startAngle, sweep, false, paint);
      startAngle += sweep;
    }
  }

  @override
  bool shouldRepaint(covariant _DonutChartPainter oldDelegate) {
    return oldDelegate.slices != slices || oldDelegate.selectedId != selectedId;
  }
}

// ---------------------------------------------------- BudgetAllocator

// Un solo grado de libertad (categoriaSeleccionada + montoAsignado): igual
// que ApartadoPlanner, todo el cálculo es una función pura de props para
// garantizar que React y Flutter muestren SIEMPRE el mismo número a partir
// del mismo stream A2UI — nunca reparto entre N categorías a la vez.
final budgetAllocator = CatalogItem(
  name: 'BudgetAllocator',
  dataSchema: S.object(
    description: 'Reparte un monto real entre destinos reales, uno a la vez.',
    properties: {
      'title': A2uiSchemas.stringReference(),
      'subtitle': A2uiSchemas.stringReference(),
      'total': S.number(),
      'categorias': S.list(
        items: S.object(
          properties: {'id': S.string(), 'label': S.string()},
          required: ['id', 'label'],
        ),
      ),
      'categoriaSeleccionada': A2uiSchemas.stringReference(),
      'montoAsignado': A2uiSchemas.numberReference(),
    },
    required: ['total', 'categorias', 'categoriaSeleccionada', 'montoAsignado'],
  ),
  widgetBuilder: (itemContext) {
    final data = itemContext.data as Map<String, Object?>;
    final total = (data['total'] as num).toDouble();
    final categorias = (data['categorias'] as List? ?? const [])
        .map((c) => (c as Map).cast<String, Object?>())
        .map((c) => _Categoria(id: c['id'] as String? ?? '', label: c['label'] as String? ?? ''))
        .toList();
    final catRef = data['categoriaSeleccionada'];
    final catPath = (catRef is Map && catRef['path'] is String) ? catRef['path'] as String : null;
    final montoRef = data['montoAsignado'];
    final montoPath = (montoRef is Map && montoRef.containsKey('path'))
        ? montoRef['path'] as String
        : '${itemContext.id}.montoAsignado';

    return BoundString(
      dataContext: itemContext.dataContext,
      value: data['title'],
      builder: (context, title) => BoundString(
        dataContext: itemContext.dataContext,
        value: data['subtitle'],
        builder: (context, subtitle) => BoundString(
          dataContext: itemContext.dataContext,
          value: catRef,
          builder: (context, categoriaSeleccionada) => BoundNumber(
            dataContext: itemContext.dataContext,
            value: {'path': montoPath},
            builder: (context, value) {
              var monto = value?.toDouble();
              monto ??= (montoRef is num) ? montoRef.toDouble() : 0.0;
              return _BudgetAllocatorView(
                title: title,
                subtitle: subtitle,
                total: total,
                categorias: categorias.isEmpty ? const [_Categoria(id: '', label: '')] : categorias,
                categoriaSeleccionada: categoriaSeleccionada,
                monto: monto,
                onSelectCategoria: catPath == null
                    ? null
                    : (id) => itemContext.dataContext.update(DataPath(catPath), id),
                onChangeMonto: (v) => itemContext.dataContext.update(DataPath(montoPath), v),
              );
            },
          ),
        ),
      ),
    );
  },
);

class _Categoria {
  const _Categoria({required this.id, required this.label});
  final String id;
  final String label;
}

class _BudgetAllocatorView extends StatelessWidget {
  const _BudgetAllocatorView({
    required this.title,
    required this.subtitle,
    required this.total,
    required this.categorias,
    required this.categoriaSeleccionada,
    required this.monto,
    required this.onSelectCategoria,
    required this.onChangeMonto,
  });

  final String? title;
  final String? subtitle;
  final double total;
  final List<_Categoria> categorias;
  final String? categoriaSeleccionada;
  final double monto;
  final void Function(String id)? onSelectCategoria;
  final ValueChanged<double> onChangeMonto;

  @override
  Widget build(BuildContext context) {
    if (categorias.length < 2) return const SizedBox.shrink();
    final texto = Theme.of(context).textTheme;
    final activaId = categoriaSeleccionada ?? categorias.first.id;
    final activa = categorias.firstWhere((c) => c.id == activaId, orElse: () => categorias.first);
    final montoAcotado = monto.clamp(0.0, total);
    final restante = total - montoAcotado;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        if (title != null && title!.isNotEmpty)
          Text(title!, style: DisplayText.seccion.copyWith(fontSize: 16)),
        if (subtitle != null && subtitle!.isNotEmpty) ...[
          const SizedBox(height: 2),
          Text(subtitle!, style: texto.bodySmall),
        ],
        const SizedBox(height: Space.s),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final c in categorias)
              ChoiceChip(
                label: Text(c.label),
                selected: c.id == activaId,
                selectedColor: const Color(0xFFFCE4E9),
                onSelected: onSelectCategoria == null ? null : (_) => onSelectCategoria!(c.id),
              ),
          ],
        ),
        const SizedBox(height: Space.s),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(formatMonto(montoAcotado), style: DisplayText.cifra.copyWith(fontSize: 28, color: BrandColors.rojo)),
            const SizedBox(width: Space.s),
            Flexible(child: Text('para ${activa.label}', style: texto.bodySmall)),
          ],
        ),
        Slider(
          value: montoAcotado,
          min: 0,
          max: total <= 0 ? 1 : total,
          activeColor: BrandColors.rojo,
          onChanged: onChangeMonto,
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(formatMonto(0), style: texto.bodySmall?.copyWith(fontSize: 11, color: BrandColors.gris)),
              Text(formatMonto(total), style: texto.bodySmall?.copyWith(fontSize: 11, color: BrandColors.gris)),
            ],
          ),
        ),
        const SizedBox(height: Space.xs),
        Text(
          'Sin asignar: ${formatMonto(restante)} de ${formatMonto(total)}',
          style: texto.bodySmall?.copyWith(fontWeight: FontWeight.w600),
        ),
      ],
    );
  }
}

// ------------------------------------------------------ Row sin desborde
//
// El 'Row' del catálogo básico de genui deja sin envolver en `Flexible` a
// cualquier hijo sin `weight` explícito (ver `buildWeightedChild` en el
// paquete: solo envuelve si `weight != null`). Combinado con
// `mainAxisSize: MainAxisSize.min`, eso le da a esos hijos un ancho máximo
// sin acotar — si el modelo arma un Row de dos Text (el patrón habitual
// "etiqueta: valor" en tarjetas de simulación) y el total no cabe, el Row
// desborda horizontalmente en vez de partir la línea. En debug se ve como
// el banner de overflow (visto en tarjetas de "Monto objetivo del
// concierto" / "Saldo mínimo proyectado"); en release el texto sencillamente
// se recorta sin aviso.
//
// Se sobreescribe el item 'Row' del catálogo básico (mismo nombre => lo
// reemplaza `Catalog.copyWith`) para que TODO hijo sin `weight` también
// quede envuelto en un `Flexible` suelto con flex 1. Un hijo que ya cabía no
// cambia de tamaño (Flexible suelto no fuerza a ocupar más espacio del que
// necesita); uno que no cabía ahora envuelve texto en vez de desbordar. Los
// hijos con `weight` explícito se comportan exactamente igual que antes.
MainAxisAlignment _parseJustify(String? value) => switch (value) {
      'center' => MainAxisAlignment.center,
      'end' => MainAxisAlignment.end,
      'spaceBetween' => MainAxisAlignment.spaceBetween,
      'spaceAround' => MainAxisAlignment.spaceAround,
      'spaceEvenly' => MainAxisAlignment.spaceEvenly,
      _ => MainAxisAlignment.start,
    };

CrossAxisAlignment _parseAlign(String? value) => switch (value) {
      'center' => CrossAxisAlignment.center,
      'end' => CrossAxisAlignment.end,
      'stretch' => CrossAxisAlignment.stretch,
      _ => CrossAxisAlignment.start,
    };

Widget _buildRowChild({
  required String componentId,
  required DataContext dataContext,
  required ChildBuilderCallback buildChild,
  required GetComponentCallback getComponent,
  Key? key,
}) {
  final explicitWeight = getComponent(componentId)?.properties['weight'] as int?;
  return buildWeightedChild(
    componentId: componentId,
    dataContext: dataContext,
    buildChild: buildChild,
    weight: explicitWeight ?? 1,
    flexFit: explicitWeight != null ? FlexFit.tight : FlexFit.loose,
    key: key,
  );
}

final rowSinDesborde = CatalogItem(
  name: 'Row',
  dataSchema: S.object(
    description: 'A layout widget that arranges its children horizontally.',
    properties: {
      'children': A2uiSchemas.componentArrayReference(
        description:
            'Either an explicit list of widget IDs for the children, or a '
            'template with a data binding to the list of children.',
      ),
      'justify': S.string(
        enumValues: ['start', 'center', 'end', 'spaceBetween', 'spaceAround', 'spaceEvenly'],
      ),
      'align': S.string(enumValues: ['start', 'center', 'end', 'stretch']),
    },
    required: ['children'],
  ),
  widgetBuilder: (itemContext) {
    final json = itemContext.data as Map<String, Object?>;
    final children = json['children'];
    final justify = _parseJustify(json['justify'] as String?);
    final align = _parseAlign(json['align'] as String?);

    return ComponentChildrenBuilder(
      childrenData: children,
      dataContext: itemContext.dataContext,
      buildChild: itemContext.buildChild,
      getComponent: itemContext.getComponent,
      explicitListBuilder: (childIds, buildChild, getComponent, dataContext) => Row(
        mainAxisAlignment: justify,
        crossAxisAlignment: align,
        mainAxisSize: MainAxisSize.min,
        spacing: 16,
        children: childIds
            .map((id) => _buildRowChild(
                  componentId: id,
                  dataContext: dataContext,
                  buildChild: buildChild,
                  getComponent: getComponent,
                ))
            .toList(),
      ),
      templateListWidgetBuilder: (context, data, componentId, dataBinding) {
        final List<Object?> values;
        final List<String> keys;
        if (data is List) {
          values = data;
          keys = List.generate(data.length, (index) => index.toString());
        } else if (data is Map) {
          values = data.values.toList();
          keys = data.keys.map((k) => k.toString()).toList();
        } else {
          return const SizedBox.shrink();
        }

        return Row(
          mainAxisAlignment: justify,
          crossAxisAlignment: align,
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < values.length; i++)
              _buildRowChild(
                componentId: componentId,
                dataContext: itemContext.dataContext.nested(DataPath('$dataBinding/${keys[i]}')),
                buildChild: itemContext.buildChild,
                getComponent: itemContext.getComponent,
                key: ValueKey(keys[i]),
              ),
          ],
        );
      },
    );
  },
);
