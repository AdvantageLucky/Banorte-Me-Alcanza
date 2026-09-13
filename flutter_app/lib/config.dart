// flutter_app/lib/config.dart

// El emulador Android usa 10.0.2.2 para referirse a localhost de la
// máquina host — NUNCA localhost directo (eso apuntaría al propio
// dispositivo virtual). Si se prueba en un celular físico en la misma
// red Wi-Fi que la laptop, cambiar esto a la IP de red local de la
// laptop (ej. 192.168.1.50) — ver flutter_app/README.md.
const String apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'https://homelab.tail8dc7f1.ts.net',
);
