import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/app_card.dart';

/// Wraps [child] in a [MaterialApp] with a constrained width for golden captures.
Widget wrapForGolden(Widget child) {
  return MaterialApp(
    home: Scaffold(
      body: Center(
        child: SizedBox(width: 350, child: child),
      ),
    ),
  );
}

void main() {
  testWidgets('AppCard basic golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      const AppCard(child: Text('Card content')),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppCard),
      matchesReferenceImage(id: 'app_card_basic'),
    );
  });

  testWidgets('AppCard with header/footer golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      AppCard(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.only(bottom: 8),
              decoration: const BoxDecoration(
                border: Border(
                  bottom: BorderSide(color: Colors.black12),
                ),
              ),
              child: const Text(
                'Card Header',
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
            const Text('Main body content goes here.'),
            const SizedBox(height: 8),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.only(top: 8),
              decoration: const BoxDecoration(
                border: Border(
                  top: BorderSide(color: Colors.black12),
                ),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(onPressed: null, child: const Text('Action')),
                ],
              ),
            ),
          ],
        ),
      ),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppCard),
      matchesReferenceImage(id: 'app_card_header_footer'),
    );
  });

  testWidgets('AppCard elevated golden', (tester) async {
    // Elevated = tappable card via onTap
    await tester.pumpWidget(wrapForGolden(
      AppCard(
        onTap: () {},
        child: const Text('Tapable card with elevation on press'),
      ),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppCard),
      matchesReferenceImage(id: 'app_card_elevated'),
    );
  });
}
