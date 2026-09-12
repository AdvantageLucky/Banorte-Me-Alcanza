import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:me_alcanza/auth/auth_repository.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('AuthRepository', () {
    test('returns null when nothing is stored', () async {
      final repo = AuthRepository();
      expect(await repo.readToken(), isNull);
    });

    test('round-trips a token through write/read', () async {
      final repo = AuthRepository();
      await repo.writeToken('jwt-abc');
      expect(await repo.readToken(), 'jwt-abc');
    });

    test('clears a stored token', () async {
      final repo = AuthRepository();
      await repo.writeToken('jwt-abc');
      await repo.clearToken();
      expect(await repo.readToken(), isNull);
    });
  });
}
