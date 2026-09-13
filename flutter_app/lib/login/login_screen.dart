// flutter_app/lib/login/login_screen.dart
import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../auth/auth_controller.dart';
import '../theme/app_theme.dart';
import '../theme/tokens.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.authController});

  final AuthController authController;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  String? _error;
  bool _submitting = false;

  Future<void> _handleSubmit() async {
    if (_submitting) return;
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      await widget.authController.login(
        _usernameController.text.trim(),
        _passwordController.text,
      );
    } on ApiException catch (err) {
      setState(() => _error = err.statusCode == 401
          ? 'Usuario o contraseña incorrectos.'
          : (err.detail ?? 'El servidor respondió con un error.'));
    } catch (_) {
      setState(() => _error = 'No se pudo contactar el servidor. Revisa la conexión.');
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final texto = Theme.of(context).textTheme;
    return Scaffold(
      backgroundColor: BrandColors.rojo,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) => SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(minHeight: constraints.maxHeight),
              child: IntrinsicHeight(
                child: Column(
                children: [
                  // Bloque de marca: la pregunta del producto, en la voz de la marca.
                  Padding(
                    padding: const EdgeInsets.fromLTRB(Space.l, Space.xxl, Space.l, Space.xl),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Banorte', style: DisplayText.marca),
                        const SizedBox(height: Space.l),
                        Text(
                          '¿Me alcanza?',
                          style: DisplayText.saldo.copyWith(color: Colors.white, fontSize: 40),
                        ),
                        const SizedBox(height: Space.s),
                        Text(
                          'Pregunta, mira el veredicto y actúa desde la misma pantalla.',
                          style: texto.bodyLarge?.copyWith(color: const Color(0xFFFFD6DE)),
                        ),
                      ],
                    ),
                  ),
                  const Spacer(),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.fromLTRB(Space.l, Space.xl, Space.l, Space.xl),
                    decoration: const BoxDecoration(
                      color: BrandColors.superficie,
                      borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.sheet)),
                    ),
                    child: AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text('Entra a tu cuenta', style: DisplayText.seccion.copyWith(fontSize: 20)),
                          const SizedBox(height: Space.l),
                          TextField(
                            controller: _usernameController,
                            autofillHints: const [AutofillHints.username],
                            textInputAction: TextInputAction.next,
                            autocorrect: false,
                            decoration: const InputDecoration(labelText: 'Usuario'),
                          ),
                          const SizedBox(height: Space.m),
                          TextField(
                            controller: _passwordController,
                            autofillHints: const [AutofillHints.password],
                            textInputAction: TextInputAction.done,
                            obscureText: true,
                            decoration: const InputDecoration(labelText: 'Contraseña'),
                            onSubmitted: (_) => _handleSubmit(),
                          ),
                          if (_error != null) ...[
                            const SizedBox(height: Space.m),
                            Text(_error!, style: const TextStyle(color: BrandColors.error)),
                          ],
                          const SizedBox(height: Space.l),
                          FilledButton(
                            onPressed: _submitting ? null : _handleSubmit,
                            child: Text(_submitting ? 'Entrando…' : 'Entrar'),
                          ),
                          const SizedBox(height: Space.m),
                          Text(
                            'Cuentas de demostración: ana / pass123, luis / pass456',
                            style: texto.bodySmall,
                            textAlign: TextAlign.center,
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
