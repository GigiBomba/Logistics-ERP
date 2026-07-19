import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/app_button.dart';

/// Wraps [child] in a [MaterialApp] with a constrained width for golden captures.
Widget wrapForGolden(Widget child) {
  return MaterialApp(
    home: Scaffold(
      body: Center(
        child: SizedBox(width: 300, child: child),
      ),
    ),
  );
}

void main() {
  testWidgets('AppButton primary golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      AppButton.primary(label: 'Sign In', onPressed: () {}),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppButton),
      matchesReferenceImage(id: 'app_button_primary'),
    );
  });

  testWidgets('AppButton secondary golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      AppButton.secondary(label: 'Cancel', onPressed: () {}),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppButton),
      matchesReferenceImage(id: 'app_button_secondary'),
    );
  });

  testWidgets('AppButton disabled golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      AppButton.primary(label: 'Disabled', onPressed: null),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppButton),
      matchesReferenceImage(id: 'app_button_disabled'),
    );
  });

  testWidgets('AppButton loading golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      AppButton.primary(label: 'Loading', onPressed: () {}, isLoading: true),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppButton),
      matchesReferenceImage(id: 'app_button_loading'),
    );
  });
}
