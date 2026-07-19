import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/shared/widgets/app_text_field.dart';

/// Wraps [child] in a [MaterialApp] with a constrained width for golden captures.
/// Accepts an optional [formKey] to embed the field inside a [Form].
Widget wrapForGolden(Widget child, {GlobalKey<FormState>? formKey}) {
  return MaterialApp(
    home: Scaffold(
      body: Center(
        child: SizedBox(
          width: 350,
          child: formKey != null
              ? Form(key: formKey, child: child)
              : child,
        ),
      ),
    ),
  );
}

void main() {
  testWidgets('AppTextField empty golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      const AppTextField(labelText: 'Email', hintText: 'email@example.com'),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppTextField),
      matchesReferenceImage(id: 'app_text_field_empty'),
    );
  });

  testWidgets('AppTextField filled golden', (tester) async {
    await tester.pumpWidget(wrapForGolden(
      const AppTextField(labelText: 'Name'),
    ));
    await tester.enterText(find.byType(TextFormField), 'John Doe');
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppTextField),
      matchesReferenceImage(id: 'app_text_field_filled'),
    );
  });

  testWidgets('AppTextField error state golden', (tester) async {
    final formKey = GlobalKey<FormState>();
    await tester.pumpWidget(wrapForGolden(
      AppTextField(
        labelText: 'Password',
        validator: (value) =>
            value == null || value.isEmpty ? 'Password is required' : null,
      ),
      formKey: formKey,
    ));
    // Trigger form validation
    formKey.currentState!.validate();
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppTextField),
      matchesReferenceImage(id: 'app_text_field_error'),
    );
  });

  testWidgets('AppTextField read-only golden', (tester) async {
    // Simulate a read-only field (pre-filled, non-interactive)
    final controller = TextEditingController(text: 'Prefilled value');
    addTearDown(controller.dispose);

    await tester.pumpWidget(wrapForGolden(
      AppTextField(
        labelText: 'Read Only',
        controller: controller,
      ),
    ));
    await tester.pumpAndSettle();
    await expectLater(
      find.byType(AppTextField),
      matchesReferenceImage(id: 'app_text_field_readonly'),
    );
  });
}
