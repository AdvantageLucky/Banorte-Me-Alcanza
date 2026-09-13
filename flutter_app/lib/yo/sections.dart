// flutter_app/lib/yo/sections.dart
//
// Secciones de la pestaña Yo. Cada una lista un recurso, abre su sheet
// de alta/edición y permite eliminar deslizando. Sin tarjetas: filas con
// hairline sobre el fondo técnico; la única superficie blanca es el hero.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../shared/formatters.dart';
import '../shared/widgets.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';
import 'quincena.dart';
import 'quincena_rail.dart';
import 'sheets/apartado_sheet.dart';
import 'sheets/contacto_sheet.dart';
import 'sheets/meta_sheet.dart';
import 'sheets/recurrente_sheet.dart';
import 'yo_controller.dart';

// ------------------------------------------------------------------ hero

class CuentaHero extends StatelessWidget {
  const CuentaHero({super.key, required this.controller});

  final YoController controller;

  @override
  Widget build(BuildContext context) {
    final cuenta = controller.cuenta;
    final texto = Theme.of(context).textTheme;
    final riel = construirRiel(ingresos: controller.ingresos, gastosFijos: controller.gastosFijos);

    return Container(
      color: BrandColors.superficie,
      padding: const EdgeInsets.fromLTRB(Space.m, Space.l, Space.m, Space.m),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Expanded(
                child: Text(cuenta?.titular ?? '—', style: texto.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
              ),
              Text(cuenta?.numeroEnmascarado ?? '', style: texto.bodySmall),
            ],
          ),
          const SizedBox(height: Space.m),
          // La cifra se anima al cambiar (p. ej. tras un apartado): el
          // usuario ve que su acción movió dinero de verdad.
          TweenAnimationBuilder<double>(
            tween: Tween(end: cuenta?.saldo ?? 0),
            duration: const Duration(milliseconds: 600),
            curve: Curves.easeOutCubic,
            builder: (context, valor, _) => Text(formatMonto(valor), style: DisplayText.saldo),
          ),
          const SizedBox(height: Space.xs),
          Row(
            children: [
              Expanded(child: Text(describirNomina(riel), style: texto.bodyMedium?.copyWith(color: BrandColors.gris))),
              if (controller.score != null) _ScoreChip(score: controller.score!),
            ],
          ),
          const SizedBox(height: Space.m),
          QuincenaRail(riel: riel),
          if (riel.pagos.isNotEmpty) ...[
            const SizedBox(height: Space.xs),
            Text(
              riel.saldoProyectado(cuenta?.saldo ?? 0) >= 0
                  ? 'Pagando todo antes de cobrar te quedan ${formatMonto(riel.saldoProyectado(cuenta?.saldo ?? 0))}.'
                  : 'Pagando todo antes de cobrar te faltan ${formatMonto(-riel.saldoProyectado(cuenta?.saldo ?? 0))}.',
              style: texto.bodySmall?.copyWith(
                color: riel.saldoProyectado(cuenta?.saldo ?? 0) >= 0 ? BrandColors.gris : BrandColors.error,
              ),
            ),
          ] else if (riel.tieneNomina) ...[
            const SizedBox(height: Space.xs),
            Text('Nada que pagar antes de cobrar.', style: texto.bodySmall),
          ],
        ],
      ),
    );
  }
}

class _ScoreChip extends StatelessWidget {
  const _ScoreChip({required this.score});

  final ScoreSalud score;

  @override
  Widget build(BuildContext context) {
    final color = switch (score.categoria) {
      'Saludable' => BrandColors.exito,
      'Atención' => const Color(0xFFB8860B),
      _ => BrandColors.error,
    };
    return Tooltip(
      message: score.factores.join('\n'),
      triggerMode: TooltipTriggerMode.tap,
      showDuration: const Duration(seconds: 6),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          border: Border.all(color: color),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('${score.score}', style: DisplayText.cifra.copyWith(fontSize: 15, color: color)),
            const SizedBox(width: 6),
            Text(score.categoria, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color)),
          ],
        ),
      ),
    );
  }
}

// ------------------------------------------------------- recurrentes

class RecurrentesSection extends StatelessWidget {
  const RecurrentesSection({super.key, required this.controller, required this.tipo});

  final YoController controller;
  final TipoRecurrente tipo;

  bool get _esGasto => tipo == TipoRecurrente.gasto;
  List<Recurrente> get _items => _esGasto ? controller.gastosFijos : controller.ingresos;

  Future<void> _abrir(BuildContext context, {Recurrente? existente}) async {
    final c = controller;
    final e = existente;
    await mostrarRecurrenteSheet(
      context,
      tipo: tipo,
      existente: existente,
      onGuardar: ({required etiqueta, required monto, required frecuencia, required proximaFecha}) {
        if (e == null) {
          return _esGasto
              ? c.crearGastoFijo(concepto: etiqueta, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha)
              : c.crearIngreso(descripcion: etiqueta, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha);
        }
        return _esGasto
            ? c.actualizarGastoFijo(e.id,
                concepto: etiqueta, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha)
            : c.actualizarIngreso(e.id,
                descripcion: etiqueta, monto: monto, frecuencia: frecuencia, proximaFecha: proximaFecha);
      },
      onEliminar: e == null
          ? null
          : () => _esGasto ? c.eliminarGastoFijo(e.id) : c.eliminarIngreso(e.id),
    );
  }

  Future<bool> _confirmarBorrado(BuildContext context, Recurrente r) async {
    final ok = await confirmarAccion(
      context,
      titulo: 'Eliminar ${r.etiqueta}',
      mensaje: _esGasto
          ? 'Dejará de contar en tu proyección de saldo.'
          : 'Dejará de contar como ingreso esperado.',
    );
    if (!ok) return false;
    try {
      await (_esGasto ? controller.eliminarGastoFijo(r.id) : controller.eliminarIngreso(r.id));
      return true;
    } catch (err) {
      if (context.mounted) mostrarAviso(context, describirError(err, fallback: 'No se pudo eliminar.'));
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = List.of(_items)..sort((a, b) => a.proximaFecha.compareTo(b.proximaFecha));
    final total = items.fold(0.0, (s, r) => s + r.monto);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(
          titulo: _esGasto ? 'Pagos fijos' : 'Ingresos',
          subtitulo: items.isEmpty ? null : '${formatMonto(total)} en total',
          trailing: AddButton(
            tooltip: _esGasto ? 'Agregar pago fijo' : 'Agregar ingreso',
            onPressed: () => _abrir(context),
          ),
        ),
        if (items.isEmpty)
          EmptyHint(
            texto: _esGasto
                ? 'Sin pagos fijos. Agrega renta, luz o colegiaturas para que el saldo proyectado sea real.'
                : 'Sin ingresos programados. Agrega tu nómina para saber hasta cuándo te tiene que alcanzar.',
          ),
        for (final r in items)
          Dismissible(
            key: ValueKey('${tipo.name}-${r.id}'),
            direction: DismissDirection.endToStart,
            background: const _FondoBorrar(),
            confirmDismiss: (_) => _confirmarBorrado(context, r),
            child: HairlineRow(
              onTap: () => _abrir(context, existente: r),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(r.etiqueta, style: Theme.of(context).textTheme.bodyLarge),
                        const SizedBox(height: 2),
                        Text(
                          '${describirFrecuencia(r.frecuencia)}, ${describirDias(diasHasta(r.proximaFecha))}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      ],
                    ),
                  ),
                  Text(
                    (_esGasto ? '-' : '+') + formatMonto(r.monto),
                    style: DisplayText.cifra.copyWith(fontSize: 18, color: _esGasto ? BrandColors.tinta : BrandColors.exito),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _FondoBorrar extends StatelessWidget {
  const _FondoBorrar();

  @override
  Widget build(BuildContext context) {
    return Container(
      color: BrandColors.error,
      alignment: Alignment.centerRight,
      padding: const EdgeInsets.symmetric(horizontal: Space.l),
      child: const Icon(Icons.delete_outline, color: Colors.white),
    );
  }
}

// ------------------------------------------------------------- metas

class MetasSection extends StatelessWidget {
  const MetasSection({super.key, required this.controller});

  final YoController controller;

  Future<void> _abrir(BuildContext context, {Meta? existente}) async {
    final c = controller;
    final e = existente;
    await mostrarMetaSheet(
      context,
      existente: e,
      onGuardar: ({required descripcion, required montoObjetivo, required fechaObjetivo}) => e == null
          ? c.crearMeta(descripcion: descripcion, montoObjetivo: montoObjetivo, fechaObjetivo: fechaObjetivo)
          : c.actualizarMeta(e.id,
              descripcion: descripcion, montoObjetivo: montoObjetivo, fechaObjetivo: fechaObjetivo),
      onEliminar: e == null ? null : () => c.eliminarMeta(e.id),
    );
  }

  Future<void> _apartar(BuildContext context, Meta meta) async {
    final ok = await mostrarApartadoSheet(
      context,
      meta: meta,
      saldoActual: controller.cuenta?.saldo ?? 0,
      onCrear: ({required montoPorPeriodo, required periodicidad}) =>
          controller.crearApartado(metaId: meta.id, montoPorPeriodo: montoPorPeriodo, periodicidad: periodicidad),
    );
    if (ok == true && context.mounted) mostrarAviso(context, 'Apartado activado. Ya se descontó el primer periodo.');
  }

  Future<void> _cancelarApartado(BuildContext context, Apartado a) async {
    final ok = await confirmarAccion(
      context,
      titulo: 'Cancelar apartado',
      mensaje: 'Dejarás de apartar ${formatMonto(a.montoPorPeriodo)} ${describirFrecuencia(a.periodicidad)}. Lo ya ahorrado se queda en la meta.',
      confirmar: 'Cancelar apartado',
    );
    if (!ok) return;
    try {
      await controller.cancelarApartado(a.id);
      if (context.mounted) mostrarAviso(context, 'Apartado cancelado.');
    } catch (err) {
      if (context.mounted) mostrarAviso(context, describirError(err, fallback: 'No se pudo cancelar.'));
    }
  }

  @override
  Widget build(BuildContext context) {
    final metas = controller.metas;
    final texto = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(
          titulo: 'Metas',
          trailing: AddButton(tooltip: 'Nueva meta', onPressed: () => _abrir(context)),
        ),
        if (metas.isEmpty)
          const EmptyHint(texto: 'Sin metas. Ponle nombre y fecha a algo que quieras y te decimos si te alcanza.'),
        for (final m in metas) ...[
          HairlineRow(
            onTap: () => _abrir(context, existente: m),
            padding: const EdgeInsets.fromLTRB(Space.m, 14, Space.m, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Expanded(child: Text(m.descripcion, style: texto.bodyLarge)),
                    Text(
                      '${describirDias(diasHasta(m.fechaObjetivo))}, ${formatFecha(m.fechaObjetivo)}',
                      style: texto.bodySmall,
                    ),
                  ],
                ),
                const SizedBox(height: Space.s),
                _BarraProgreso(progreso: m.progreso, completada: m.completada),
                const SizedBox(height: 6),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(formatMonto(m.montoAhorrado), style: DisplayText.cifra.copyWith(fontSize: 18)),
                    Text(' de ${formatMonto(m.montoObjetivo)}', style: texto.bodySmall),
                    const Spacer(),
                    if (m.completada)
                      const Text('Completada', style: TextStyle(color: BrandColors.exito, fontWeight: FontWeight.w600, fontSize: 13)),
                  ],
                ),
                _ApartadosDeMeta(
                  meta: m,
                  controller: controller,
                  onApartar: () => _apartar(context, m),
                  onCancelar: (a) => _cancelarApartado(context, a),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _BarraProgreso extends StatelessWidget {
  const _BarraProgreso({required this.progreso, required this.completada});

  final double progreso;
  final bool completada;

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(3),
      child: TweenAnimationBuilder<double>(
        tween: Tween(end: progreso),
        duration: const Duration(milliseconds: 600),
        curve: Curves.easeOutCubic,
        builder: (context, v, _) => LinearProgressIndicator(
          value: v,
          minHeight: 6,
          backgroundColor: const Color(0xFFE3E4E4),
          color: completada ? BrandColors.exito : BrandColors.rojo,
        ),
      ),
    );
  }
}

class _ApartadosDeMeta extends StatelessWidget {
  const _ApartadosDeMeta({
    required this.meta,
    required this.controller,
    required this.onApartar,
    required this.onCancelar,
  });

  final Meta meta;
  final YoController controller;
  final VoidCallback onApartar;
  final void Function(Apartado) onCancelar;

  @override
  Widget build(BuildContext context) {
    final activo = controller.apartadoActivoDe(meta);
    final texto = Theme.of(context).textTheme;
    return Padding(
      padding: const EdgeInsets.only(top: Space.s, bottom: Space.s),
      child: activo == null
          ? Align(
              alignment: Alignment.centerLeft,
              child: meta.completada
                  ? const SizedBox.shrink()
                  : TextButton.icon(
                      onPressed: onApartar,
                      style: TextButton.styleFrom(
                        foregroundColor: BrandColors.rojo,
                        padding: const EdgeInsets.symmetric(horizontal: Space.s),
                      ),
                      icon: const Icon(Icons.savings_outlined, size: 18),
                      label: const Text('Apartar'),
                    ),
            )
          : Row(
              children: [
                const Icon(Icons.autorenew, size: 16, color: BrandColors.gris),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    'Apartando ${formatMonto(activo.montoPorPeriodo)} ${describirFrecuencia(activo.periodicidad)} desde el ${formatFecha(activo.fechaInicio)}',
                    style: texto.bodySmall,
                  ),
                ),
                TextButton(
                  onPressed: () => onCancelar(activo),
                  style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: Space.s)),
                  child: const Text('Cancelar'),
                ),
              ],
            ),
    );
  }
}

// --------------------------------------------------------- contactos

class ContactosSection extends StatelessWidget {
  const ContactosSection({super.key, required this.controller});

  final YoController controller;

  Future<void> _abrir(BuildContext context, {Contacto? existente}) async {
    final c = controller;
    final e = existente;
    await mostrarContactoSheet(
      context,
      existente: e,
      onGuardar: ({required nombre, required alias, required cuentaDestino, required relacion}) => e == null
          ? c.crearContacto(nombre: nombre, alias: alias, cuentaDestino: cuentaDestino, relacion: relacion)
          : c.actualizarContacto(e.id,
              nombre: nombre, alias: alias, cuentaDestino: cuentaDestino, relacion: relacion),
      onEliminar: e == null ? null : () => c.eliminarContacto(e.id),
    );
  }

  Future<bool> _confirmarBorrado(BuildContext context, Contacto co) async {
    final ok = await confirmarAccion(
      context,
      titulo: 'Eliminar a ${co.alias}',
      mensaje: 'Ya no podrás pedirle al asistente que le transfiera.',
    );
    if (!ok) return false;
    try {
      await controller.eliminarContacto(co.id);
      return true;
    } catch (err) {
      if (context.mounted) mostrarAviso(context, describirError(err, fallback: 'No se pudo eliminar.'));
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    final contactos = controller.contactos;
    final texto = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(
          titulo: 'Contactos',
          subtitulo: 'A quién le puedes transferir desde el asistente',
          trailing: AddButton(tooltip: 'Agregar contacto', onPressed: () => _abrir(context)),
        ),
        if (contactos.isEmpty)
          const EmptyHint(texto: 'Sin contactos. Agrega a alguien con un alias y luego pídele al asistente: "deposítale 500 a Pepe".'),
        for (final co in contactos)
          Dismissible(
            key: ValueKey('contacto-${co.id}'),
            direction: DismissDirection.endToStart,
            background: const _FondoBorrar(),
            confirmDismiss: (_) => _confirmarBorrado(context, co),
            child: HairlineRow(
              onTap: () => _abrir(context, existente: co),
              child: Row(
                children: [
                  _Inicial(alias: co.alias),
                  const SizedBox(width: Space.m),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(co.alias, style: texto.bodyLarge),
                        const SizedBox(height: 2),
                        Text('${co.nombre}, ${co.relacion}', style: texto.bodySmall),
                      ],
                    ),
                  ),
                  Text(
                    '····${co.cuentaDestino.length > 4 ? co.cuentaDestino.substring(co.cuentaDestino.length - 4) : co.cuentaDestino}',
                    style: texto.bodySmall,
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }
}

class _Inicial extends StatelessWidget {
  const _Inicial({required this.alias});

  final String alias;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 36,
      height: 36,
      alignment: Alignment.center,
      decoration: const BoxDecoration(color: BrandColors.tinta, shape: BoxShape.circle),
      child: Text(
        alias.isEmpty ? '?' : alias[0].toUpperCase(),
        style: DisplayText.cifra.copyWith(fontSize: 16, color: Colors.white),
      ),
    );
  }
}

// ------------------------------------------------------- movimientos

class MovimientosSection extends StatelessWidget {
  const MovimientosSection({super.key, required this.controller});

  final YoController controller;

  @override
  Widget build(BuildContext context) {
    final movimientos = controller.movimientos;
    final texto = Theme.of(context).textTheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeader(titulo: 'Movimientos'),
        if (movimientos.isEmpty)
          const EmptyHint(texto: 'Aún no hay movimientos. Cuando apartes o transfieras, aparecen aquí.'),
        for (final mv in movimientos)
          HairlineRow(
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(mv.concepto, style: texto.bodyLarge),
                      const SizedBox(height: 2),
                      Text(formatFechaLarga(mv.fecha), style: texto.bodySmall),
                    ],
                  ),
                ),
                Text(
                  (mv.monto >= 0 ? '+' : '') + formatMonto(mv.monto),
                  style: DisplayText.cifra.copyWith(
                    fontSize: 18,
                    color: mv.monto >= 0 ? BrandColors.exito : BrandColors.tinta,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
