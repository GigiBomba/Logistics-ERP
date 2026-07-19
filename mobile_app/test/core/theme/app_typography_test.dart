import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/theme/app_colors.dart';
import 'package:operion_mobile/core/theme/app_typography.dart';

void main() {
  // Google Fonts interTextTheme() requires an initialized binding, so we use
  // testWidgets (which sets up TestWidgetsFlutterBinding) even though these
  // are essentially unit tests for data objects.

  // ==========================================================================
  // Light text theme
  // ==========================================================================
  group('lightTextTheme', () {
    testWidgets('returns a TextTheme', (tester) async {
      expect(AppTypography.lightTextTheme, isA<TextTheme>());
    });

    testWidgets('body color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.bodyLarge?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('display color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.displayLarge?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('headlineLarge color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.headlineLarge?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('bodyMedium color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.bodyMedium?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('bodySmall color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.bodySmall?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('titleLarge color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.titleLarge?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('titleMedium color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.titleMedium?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('labelSmall color is textPrimaryLight', (tester) async {
      expect(
        AppTypography.lightTextTheme.labelSmall?.color,
        AppColors.textPrimaryLight,
      );
    });

    testWidgets('titleMedium color is applied', (tester) async {
      // Google Fonts interTextTheme does not set explicit fontWeight,
      // but the color is applied via .apply()
      expect(
        AppTypography.lightTextTheme.titleMedium?.color,
        isNotNull,
      );
    });

    testWidgets('labelSmall color is applied', (tester) async {
      expect(
        AppTypography.lightTextTheme.labelSmall?.color,
        isNotNull,
      );
    });

    testWidgets('all text styles have Inter font-family', (tester) async {
      final theme = AppTypography.lightTextTheme;
      final styles = [
        theme.displayLarge,
        theme.displayMedium,
        theme.displaySmall,
        theme.headlineLarge,
        theme.headlineMedium,
        theme.headlineSmall,
        theme.titleLarge,
        theme.titleMedium,
        theme.titleSmall,
        theme.bodyLarge,
        theme.bodyMedium,
        theme.bodySmall,
        theme.labelLarge,
        theme.labelMedium,
        theme.labelSmall,
      ];
      for (final style in styles) {
        if (style != null) {
          // Google Fonts appends the weight variant (e.g. "Inter_regular")
          expect(style.fontFamily, contains('Inter'));
        }
      }
    });
  });

  // ==========================================================================
  // Dark text theme
  // ==========================================================================
  group('darkTextTheme', () {
    testWidgets('returns a TextTheme', (tester) async {
      expect(AppTypography.darkTextTheme, isA<TextTheme>());
    });

    testWidgets('body color is textPrimaryDark', (tester) async {
      expect(
        AppTypography.darkTextTheme.bodyLarge?.color,
        AppColors.textPrimaryDark,
      );
    });

    testWidgets('display color is textPrimaryDark', (tester) async {
      expect(
        AppTypography.darkTextTheme.displayLarge?.color,
        AppColors.textPrimaryDark,
      );
    });

    testWidgets('labelSmall color is textPrimaryDark', (tester) async {
      expect(
        AppTypography.darkTextTheme.labelSmall?.color,
        AppColors.textPrimaryDark,
      );
    });

    testWidgets('dark styles have Inter font-family', (tester) async {
      final theme = AppTypography.darkTextTheme;
      expect(theme.bodyLarge?.fontFamily, contains('Inter'));
      expect(theme.titleMedium?.fontFamily, contains('Inter'));
      expect(theme.labelSmall?.fontFamily, contains('Inter'));
    });

    testWidgets('dark theme uses dark text colors throughout', (tester) async {
      final theme = AppTypography.darkTextTheme;
      expect(theme.bodyLarge?.color, AppColors.textPrimaryDark);
      expect(theme.bodyMedium?.color, AppColors.textPrimaryDark);
      expect(theme.bodySmall?.color, AppColors.textPrimaryDark);
      expect(theme.titleLarge?.color, AppColors.textPrimaryDark);
      expect(theme.titleMedium?.color, AppColors.textPrimaryDark);
      expect(theme.titleSmall?.color, AppColors.textPrimaryDark);
    });
  });

  // ==========================================================================
  // Light vs dark theme comparison
  // ==========================================================================
  group('Light vs dark theme', () {
    testWidgets('light and dark use different primary colors', (tester) async {
      expect(
        AppTypography.lightTextTheme.bodyLarge?.color,
        isNot(AppTypography.darkTextTheme.bodyLarge?.color),
      );
    });
  });

  // ==========================================================================
  // Convenience aliases
  // ==========================================================================
  group('Convenience aliases', () {
    testWidgets('bodyLarge maps to lightTextTheme.bodyLarge', (tester) async {
      expect(AppTypography.bodyLarge, AppTypography.lightTextTheme.bodyLarge);
    });

    testWidgets('bodyMedium maps to lightTextTheme.bodyMedium', (tester) async {
      expect(AppTypography.bodyMedium, AppTypography.lightTextTheme.bodyMedium);
    });

    testWidgets('bodySmall maps to lightTextTheme.bodySmall', (tester) async {
      expect(AppTypography.bodySmall, AppTypography.lightTextTheme.bodySmall);
    });

    testWidgets('titleMedium maps to lightTextTheme.titleMedium',
        (tester) async {
      expect(
        AppTypography.titleMedium,
        AppTypography.lightTextTheme.titleMedium,
      );
    });

    testWidgets('labelSmall maps to lightTextTheme.labelSmall',
        (tester) async {
      expect(AppTypography.labelSmall, AppTypography.lightTextTheme.labelSmall);
    });

    testWidgets('bodyLarge has a non-null TextStyle', (tester) async {
      expect(AppTypography.bodyLarge, isNotNull);
    });

    testWidgets('bodyMedium has a non-null TextStyle', (tester) async {
      expect(AppTypography.bodyMedium, isNotNull);
    });

    testWidgets('bodySmall has a non-null TextStyle', (tester) async {
      expect(AppTypography.bodySmall, isNotNull);
    });

    testWidgets('titleMedium has a non-null TextStyle', (tester) async {
      expect(AppTypography.titleMedium, isNotNull);
    });

    testWidgets('labelSmall has a non-null TextStyle', (tester) async {
      expect(AppTypography.labelSmall, isNotNull);
    });

    testWidgets('bodyLarge has Inter font-family', (tester) async {
      expect(AppTypography.bodyLarge?.fontFamily, contains('Inter'));
    });

    testWidgets('bodyLarge color is textPrimaryLight', (tester) async {
      expect(AppTypography.bodyLarge?.color, AppColors.textPrimaryLight);
    });
  });
}
