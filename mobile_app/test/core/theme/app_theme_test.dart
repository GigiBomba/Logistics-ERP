import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/theme/app_colors.dart';
import 'package:operion_mobile/core/theme/app_spacing.dart';
import 'package:operion_mobile/core/theme/app_theme.dart';

/// Helper that returns the light theme (lazy so it runs inside testWidgets).
ThemeData get _light => AppTheme.light;
ThemeData get _dark => AppTheme.dark;

void main() {
  // Google Fonts interTextTheme() requires an initialized binding, so we use
  // testWidgets throughout.

  // ==========================================================================
  // Light theme
  // ==========================================================================
  group('AppTheme.light', () {
    testWidgets('returns a non-null ThemeData', (tester) async {
      expect(_light, isA<ThemeData>());
    });

    testWidgets('uses Material 3', (tester) async {
      expect(_light.useMaterial3, isTrue);
    });

    testWidgets('brightness is light', (tester) async {
      expect(_light.brightness, Brightness.light);
    });

    testWidgets('scaffoldBackgroundColor is lightBackground', (tester) async {
      expect(_light.scaffoldBackgroundColor, AppColors.lightBackground);
    });

    testWidgets('textTheme uses Inter font', (tester) async {
      // Google Fonts appends weight variant (e.g. "Inter_regular")
      expect(_light.textTheme.bodyLarge?.fontFamily, contains('Inter'));
    });

    testWidgets('textTheme body color is textPrimaryLight', (tester) async {
      expect(_light.textTheme.bodyLarge?.color, AppColors.textPrimaryLight);
    });
  });

  // ==========================================================================
  // Dark theme
  // ==========================================================================
  group('AppTheme.dark', () {
    testWidgets('returns a non-null ThemeData', (tester) async {
      expect(_dark, isA<ThemeData>());
    });

    testWidgets('uses Material 3', (tester) async {
      expect(_dark.useMaterial3, isTrue);
    });

    testWidgets('brightness is dark', (tester) async {
      expect(_dark.brightness, Brightness.dark);
    });

    testWidgets('scaffoldBackgroundColor is darkBackground', (tester) async {
      expect(_dark.scaffoldBackgroundColor, AppColors.darkBackground);
    });

    testWidgets('textTheme body color is textPrimaryDark', (tester) async {
      expect(_dark.textTheme.bodyLarge?.color, AppColors.textPrimaryDark);
    });
  });

  // ==========================================================================
  // Theme comparison
  // ==========================================================================
  group('Light vs dark theme comparison', () {
    testWidgets('brightness differs', (tester) async {
      expect(_light.brightness, isNot(_dark.brightness));
    });

    testWidgets('scaffoldBackgroundColor differs', (tester) async {
      expect(
        _light.scaffoldBackgroundColor,
        isNot(_dark.scaffoldBackgroundColor),
      );
    });

    testWidgets('text themes use different primary colors', (tester) async {
      expect(
        _light.textTheme.bodyLarge?.color,
        isNot(_dark.textTheme.bodyLarge?.color),
      );
    });

    testWidgets('both use Material 3', (tester) async {
      expect(_light.useMaterial3, isTrue);
      expect(_dark.useMaterial3, isTrue);
    });
  });

  // ==========================================================================
  // Component theme overrides — shared base
  // ==========================================================================
  group('Component theme overrides', () {
    group('InputDecoration', () {
      testWidgets('light theme input decoration has filled: true',
          (tester) async {
        expect(_light.inputDecorationTheme.filled, isTrue);
      });

      testWidgets('light theme input fillColor is lightElevated',
          (tester) async {
        expect(_light.inputDecorationTheme.fillColor, AppColors.lightElevated);
      });

      testWidgets('dark theme input fillColor is darkOverlay',
          (tester) async {
        expect(_dark.inputDecorationTheme.fillColor, AppColors.darkOverlay);
      });

      testWidgets('light theme focused border has accent color',
          (tester) async {
        final focusedBorder = _light.inputDecorationTheme.focusedBorder;
        expect(focusedBorder, isA<OutlineInputBorder>());
        final border = focusedBorder as OutlineInputBorder;
        expect(border.borderSide?.color, AppColors.accent);
        expect(border.borderSide?.width, 1.5);
      });

      testWidgets('dark theme focused border has accent color',
          (tester) async {
        final focusedBorder = _dark.inputDecorationTheme.focusedBorder;
        expect(focusedBorder, isA<OutlineInputBorder>());
        final border = focusedBorder as OutlineInputBorder;
        expect(border.borderSide?.color, AppColors.accent);
      });

      testWidgets('border radius is lg (8)', (tester) async {
        final border = _light.inputDecorationTheme.border;
        expect(border, isA<OutlineInputBorder>());
        expect(
          (border as OutlineInputBorder).borderRadius,
          AppRadius.lgAll,
        );
      });
    });

    group('CardTheme', () {
      testWidgets('light theme card color is lightSurface', (tester) async {
        expect(_light.cardTheme.color, AppColors.lightSurface);
      });

      testWidgets('dark theme card color is darkSurface', (tester) async {
        expect(_dark.cardTheme.color, AppColors.darkSurface);
      });

      testWidgets('card elevation is 0', (tester) async {
        expect(_light.cardTheme.elevation, 0);
        expect(_dark.cardTheme.elevation, 0);
      });

      testWidgets('card margin is zero', (tester) async {
        expect(_light.cardTheme.margin, EdgeInsets.zero);
      });

      testWidgets('card shape uses lg radius', (tester) async {
        final shape = _light.cardTheme.shape;
        expect(shape, isA<RoundedRectangleBorder>());
        expect(
          (shape as RoundedRectangleBorder).borderRadius,
          AppRadius.lgAll,
        );
      });

      testWidgets('card has clipBehavior antiAlias', (tester) async {
        expect(_light.cardTheme.clipBehavior, Clip.antiAlias);
      });
    });

    group('AppBarTheme', () {
      testWidgets('centerTitle is true', (tester) async {
        expect(_light.appBarTheme.centerTitle, isTrue);
        expect(_dark.appBarTheme.centerTitle, isTrue);
      });

      testWidgets('elevation is 0', (tester) async {
        expect(_light.appBarTheme.elevation, 0);
      });

      testWidgets('scrolledUnderElevation is 1', (tester) async {
        expect(_light.appBarTheme.scrolledUnderElevation, 1);
      });

      testWidgets('light theme background is lightBackground', (tester) async {
        expect(
          _light.appBarTheme.backgroundColor,
          AppColors.lightBackground,
        );
      });

      testWidgets('light theme foreground is textPrimaryLight',
          (tester) async {
        expect(_light.appBarTheme.foregroundColor, AppColors.textPrimaryLight);
      });

      testWidgets('dark theme background is darkBackground', (tester) async {
        expect(
          _dark.appBarTheme.backgroundColor,
          AppColors.darkBackground,
        );
      });

      testWidgets('dark theme foreground is textPrimaryDark', (tester) async {
        expect(_dark.appBarTheme.foregroundColor, AppColors.textPrimaryDark);
      });
    });

    group('BottomNavigationBarTheme', () {
      testWidgets('type is fixed', (tester) async {
        expect(
          _light.bottomNavigationBarTheme.type,
          BottomNavigationBarType.fixed,
        );
      });

      testWidgets('selected label style has fontSize 12 and w500',
          (tester) async {
        final style = _light.bottomNavigationBarTheme.selectedLabelStyle;
        expect(style?.fontSize, 12);
        expect(style?.fontWeight, FontWeight.w500);
      });

      testWidgets('unselected label style has fontSize 12 and w400',
          (tester) async {
        final style = _light.bottomNavigationBarTheme.unselectedLabelStyle;
        expect(style?.fontSize, 12);
        expect(style?.fontWeight, FontWeight.w400);
      });

      testWidgets('light theme background is lightSurface', (tester) async {
        expect(
          _light.bottomNavigationBarTheme.backgroundColor,
          AppColors.lightSurface,
        );
      });

      testWidgets('light theme selectedItemColor is accent', (tester) async {
        expect(
          _light.bottomNavigationBarTheme.selectedItemColor,
          AppColors.accent,
        );
      });

      testWidgets('light theme unselectedItemColor is textSecondaryLight',
          (tester) async {
        expect(
          _light.bottomNavigationBarTheme.unselectedItemColor,
          AppColors.textSecondaryLight,
        );
      });

      testWidgets('dark theme background is darkSurface', (tester) async {
        expect(
          _dark.bottomNavigationBarTheme.backgroundColor,
          AppColors.darkSurface,
        );
      });

      testWidgets('dark theme selectedItemColor is accent', (tester) async {
        expect(
          _dark.bottomNavigationBarTheme.selectedItemColor,
          AppColors.accent,
        );
      });

      testWidgets('dark theme unselectedItemColor is textSecondaryDark',
          (tester) async {
        expect(
          _dark.bottomNavigationBarTheme.unselectedItemColor,
          AppColors.textSecondaryDark,
        );
      });
    });

    group('ChipTheme', () {
      testWidgets('label style has fontSize 11 and w500', (tester) async {
        final style = _light.chipTheme.labelStyle;
        expect(style?.fontSize, 11);
        expect(style?.fontWeight, FontWeight.w500);
      });

      testWidgets('shape is pill (fully rounded)', (tester) async {
        final shape = _light.chipTheme.shape;
        expect(shape, isA<RoundedRectangleBorder>());
        expect(
          (shape as RoundedRectangleBorder).borderRadius,
          AppRadius.pillAll,
        );
      });

      testWidgets('light theme chip background is lightElevated',
          (tester) async {
        expect(_light.chipTheme.backgroundColor, AppColors.lightElevated);
      });

      testWidgets('dark theme chip background is darkOverlay',
          (tester) async {
        expect(_dark.chipTheme.backgroundColor, AppColors.darkOverlay);
      });

      testWidgets('light theme chip label color is textPrimaryLight',
          (tester) async {
        expect(_light.chipTheme.labelStyle?.color, AppColors.textPrimaryLight);
      });

      testWidgets('dark theme chip label color is textPrimaryDark',
          (tester) async {
        expect(_dark.chipTheme.labelStyle?.color, AppColors.textPrimaryDark);
      });
    });

    group('ElevatedButtonTheme', () {
      testWidgets('button elevation is 0', (tester) async {
        final style = _light.elevatedButtonTheme.style;
        expect(style?.elevation?.resolve({}), 0);
      });

      testWidgets('button shape uses lg radius', (tester) async {
        final style = _light.elevatedButtonTheme.style;
        final shape = style?.shape?.resolve({});
        expect(shape, isA<RoundedRectangleBorder>());
        expect(
          (shape as RoundedRectangleBorder?)?.borderRadius,
          AppRadius.lgAll,
        );
      });

      testWidgets('button textStyle has fontSize 14 and w600', (tester) async {
        final style = _light.elevatedButtonTheme.style;
        final textStyle = style?.textStyle?.resolve({});
        expect(textStyle?.fontSize, 14);
        expect(textStyle?.fontWeight, FontWeight.w600);
      });

      testWidgets('button minimumSize has height 48', (tester) async {
        final style = _light.elevatedButtonTheme.style;
        final minSize = style?.minimumSize?.resolve({});
        expect(minSize?.height, 48);
      });
    });
  });

  // ==========================================================================
  // Theme inheritance — shared references between light/dark
  // ==========================================================================
  group('Theme inheritance and sharing', () {
    testWidgets('light and dark share the same ElevatedButtonTheme',
        (tester) async {
      expect(
        _light.elevatedButtonTheme,
        same(_dark.elevatedButtonTheme),
      );
    });

    testWidgets('both themes have primary color from seed', (tester) async {
      expect(_light.colorScheme.primary, isNotNull);
      expect(_dark.colorScheme.primary, isNotNull);
    });
  });
}
