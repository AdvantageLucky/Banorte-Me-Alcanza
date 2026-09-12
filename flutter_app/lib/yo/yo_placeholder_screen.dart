// flutter_app/lib/yo/yo_placeholder_screen.dart
import 'package:flutter/material.dart';

class YoPlaceholderScreen extends StatelessWidget {
  const YoPlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Yo')),
      body: const Center(child: Text('Próximamente')),
    );
  }
}
