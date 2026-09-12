// flutter_app/lib/main.dart
import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'auth/auth_controller.dart';
import 'auth/auth_repository.dart';
import 'config.dart';
import 'shell/app_shell.dart';

void main() {
  runApp(const MeAlcanzaApp());
}

class MeAlcanzaApp extends StatefulWidget {
  const MeAlcanzaApp({super.key});

  @override
  State<MeAlcanzaApp> createState() => _MeAlcanzaAppState();
}

class _MeAlcanzaAppState extends State<MeAlcanzaApp> {
  late final ApiClient _apiClient = ApiClient(apiBaseUrl);
  late final AuthController _authController = AuthController(
    apiClient: _apiClient,
    authRepository: AuthRepository(),
  );

  @override
  void initState() {
    super.initState();
    _authController.restoreSession();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Me Alcanza',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFEC0029),
          primary: const Color(0xFFEC0029),
          onPrimary: Colors.white,
          secondary: const Color(0xFF6A6867),
          onSecondary: Colors.white,
          // Mismo tono que PALETTE.brand.tertiary en
          // frontend/src/constants/colors.js — ahí es el color real de
          // la burbuja del usuario (--color-message-user), distinto del
          // rojo de marca.
          tertiary: const Color(0xFF5B6570),
          onTertiary: Colors.white,
          surface: Colors.white,
          onSurface: const Color(0xFF1F1F1F),
          // --a2ui-color-border en frontend/src/styles/index.css.
          outline: const Color(0xFFC7C9C9),
          error: const Color(0xFFC5221F),
        ),
        scaffoldBackgroundColor: const Color(0xFFF5F5F5),
        appBarTheme: const AppBarTheme(
          backgroundColor: Color(0xFFEC0029),
          foregroundColor: Colors.white,
        ),
        inputDecorationTheme: InputDecorationTheme(
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(6),
            borderSide: const BorderSide(color: Color(0xFFC7C9C9)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(6),
            borderSide: const BorderSide(color: Color(0xFFC7C9C9)),
          ),
          filled: true,
          fillColor: Colors.white,
        ),
      ),
      home: ListenableBuilder(
        listenable: _authController,
        builder: (context, _) => AppShell(
          apiClient: _apiClient,
          authController: _authController,
        ),
      ),
    );
  }
}
