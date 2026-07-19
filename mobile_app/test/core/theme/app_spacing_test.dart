import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/theme/app_spacing.dart';

void main() {
  // ==========================================================================
  // AppSpacing
  // ==========================================================================
  group('AppSpacing', () {
    test('xs is 4', () {
      expect(AppSpacing.xs, 4);
    });

    test('sm is 8', () {
      expect(AppSpacing.sm, 8);
    });

    test('md is 12', () {
      expect(AppSpacing.md, 12);
    });

    test('lg is 16', () {
      expect(AppSpacing.lg, 16);
    });

    test('xl is 20', () {
      expect(AppSpacing.xl, 20);
    });

    test('xxl is 24', () {
      expect(AppSpacing.xxl, 24);
    });

    test('xxxl is 32', () {
      expect(AppSpacing.xxxl, 32);
    });

    test('huge is 40', () {
      expect(AppSpacing.huge, 40);
    });

    test('xhuge is 48', () {
      expect(AppSpacing.xhuge, 48);
    });

    test('giant is 64', () {
      expect(AppSpacing.giant, 64);
    });

    group('Spacing scale is strictly increasing', () {
      test('xs < sm < md < lg', () {
        expect(AppSpacing.xs, lessThan(AppSpacing.sm));
        expect(AppSpacing.sm, lessThan(AppSpacing.md));
        expect(AppSpacing.md, lessThan(AppSpacing.lg));
      });

      test('lg < xl < xxl < xxxl < huge < xhuge < giant', () {
        expect(AppSpacing.lg, lessThan(AppSpacing.xl));
        expect(AppSpacing.xl, lessThan(AppSpacing.xxl));
        expect(AppSpacing.xxl, lessThan(AppSpacing.xxxl));
        expect(AppSpacing.xxxl, lessThan(AppSpacing.huge));
        expect(AppSpacing.huge, lessThan(AppSpacing.xhuge));
        expect(AppSpacing.xhuge, lessThan(AppSpacing.giant));
      });
    });

    group('Edge inset values', () {
      test('EdgeInsets.all(xs) creates uniform 4px insets', () {
        const insets = EdgeInsets.all(AppSpacing.xs);
        expect(insets.left, 4);
        expect(insets.right, 4);
        expect(insets.top, 4);
        expect(insets.bottom, 4);
      });
      test(
          'EdgeInsets.symmetric(horizontal: lg, vertical: md) creates 32x24',
          () {
        // EdgeInsets.symmetric sums left+right and top+bottom
        const insets = EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.md,
        );
        expect(insets.horizontal, AppSpacing.lg * 2); // 32
        expect(insets.vertical, AppSpacing.md * 2); // 24
      });

      test('EdgeInsets.only(left: xl, right: xxl) asymmetrical inset', () {
        const insets = EdgeInsets.only(
          left: AppSpacing.xl,
          right: AppSpacing.xxl,
        );
        expect(insets.left, 20);
        expect(insets.right, 24);
        expect(insets.top, 0);
        expect(insets.bottom, 0);
      });
    });
  });

  // ==========================================================================
  // AppRadius
  // ==========================================================================
  group('AppRadius', () {
    test('sm is 4', () {
      expect(AppRadius.sm, 4);
    });

    test('md is 6', () {
      expect(AppRadius.md, 6);
    });

    test('lg is 8', () {
      expect(AppRadius.lg, 8);
    });

    test('xl is 12', () {
      expect(AppRadius.xl, 12);
    });

    test('pill is 999', () {
      expect(AppRadius.pill, 999);
    });

    group('BorderRadius constants', () {
      test('smAll is all corners with sm radius', () {
        expect(AppRadius.smAll, const BorderRadius.all(Radius.circular(4)));
      });

      test('mdAll is all corners with md radius', () {
        expect(AppRadius.mdAll, const BorderRadius.all(Radius.circular(6)));
      });

      test('lgAll is all corners with lg radius', () {
        expect(AppRadius.lgAll, const BorderRadius.all(Radius.circular(8)));
      });

      test('xlAll is all corners with xl radius', () {
        expect(AppRadius.xlAll, const BorderRadius.all(Radius.circular(12)));
      });

      test('pillAll is all corners with pill radius (999)', () {
        expect(
          AppRadius.pillAll,
          const BorderRadius.all(Radius.circular(999)),
        );
      });
    });

    group('Radius scale consistency', () {
      test('sm < md < lg < xl', () {
        expect(AppRadius.sm, lessThan(AppRadius.md));
        expect(AppRadius.md, lessThan(AppRadius.lg));
        expect(AppRadius.lg, lessThan(AppRadius.xl));
      });

      test('pill is the largest', () {
        expect(AppRadius.pill, greaterThan(AppRadius.xl));
      });
    });

    group('BorderRadius usage patterns', () {
      test('pillAll produces fully rounded corners', () {
        const rect = RoundedRectangleBorder(
          borderRadius: AppRadius.pillAll,
        );
        expect(rect.borderRadius, AppRadius.pillAll);
      });

      test('lgAll matches the app default component radius', () {
        // Used throughout component themes
        expect(AppRadius.lgAll.topLeft.x, AppRadius.lg);
        expect(AppRadius.lgAll.topRight.x, AppRadius.lg);
        expect(AppRadius.lgAll.bottomLeft.x, AppRadius.lg);
        expect(AppRadius.lgAll.bottomRight.x, AppRadius.lg);
      });
    });
  });
}
