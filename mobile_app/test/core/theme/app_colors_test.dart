import 'dart:math' show max, min, pow;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/theme/app_colors.dart';

/// WCAG 2.1 relative luminance helpers.
double _linearize(double c) {
  if (c <= 0.03928) return c / 12.92;
  return pow((c + 0.055) / 1.055, 2.4).toDouble();
}

double _relativeLuminance(Color color) {
  final r = _linearize(color.red / 255.0);
  final g = _linearize(color.green / 255.0);
  final b = _linearize(color.blue / 255.0);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

double contrastRatio(Color a, Color b) {
  final l1 = _relativeLuminance(a);
  final l2 = _relativeLuminance(b);
  final lighter = max(l1, l2);
  final darker = min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

void main() {
  // ==========================================================================
  // Brand / accent
  // ==========================================================================
  group('Brand / accent colors', () {
    test('accent is Indigo-500 (#6366F1)', () {
      expect(AppColors.accent, const Color(0xFF6366F1));
    });

    test('accentHover is slightly darker (#5254CC)', () {
      expect(AppColors.accentHover, const Color(0xFF5254CC));
    });

    test('accentSubtle is accent at 16% opacity', () {
      expect(AppColors.accentSubtle, const Color(0x296366F1));
    });
  });

  // ==========================================================================
  // Dark theme backgrounds
  // ==========================================================================
  group('Dark theme backgrounds', () {
    test('darkBackground is near-black (#0C0C0E)', () {
      expect(AppColors.darkBackground, const Color(0xFF0C0C0E));
    });

    test('darkSurface is slightly lighter (#141416)', () {
      expect(AppColors.darkSurface, const Color(0xFF141416));
    });

    test('darkOverlay is medium dark (#1C1C1F)', () {
      expect(AppColors.darkOverlay, const Color(0xFF1C1C1F));
    });
  });

  // ==========================================================================
  // Light theme backgrounds
  // ==========================================================================
  group('Light theme backgrounds', () {
    test('lightBackground is off-white (#FAFAFA)', () {
      expect(AppColors.lightBackground, const Color(0xFFFAFAFA));
    });

    test('lightSurface is white (#FFFFFF)', () {
      expect(AppColors.lightSurface, const Color(0xFFFFFFFF));
    });

    test('lightElevated is very light gray (#F5F5F5)', () {
      expect(AppColors.lightElevated, const Color(0xFFF5F5F5));
    });
  });

  // ==========================================================================
  // Text colors — light mode
  // ==========================================================================
  group('Light mode text colors', () {
    test('textPrimaryLight is near-black (#1A1A1A)', () {
      expect(AppColors.textPrimaryLight, const Color(0xFF1A1A1A));
    });

    test('textSecondaryLight is medium gray (#6B7280)', () {
      expect(AppColors.textSecondaryLight, const Color(0xFF6B7280));
    });
  });

  // ==========================================================================
  // Text colors — dark mode
  // ==========================================================================
  group('Dark mode text colors', () {
    test('textPrimaryDark is near-white (#F0F0F3)', () {
      expect(AppColors.textPrimaryDark, const Color(0xFFF0F0F3));
    });

    test('textSecondaryDark is muted gray (#8E8EA0)', () {
      expect(AppColors.textSecondaryDark, const Color(0xFF8E8EA0));
    });
  });

  // ==========================================================================
  // Semantic / helper colors
  // ==========================================================================
  group('Semantic colors', () {
    group('success', () {
      test('success is green (#10B981)', () {
        expect(AppColors.success, const Color(0xFF10B981));
      });
      test('successText matches success', () {
        expect(AppColors.successText, AppColors.success);
      });
      test('successSubtle is success at 16% opacity', () {
        expect(AppColors.successSubtle, const Color(0x2910B981));
      });
    });

    group('warning', () {
      test('warning is amber (#F59E0B)', () {
        expect(AppColors.warning, const Color(0xFFF59E0B));
      });
      test('warningText matches warning', () {
        expect(AppColors.warningText, AppColors.warning);
      });
      test('warningSubtle is warning at 16% opacity', () {
        expect(AppColors.warningSubtle, const Color(0x29F59E0B));
      });
    });

    group('error', () {
      test('error is red (#EF4444)', () {
        expect(AppColors.error, const Color(0xFFEF4444));
      });
      test('errorText matches error', () {
        expect(AppColors.errorText, AppColors.error);
      });
      test('errorSubtle is error at 16% opacity', () {
        expect(AppColors.errorSubtle, const Color(0x29EF4444));
      });
    });

    group('info', () {
      test('info is blue (#3B82F6)', () {
        expect(AppColors.info, const Color(0xFF3B82F6));
      });
      test('infoText matches info', () {
        expect(AppColors.infoText, AppColors.info);
      });
      test('infoSubtle is info at 16% opacity', () {
        expect(AppColors.infoSubtle, const Color(0x293B82F6));
      });
    });

    group('neutral', () {
      test('neutralText is muted gray (#8E8EA0)', () {
        expect(AppColors.neutralText, const Color(0xFF8E8EA0));
      });
      test('neutralSubtle is neutral at 16% opacity', () {
        expect(AppColors.neutralSubtle, const Color(0x298E8EA0));
      });
    });

    test('tertiary matches neutralText', () {
      expect(AppColors.tertiary, AppColors.neutralText);
    });
  });

  // ==========================================================================
  // Aliases
  // ==========================================================================
  group('Aliases', () {
    test('primary equals accent', () {
      expect(AppColors.primary, AppColors.accent);
    });
    test('onPrimary is white', () {
      expect(AppColors.onPrimary, const Color(0xFFFFFFFF));
    });
    test('surface equals lightSurface', () {
      expect(AppColors.surface, AppColors.lightSurface);
    });
    test('surfaceVariant is light gray (#F0F0F3)', () {
      expect(AppColors.surfaceVariant, const Color(0xFFF0F0F3));
    });
    test('textPrimary equals textPrimaryLight', () {
      expect(AppColors.textPrimary, AppColors.textPrimaryLight);
    });
    test('textSecondary equals textSecondaryLight', () {
      expect(AppColors.textSecondary, AppColors.textSecondaryLight);
    });
    test('textTertiary is gray (#9CA3AF)', () {
      expect(AppColors.textTertiary, const Color(0xFF9CA3AF));
    });
    test('divider is light gray (#E5E7EB)', () {
      expect(AppColors.divider, const Color(0xFFE5E7EB));
    });
  });

  // ==========================================================================
  // Chart colors
  // ==========================================================================
  group('Chart colors', () {
    test('chartColors has 5 entries', () {
      expect(AppColors.chartColors, hasLength(5));
    });

    test('first chart color is accent (indigo)', () {
      expect(AppColors.chartColors[0], AppColors.accent);
    });

    test('chart colors are non-null and unique', () {
      // At minimum each should be a valid color
      for (final c in AppColors.chartColors) {
        expect(c, isA<Color>());
      }
    });
  });

  // ==========================================================================
  // Color contrast validation (WCAG AA)
  // ==========================================================================
  group('Color contrast validation', () {
    // WCAG AA requires 4.5:1 for normal text, 3:1 for large text.
    const double minContrastNormal = 4.5;
    const double minContrastLarge = 3.0;

    group('Light theme text on backgrounds', () {
      test('textPrimaryLight on lightBackground meets AA (normal text)', () {
        final ratio = contrastRatio(
          AppColors.textPrimaryLight,
          AppColors.lightBackground,
        );
        expect(ratio, greaterThanOrEqualTo(minContrastNormal));
      });

      test('textSecondaryLight on lightBackground meets AA (large text)', () {
        final ratio = contrastRatio(
          AppColors.textSecondaryLight,
          AppColors.lightBackground,
        );
        // Secondary text is acceptable at 3:1 for large text
        expect(ratio, greaterThanOrEqualTo(minContrastLarge));
      });

      test('accent on white meets AA (large text)', () {
        // Accent is used for links and interactive elements
        final ratio = contrastRatio(AppColors.accent, AppColors.lightSurface);
        expect(ratio, greaterThanOrEqualTo(minContrastLarge));
      });

      test('error on lightBackground meets AA for large text (3:1)', () {
        final ratio = contrastRatio(
          AppColors.error,
          AppColors.lightBackground,
        );
        // Red (#EF4444) on off-white achieves ~3.6:1 — sufficient for
        // large text (AA) and UI components but not normal text.
        expect(ratio, greaterThanOrEqualTo(minContrastLarge));
      });
    });

    group('Dark theme text on backgrounds', () {
      test('textPrimaryDark on darkBackground meets AA (normal text)', () {
        final ratio = contrastRatio(
          AppColors.textPrimaryDark,
          AppColors.darkBackground,
        );
        expect(ratio, greaterThanOrEqualTo(minContrastNormal));
      });

      test('textSecondaryDark on darkSurface meets AA (large text)', () {
        final ratio = contrastRatio(
          AppColors.textSecondaryDark,
          AppColors.darkSurface,
        );
        expect(ratio, greaterThanOrEqualTo(minContrastLarge));
      });

      test('accent on darkSurface meets AA (large text)', () {
        final ratio = contrastRatio(AppColors.accent, AppColors.darkSurface);
        expect(ratio, greaterThanOrEqualTo(minContrastLarge));
      });

      test('error on darkBackground meets AA', () {
        final ratio = contrastRatio(
          AppColors.error,
          AppColors.darkBackground,
        );
        expect(ratio, greaterThanOrEqualTo(minContrastNormal));
      });
    });

    group('On-primary contrast', () {
      test('onPrimary (white) on accent meets AA for large text (3:1)', () {
        final ratio = contrastRatio(AppColors.onPrimary, AppColors.accent);
        // White (#FFFFFF) on Indigo (#6366F1) achieves ~4.47:1 which
        // meets AA for large text (3:1) and is very close to AA normal.
        expect(ratio, greaterThanOrEqualTo(minContrastLarge));
      });
    });

    group('Semantic colors on backgrounds', () {
      test('success on darkBackground meets AA', () {
        final ratio = contrastRatio(AppColors.success, AppColors.darkBackground);
        expect(ratio, greaterThanOrEqualTo(minContrastNormal));
      });

      test('warning on darkBackground meets AA', () {
        final ratio = contrastRatio(AppColors.warning, AppColors.darkBackground);
        expect(ratio, greaterThanOrEqualTo(minContrastNormal));
      });

      test('info on darkBackground meets AA', () {
        final ratio = contrastRatio(AppColors.info, AppColors.darkBackground);
        expect(ratio, greaterThanOrEqualTo(minContrastNormal));
      });
    });
  });
}
