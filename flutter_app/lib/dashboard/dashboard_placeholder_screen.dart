// flutter_app/lib/dashboard/dashboard_placeholder_screen.dart
import 'package:flutter/material.dart';

class DashboardPlaceholderScreen extends StatelessWidget {
  const DashboardPlaceholderScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: const Center(child: Text('Próximamente')),
    );
  }
}
