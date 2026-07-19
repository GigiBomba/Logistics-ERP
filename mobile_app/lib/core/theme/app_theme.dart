import 'package:flutter/material.dart';

import 'app_colors.dart';
import 'app_spacing.dart';
import 'app_typography.dart';

/// Full Material 3 theme definitions for Operion Mobile.
class AppTheme {
  AppTheme._();

  // ──────────────────────────────────────────────
  // Shared component themes
  // ──────────────────────────────────────────────

  static const InputDecorationTheme _inputDecoration = InputDecorationTheme(
    filled: true,
    contentPadding: EdgeInsets.symmetric(
      horizontal: AppSpacing.lg,
      vertical: AppSpacing.md,
    ),
    border: OutlineInputBorder(
      borderRadius: AppRadius.lgAll,
      borderSide: BorderSide.none,
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: AppRadius.lgAll,
      borderSide: BorderSide.none,
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: AppRadius.lgAll,
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: AppRadius.lgAll,
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: AppRadius.lgAll,
    ),
  );

  static const CardThemeData _cardTheme = CardThemeData(
    elevation: 0,
    margin: EdgeInsets.zero,
    shape: RoundedRectangleBorder(
      borderRadius: AppRadius.lgAll,
    ),
    clipBehavior: Clip.antiAlias,
  );

  static const AppBarTheme _appBarTheme = AppBarTheme(
    centerTitle: true,
    elevation: 0,
    scrolledUnderElevation: 1,
  );

  static const BottomNavigationBarThemeData _bottomNavTheme =
      BottomNavigationBarThemeData(
    type: BottomNavigationBarType.fixed,
    selectedLabelStyle: TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
    unselectedLabelStyle: TextStyle(fontSize: 12, fontWeight: FontWeight.w400),
  );

  static const ChipThemeData _chipTheme = ChipThemeData(
    padding: EdgeInsets.symmetric(
      horizontal: AppSpacing.sm,
      vertical: AppSpacing.xs,
    ),
    labelStyle: TextStyle(fontSize: 11, fontWeight: FontWeight.w500),
    shape: RoundedRectangleBorder(
      borderRadius: AppRadius.pillAll,
    ),
  );

  static const ElevatedButtonThemeData _elevatedButtonTheme =
      ElevatedButtonThemeData(
    style: ButtonStyle(
      elevation: WidgetStatePropertyAll(0),
      padding: WidgetStatePropertyAll(
        EdgeInsets.symmetric(
          horizontal: AppSpacing.xl,
          vertical: AppSpacing.md,
        ),
      ),
      shape: WidgetStatePropertyAll(
        RoundedRectangleBorder(
          borderRadius: AppRadius.lgAll,
        ),
      ),
      textStyle: WidgetStatePropertyAll(
        TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
      minimumSize: WidgetStatePropertyAll(const Size.fromHeight(48)),
    ),
  );

  // ──────────────────────────────────────────────
  // Light theme
  // ──────────────────────────────────────────────

  static ThemeData get light {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorSchemeSeed: AppColors.accent,
      scaffoldBackgroundColor: AppColors.lightBackground,
      textTheme: AppTypography.lightTextTheme,
      primaryTextTheme: AppTypography.lightTextTheme,
      cardTheme: _cardTheme.copyWith(
        color: AppColors.lightSurface,
        surfaceTintColor: AppColors.lightSurface,
      ),
      inputDecorationTheme: _inputDecoration.copyWith(
        fillColor: AppColors.lightElevated,
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadius.lgAll,
          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
        ),
      ),
      elevatedButtonTheme: _elevatedButtonTheme,
      appBarTheme: _appBarTheme.copyWith(
        backgroundColor: AppColors.lightBackground,
        foregroundColor: AppColors.textPrimaryLight,
      ),
      bottomNavigationBarTheme: _bottomNavTheme.copyWith(
        backgroundColor: AppColors.lightSurface,
        selectedItemColor: AppColors.accent,
        unselectedItemColor: AppColors.textSecondaryLight,
      ),
      chipTheme: _chipTheme.copyWith(
        backgroundColor: AppColors.lightElevated,
        labelStyle: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: AppColors.textPrimaryLight,
        ),
      ),
    );
  }

  // ──────────────────────────────────────────────
  // Dark theme
  // ──────────────────────────────────────────────

  static ThemeData get dark {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorSchemeSeed: AppColors.accent,
      scaffoldBackgroundColor: AppColors.darkBackground,
      textTheme: AppTypography.darkTextTheme,
      primaryTextTheme: AppTypography.darkTextTheme,
      cardTheme: _cardTheme.copyWith(
        color: AppColors.darkSurface,
        surfaceTintColor: AppColors.darkSurface,
      ),
      inputDecorationTheme: _inputDecoration.copyWith(
        fillColor: AppColors.darkOverlay,
        focusedBorder: OutlineInputBorder(
          borderRadius: AppRadius.lgAll,
          borderSide: const BorderSide(color: AppColors.accent, width: 1.5),
        ),
      ),
      elevatedButtonTheme: _elevatedButtonTheme,
      appBarTheme: _appBarTheme.copyWith(
        backgroundColor: AppColors.darkBackground,
        foregroundColor: AppColors.textPrimaryDark,
      ),
      bottomNavigationBarTheme: _bottomNavTheme.copyWith(
        backgroundColor: AppColors.darkSurface,
        selectedItemColor: AppColors.accent,
        unselectedItemColor: AppColors.textSecondaryDark,
      ),
      chipTheme: _chipTheme.copyWith(
        backgroundColor: AppColors.darkOverlay,
        labelStyle: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w500,
          color: AppColors.textPrimaryDark,
        ),
      ),
    );
  }
}
