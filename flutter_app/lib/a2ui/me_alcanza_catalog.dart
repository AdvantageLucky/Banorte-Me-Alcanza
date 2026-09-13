// flutter_app/lib/a2ui/me_alcanza_catalog.dart
//
// Catálogo A2UI propio del equipo para Flutter: los primitivos básicos de
// genui más los componentes de dominio financiero que diseñamos nosotros
// (StatCard, BarChart, PlanDePago). Debe mantenerse en sync a mano con
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
      newItems: [statCard, barChart, planDePago],
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
