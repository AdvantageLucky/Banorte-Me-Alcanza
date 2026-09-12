// flutter_app/lib/auth/auth_controller.dart
import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import 'auth_repository.dart';

class AuthController extends ChangeNotifier {
  AuthController({
    required ApiClient apiClient,
    required AuthRepository authRepository,
  })  : _apiClient = apiClient,
        _authRepository = authRepository;

  final ApiClient _apiClient;
  final AuthRepository _authRepository;

  String? _token;
  String? get token => _token;

  Future<void> restoreSession() async {
    _token = await _authRepository.readToken();
    notifyListeners();
  }

  Future<void> login(String username, String password) async {
    final newToken = await _apiClient.login(username, password);
    await _authRepository.writeToken(newToken);
    _token = newToken;
    notifyListeners();
  }

  void logout() {
    _authRepository.clearToken();
    _token = null;
    notifyListeners();
  }
}
