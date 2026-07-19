import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'app_colors.dart';

/// Typography system for Operion Mobile.
///
/// Builds a Material [TextTheme] using the Inter font family with sizes
/// derived from the desktop design tokens.
class AppTypography {
  AppTypography._();

  /// Text theme intended for light backgrounds with dark text.
  static TextTheme get lightTextTheme {
    return GoogleFonts.interTextTheme().apply(
      bodyColor: AppColors.textPrimaryLight,
      displayColor: AppColors.textPrimaryLight,
      decorationColor: AppColors.textPrimaryLight,
    );
  }

  /// Text theme intended for dark backgrounds with light text.
  static TextTheme get darkTextTheme {
    return GoogleFonts.interTextTheme().apply(
      bodyColor: AppColors.textPrimaryDark,
      displayColor: AppColors.textPrimaryDark,
      decorationColor: AppColors.textPrimaryDark,
    );
  }

  // ── Convenience aliases (light theme defaults) ───────────────────

  static TextStyle get bodyLarge => lightTextTheme.bodyLarge!;
  static TextStyle get bodyMedium => lightTextTheme.bodyMedium!;
  static TextStyle get bodySmall => lightTextTheme.bodySmall!;
  static TextStyle get titleMedium => lightTextTheme.titleMedium!;
  static TextStyle get labelSmall => lightTextTheme.labelSmall!;
}
