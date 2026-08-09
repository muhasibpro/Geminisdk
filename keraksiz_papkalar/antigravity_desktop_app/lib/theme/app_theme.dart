import 'package:flutter/material.dart';

class AppTheme {
  static const Color background = Color(0xFF0D0F18);
  static const Color sidebarBg = Color(0xFF141724);
  static const Color cardBg = Color(0xFF1C2033);
  static const Color glassBorder = Color(0xFF2B324D);
  
  static const Color primaryNeon = Color(0xFF6C5CE7);
  static const Color accentCyan = Color(0xFF00CEC9);
  static const Color accentGreen = Color(0xFF00B894);
  static const Color accentPink = Color(0xFFFD79A8);
  static const Color accentYellow = Color(0xFFFDCB6E);
  
  static const Color textPrimary = Color(0xFFF1F2F6);
  static const Color textSecondary = Color(0xFFA4B0BE);
  static const Color textMuted = Color(0xFF747D8C);

  static ThemeData get darkTheme {
    return ThemeData.dark().copyWith(
      scaffoldBackgroundColor: background,
      primaryColor: primaryNeon,
      colorScheme: const ColorScheme.dark(
        primary: primaryNeon,
        secondary: accentCyan,
        surface: cardBg,
      ),
      cardTheme: CardThemeData(
        color: cardBg,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: const BorderSide(color: glassBorder, width: 1),
        ),
      ),
      dividerTheme: const DividerThemeData(
        color: glassBorder,
        thickness: 1,
      ),
    );
  }
}
