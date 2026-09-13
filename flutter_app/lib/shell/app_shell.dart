// flutter_app/lib/shell/app_shell.dart
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../auth/auth_controller.dart';
import '../chat/chat_screen.dart';
import '../login/login_screen.dart';
import '../sugerencias/sugerencias_controller.dart';
import '../sugerencias/sugerencias_screen.dart';
import '../yo/yo_controller.dart';
import '../yo/yo_screen.dart';

class AppShell extends StatefulWidget {
  const AppShell({
    super.key,
    required this.apiClient,
    required this.authController,
  });

  final ApiClient apiClient;
  final AuthController authController;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  // Sugerencias es la pestaña inicial: es lo que la app te dice sin que
  // preguntes. El asistente está a un toque.
  int _currentIndex = 0;

  SugerenciasController? _sugerencias;
  YoController? _yo;
  String? _tokenDeControladores;

  @override
  void initState() {
    super.initState();
    widget.authController.addListener(_onAuthChanged);
    _asegurarControladores();
  }

  @override
  void dispose() {
    widget.authController.removeListener(_onAuthChanged);
    _sugerencias?.dispose();
    _yo?.dispose();
    super.dispose();
  }

  void _onAuthChanged() {
    _asegurarControladores();
    setState(() {});
  }

  /// Los controladores viven mientras dure la sesión: al cambiar de
  /// usuario se reconstruyen para no mezclar datos de dos cuentas.
  void _asegurarControladores() {
    final token = widget.authController.token;
    if (token == _tokenDeControladores) return;
    _sugerencias?.dispose();
    _yo?.dispose();
    _tokenDeControladores = token;
    if (token == null) {
      _sugerencias = null;
      _yo = null;
      _currentIndex = 0;
      return;
    }
    String tokenActual() => widget.authController.token ?? token;
    _sugerencias = SugerenciasController(apiClient: widget.apiClient, tokenProvider: tokenActual);
    _yo = YoController(
      apiClient: widget.apiClient,
      tokenProvider: tokenActual,
      onUnauthorized: widget.authController.logout,
    );
    // Cargar el conteo de pendientes desde el arranque para el badge.
    _sugerencias!.cargar();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.authController.token == null || _sugerencias == null || _yo == null) {
      return LoginScreen(authController: widget.authController);
    }

    final screens = [
      SugerenciasScreen(controller: _sugerencias!, authController: widget.authController),
      ChatScreen(apiClient: widget.apiClient, authController: widget.authController),
      YoScreen(controller: _yo!, authController: widget.authController),
    ];

    return Scaffold(
      body: IndexedStack(index: _currentIndex, children: screens),
      bottomNavigationBar: ListenableBuilder(
        listenable: _sugerencias!,
        builder: (context, _) {
          final pendientes = _sugerencias!.pendientesCount;
          return NavigationBar(
            selectedIndex: _currentIndex,
            onDestinationSelected: (i) {
              setState(() => _currentIndex = i);
              // Recargar al entrar: Yo pudo haber cambiado el saldo, y el
              // backend regenera sugerencias en cada GET.
              if (i == 0) _sugerencias!.cargar();
              if (i == 2 && _yo!.primeraCargaHecha) _yo!.cargarTodo();
            },
            destinations: [
              NavigationDestination(
                icon: Badge.count(
                  count: pendientes,
                  isLabelVisible: pendientes > 0,
                  child: const Icon(Icons.notifications_outlined),
                ),
                selectedIcon: Badge.count(
                  count: pendientes,
                  isLabelVisible: pendientes > 0,
                  child: const Icon(Icons.notifications),
                ),
                label: 'Sugerencias',
              ),
              const NavigationDestination(
                icon: Icon(Icons.chat_bubble_outline),
                selectedIcon: Icon(Icons.chat_bubble),
                label: 'Asistente',
              ),
              const NavigationDestination(
                icon: Icon(Icons.person_outline),
                selectedIcon: Icon(Icons.person),
                label: 'Yo',
              ),
            ],
          );
        },
      ),
    );
  }
}
