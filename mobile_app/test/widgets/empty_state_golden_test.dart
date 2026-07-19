import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/empty_state.dart';

/// Wraps [child] in a [MaterialApp] for golden captures.
Widget wrapForGolden(Widget child) {
  return MaterialApp(
    home: Scaffold(
      body: child, // EmptyState already uses Center with padding
    ),
  );
}

void main() {
  testWidgets('EmptyState default golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      const EmptyState(
        icon: Icon(Icons.inbox_outlined),
        title: 'No data available',
      ),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(EmptyState),
      matchesReferenceImage(id: 'empty_state_default'),
    );
  });

  testWidgets('EmptyState custom icon/text golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      const EmptyState(
        icon: Icon(Icons.search_off),
        title: 'No results found',
        subtitle: 'Try adjusting your filters or search terms',
      ),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(EmptyState),
      matchesReferenceImage(id: 'empty_state_custom'),
    );
  });
}
