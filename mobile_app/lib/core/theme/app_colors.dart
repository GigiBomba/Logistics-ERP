import 'package:flutter/material.dart';

/// Central color palette for the Operion Mobile app.
/// Mirrors the desktop design tokens from [design_tokens.py].
class AppColors {
  AppColors._();

  // ──────────────────────────────────────────────
  // Brand / accent
  // ──────────────────────────────────────────────
  static const Color accent = Color(0xFF6366F1); // Indigo-500
  static const Color accentHover = Color(0xFF5254CC);
  static const Color accentSubtle = Color(0x296366F1);

  // ──────────────────────────────────────────────
  // Dark theme backgrounds
  // ──────────────────────────────────────────────
  static const Color darkBackground = Color(0xFF0C0C0E);
  static const Color darkSurface = Color(0xFF141416);
  static const Color darkOverlay = Color(0xFF1C1C1F);

  // ──────────────────────────────────────────────
  // Light theme backgrounds
  // ──────────────────────────────────────────────
  static const Color lightBackground = Color(0xFFFAFAFA);
  static const Color lightSurface = Color(0xFFFFFFFF);
  static const Color lightElevated = Color(0xFFF5F5F5);

  // ──────────────────────────────────────────────
  // Text (light mode)
  // ──────────────────────────────────────────────
  static const Color textPrimaryLight = Color(0xFF1A1A1A);
  static const Color textSecondaryLight = Color(0xFF6B7280);

  // ──────────────────────────────────────────────
  // Text (dark mode)
  // ──────────────────────────────────────────────
  static const Color textPrimaryDark = Color(0xFFF0F0F3);
  static const Color textSecondaryDark = Color(0xFF8E8EA0);

  // ──────────────────────────────────────────────
  // Semantic / helper
  // ──────────────────────────────────────────────
  static const Color success = Color(0xFF10B981);
  static const Color successText = Color(0xFF10B981);
  static const Color successSubtle = Color(0x2910B981);

  static const Color warning = Color(0xFFF59E0B);
  static const Color warningText = Color(0xFFF59E0B);
  static const Color warningSubtle = Color(0x29F59E0B);

  static const Color error = Color(0xFFEF4444);
  static const Color errorText = Color(0xFFEF4444);
  static const Color errorSubtle = Color(0x29EF4444);

  static const Color info = Color(0xFF3B82F6);
  static const Color infoText = Color(0xFF3B82F6);
  static const Color infoSubtle = Color(0x293B82F6);

  static const Color neutralText = Color(0xFF8E8EA0);
  static const Color neutralSubtle = Color(0x298E8EA0);

  static const Color tertiary = Color(0xFF8E8EA0);

  // ──────────────────────────────────────────────
  // Aliases used by various features
  // ──────────────────────────────────────────────
  static const Color primary = accent;
  static const Color onPrimary = Color(0xFFFFFFFF);
  static const Color surface = lightSurface;
  static const Color surfaceVariant = Color(0xFFF0F0F3);
  static const Color textPrimary = textPrimaryLight;
  static const Color textSecondary = textSecondaryLight;
  static const Color textTertiary = Color(0xFF9CA3AF);
  static const Color divider = Color(0xFFE5E7EB);

  // ──────────────────────────────────────────────
  // Chart colors
  // ──────────────────────────────────────────────
  static const List<Color> chartColors = [
    Color(0xFF6366F1), // indigo
    Color(0xFF10B981), // green
    Color(0xFFF59E0B), // amber
    Color(0xFF3B82F6), // blue
    Color(0xFFEC4899), // pink
  ];
}
