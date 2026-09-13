// flutter_app/lib/theme/tokens.dart
//
// Tokens de la marca (docs/design-system.md). Un solo lugar para los
// colores y las medidas: ninguna pantalla debe inventar un hex.
import 'package:flutter/material.dart';

abstract final class BrandColors {
  /// Rojo Banorte. Solo como fondo de acciones primarias y acentos
  /// puntuales (el marcador "hoy" del riel), nunca como texto largo.
  static const Color rojo = Color(0xFFEC0029);

  /// Tinta principal para texto sobre fondo claro.
  static const Color tinta = Color(0xFF1F1F1F);

  /// Gris intenso: texto secundario, iconografía neutra.
  static const Color gris = Color(0xFF6A6867);

  /// Gris plata: hairlines, bordes, estados deshabilitados.
  static const Color plata = Color(0xFFC7C9C9);

  /// Fondo técnico de la app (no blanco puro).
  static const Color fondo = Color(0xFFF5F5F5);

  /// Superficies que "flotan": tarjetas, inputs, sheets.
  static const Color superficie = Color(0xFFFFFFFF);

  /// Verde semántico de éxito (no es de marca; convención universal).
  static const Color exito = Color(0xFF1E8E3E);

  /// Rojo de error, deliberadamente distinto del rojo de marca.
  static const Color error = Color(0xFFC5221F);

  /// Acento amarillo opcional para estados de "atención".
  static const Color atencion = Color(0xFFF8D44C);

  /// Burbuja del usuario en el chat (mismo tono que React).
  static const Color burbujaUsuario = Color(0xFF5B6570);
}

abstract final class Space {
  static const double xs = 4;
  static const double s = 8;
  static const double m = 16;
  static const double l = 24;
  static const double xl = 32;
  static const double xxl = 48;
}

abstract final class Radii {
  static const double control = 10;
  static const double card = 12;
  static const double sheet = 20;
}

/// Familia de display: la única voz tipográfica de marca que tenemos.
/// Se usa en cifras grandes y títulos de sección; el cuerpo va en la
/// sans del sistema.
const String displayFontFamily = 'BankGothic';
