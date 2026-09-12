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
      title: 'me-alcanza',
      theme: ThemeData(useMaterial3: true),
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
