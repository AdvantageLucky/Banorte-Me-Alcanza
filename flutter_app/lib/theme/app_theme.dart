// flutter_app/lib/theme/app_theme.dart
import 'package:flutter/material.dart';

import 'tokens.dart';

/// Estilos de display. BankGothic (`displayFontFamily`) queda reservado
/// SOLO para 'marca' (la palabra "Banorte" del AppBar) — igual que en
/// React, donde ese font-face solo se aplica a .app-navbar-brand /
/// .login-navbar-brand y en ningún otro lado (ni saldos, ni títulos de
/// sección, ni el riel de quincena usan una fuente distinta a la del
/// sistema). Antes 'saldo'/'cifra'/'seccion'/'etiquetaRiel' también
/// usaban BankGothic, lo que hacía que la app se viera con fuentes
/// distintas entre sí y distintas a la web.
abstract final class DisplayText {
  static const TextStyle saldo = TextStyle(
    fontWeight: FontWeight.w700,
    fontSize: 44,
    height: 1.0,
    letterSpacing: -0.5,
    color: BrandColors.tinta,
  );

  static const TextStyle cifra = TextStyle(
    fontWeight: FontWeight.w500,
    fontSize: 22,
    height: 1.1,
    color: BrandColors.tinta,
  );

  static const TextStyle seccion = TextStyle(
    fontWeight: FontWeight.w600,
    fontSize: 18,
    height: 1.2,
    color: BrandColors.tinta,
  );

  static const TextStyle marca = TextStyle(
    fontFamily: displayFontFamily,
    fontWeight: FontWeight.w700,
    fontSize: 20,
    letterSpacing: 0.5,
    color: Colors.white,
  );

  static const TextStyle etiquetaRiel = TextStyle(
    fontWeight: FontWeight.w500,
    fontSize: 11,
    height: 1.0,
    color: BrandColors.gris,
  );
}

ThemeData buildAppTheme() {
  const scheme = ColorScheme(
    brightness: Brightness.light,
    primary: BrandColors.rojo,
    onPrimary: Colors.white,
    secondary: BrandColors.gris,
    onSecondary: Colors.white,
    tertiary: BrandColors.burbujaUsuario,
    onTertiary: Colors.white,
    surface: BrandColors.superficie,
    onSurface: BrandColors.tinta,
    onSurfaceVariant: BrandColors.gris,
    outline: BrandColors.plata,
    outlineVariant: Color(0xFFE3E4E4),
    surfaceContainerHighest: Color(0xFFECECEC),
    error: BrandColors.error,
    onError: Colors.white,
  );

  final base = ThemeData(useMaterial3: true, colorScheme: scheme);

  return base.copyWith(
    scaffoldBackgroundColor: BrandColors.fondo,
    appBarTheme: const AppBarTheme(
      backgroundColor: BrandColors.rojo,
      foregroundColor: Colors.white,
      elevation: 0,
      scrolledUnderElevation: 0,
      centerTitle: false,
    ),
    dividerTheme: const DividerThemeData(
      color: BrandColors.plata,
      thickness: 1,
      space: 1,
    ),
    textTheme: base.textTheme.copyWith(
      bodyLarge: base.textTheme.bodyLarge?.copyWith(color: BrandColors.tinta, height: 1.45),
      bodyMedium: base.textTheme.bodyMedium?.copyWith(color: BrandColors.tinta, height: 1.45),
      bodySmall: base.textTheme.bodySmall?.copyWith(color: BrandColors.gris, height: 1.4),
      labelLarge: base.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w600),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: BrandColors.superficie,
      contentPadding: const EdgeInsets.symmetric(horizontal: Space.m, vertical: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Radii.control),
        borderSide: const BorderSide(color: BrandColors.plata),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Radii.control),
        borderSide: const BorderSide(color: BrandColors.plata),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Radii.control),
        borderSide: const BorderSide(color: BrandColors.tinta, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(Radii.control),
        borderSide: const BorderSide(color: BrandColors.error),
      ),
      labelStyle: const TextStyle(color: BrandColors.gris),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: BrandColors.rojo,
        foregroundColor: Colors.white,
        minimumSize: const Size.fromHeight(48),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.control)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: BrandColors.tinta,
        minimumSize: const Size.fromHeight(48),
        side: const BorderSide(color: BrandColors.plata),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(Radii.control)),
        textStyle: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: BrandColors.tinta,
        textStyle: const TextStyle(fontWeight: FontWeight.w600),
      ),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: BrandColors.superficie,
      showDragHandle: true,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.sheet)),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: BrandColors.superficie,
      indicatorColor: const Color(0xFFFCE4E9),
      height: 68,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontSize: 12,
          fontWeight: states.contains(WidgetState.selected) ? FontWeight.w700 : FontWeight.w500,
          color: states.contains(WidgetState.selected) ? BrandColors.rojo : BrandColors.gris,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          color: states.contains(WidgetState.selected) ? BrandColors.rojo : BrandColors.gris,
        ),
      ),
    ),
    snackBarTheme: const SnackBarThemeData(
      backgroundColor: BrandColors.tinta,
      contentTextStyle: TextStyle(color: Colors.white),
      behavior: SnackBarBehavior.floating,
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(color: BrandColors.rojo),
  );
}
