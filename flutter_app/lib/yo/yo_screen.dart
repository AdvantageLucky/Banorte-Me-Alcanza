// flutter_app/lib/yo/yo_screen.dart
//
// Pestaña Yo: un solo scroll. Arriba el hero (saldo + riel de la
// quincena) sobre superficie blanca; debajo, las secciones sobre el
// fondo técnico. Todo lo que se ve se puede editar sin salir de aquí.
import 'package:flutter/material.dart';

import '../auth/auth_controller.dart';
import '../shared/widgets.dart';
import '../theme/tokens.dart';
import 'sections.dart';
import 'sheets/recurrente_sheet.dart';
import 'yo_controller.dart';

class YoScreen extends StatefulWidget {
  const YoScreen({super.key, required this.controller, required this.authController});

  final YoController controller;
  final AuthController authController;

  @override
  State<YoScreen> createState() => _YoScreenState();
}

class _YoScreenState extends State<YoScreen> {
  @override
  void initState() {
    super.initState();
    if (!widget.controller.primeraCargaHecha) widget.controller.cargarTodo();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    return Scaffold(
      appBar: BrandAppBar(seccion: 'Yo', onLogout: widget.authController.logout),
      body: ListenableBuilder(
        listenable: c,
        builder: (context, _) {
          if (!c.primeraCargaHecha && c.cargando) {
            return const Center(child: CircularProgressIndicator());
          }
          if (c.errorGeneral != null && c.cuenta == null) {
            return Center(child: ErrorRetry(error: c.errorGeneral!, onRetry: c.cargarTodo));
          }
          return RefreshIndicator(
            onRefresh: c.cargarTodo,
            child: ListView(
              padding: const EdgeInsets.only(bottom: Space.xxl),
              children: [
                CuentaHero(controller: c),
                RecurrentesSection(controller: c, tipo: TipoRecurrente.gasto),
                MetasSection(controller: c),
                RecurrentesSection(controller: c, tipo: TipoRecurrente.ingreso),
                ContactosSection(controller: c),
                MovimientosSection(controller: c),
              ],
            ),
          );
        },
      ),
    );
  }
}
