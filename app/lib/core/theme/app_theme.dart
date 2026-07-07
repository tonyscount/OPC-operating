import 'package:flutter/material.dart';

class AppTheme {
  static const _primaryColor = Color(0xFF00D4FF); // 科技蓝
  static const _surfaceColor = Color(0xFF1A1D23); // 深灰底色
  static const _cardColor = Color(0xFF252830);     // 卡片背景
  static const _textPrimary = Color(0xFFF5F5F7);   // 高亮白
  static const _textSecondary = Color(0xFF9BA1A6); // 次级灰

  static ThemeData get darkTheme => ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: _surfaceColor,
        primaryColor: _primaryColor,
        colorScheme: const ColorScheme.dark(
          primary: _primaryColor,
          secondary: _primaryColor,
          surface: _surfaceColor,
        ),
        appBarTheme: const AppBarTheme(
          backgroundColor: _surfaceColor,
          elevation: 0,
          centerTitle: true,
        ),
        cardTheme: CardThemeData(
          color: _cardColor,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        ),
        bottomNavigationBarTheme: const BottomNavigationBarThemeData(
          backgroundColor: Colors.transparent,
          selectedItemColor: _primaryColor,
          unselectedItemColor: _textSecondary,
          type: BottomNavigationBarType.fixed,
        ),
        textTheme: const TextTheme(
          headlineLarge: TextStyle(color: _textPrimary, fontWeight: FontWeight.bold, fontSize: 28),
          titleLarge: TextStyle(color: _textPrimary, fontWeight: FontWeight.w600, fontSize: 18),
          bodyLarge: TextStyle(color: _textPrimary, fontSize: 16),
          bodyMedium: TextStyle(color: _textSecondary, fontSize: 14),
        ),
      );
}
