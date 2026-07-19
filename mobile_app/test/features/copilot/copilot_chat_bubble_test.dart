import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/copilot/widgets/copilot_chat_bubble.dart';

/// Helper to wrap a widget for testing with the needed Material theme.
Widget wrapInApp(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

void main() {
  group('CopilotChatBubble', () {
    // ======================================================================
    // User bubbles
    // ======================================================================
    group('user bubble', () {
      testWidgets('renders user text right-aligned', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: 'Hello AI', isUser: true),
        ));

        expect(find.text('Hello AI'), findsOneWidget);
        // User messages don't have the AI avatar
        expect(find.byIcon(Icons.auto_awesome), findsNothing);
      });

      testWidgets('renders with status label when provided', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: 'Done', isUser: true, statusLabel: 'sent'),
        ));

        expect(find.text('Done'), findsOneWidget);
        expect(find.text('sent'), findsOneWidget);
      });

      testWidgets('does not display status label when null', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: 'Hello', isUser: true, statusLabel: null),
        ));

        expect(find.text('Hello'), findsOneWidget);
        // Only one Text widget should be present (the message text, no status)
        // The status label text 'null' should NOT be in the widget tree
        expect(find.text('null'), findsNothing);
      });
    });

    // ======================================================================
    // Assistant bubbles (AI responses)
    // ======================================================================
    group('assistant bubble', () {
      testWidgets('renders AI text left-aligned with avatar', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: 'Here are the available trucks', isUser: false),
        ));

        expect(find.text('Here are the available trucks'), findsOneWidget);
        // AI messages show the auto_awesome icon avatar
        expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
      });

      testWidgets('renders with status label when provided', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(
            text: 'Processing...',
            isUser: false,
            statusLabel: 'completed',
          ),
        ));

        expect(find.text('Processing...'), findsOneWidget);
        expect(find.text('completed'), findsOneWidget);
      });

      testWidgets('hides status label when not provided', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: 'Done', isUser: false),
        ));

        // Only the AI message text should be present
        expect(find.text('Done'), findsOneWidget);
        expect(find.text('null'), findsNothing);
      });
    });

    // ======================================================================
    // Long messages
    // ======================================================================
    group('long messages', () {
      testWidgets('renders long text without overflow', (tester) async {
        final longText = 'A' * 500;
        await tester.pumpWidget(wrapInApp(
          CopilotChatBubble(text: longText, isUser: false),
        ));

        // Should render the full text
        expect(find.text(longText), findsOneWidget);
      });

      testWidgets('renders multi-line text', (tester) async {
        final multiLine = 'Line 1\nLine 2\nLine 3';
        await tester.pumpWidget(wrapInApp(
          CopilotChatBubble(text: multiLine, isUser: true),
        ));

        expect(find.text(multiLine), findsOneWidget);
      });
    });

    // ======================================================================
    // Default isUser
    // ======================================================================
    group('default values', () {
      testWidgets('default isUser is false (assistant bubble)', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: 'Default message'),
        ));

        // Should show AI avatar since isUser defaults to false
        expect(find.byIcon(Icons.auto_awesome), findsOneWidget);
        expect(find.text('Default message'), findsOneWidget);
      });
    });

    // ======================================================================
    // Edge cases
    // ======================================================================
    group('edge cases', () {
      testWidgets('renders empty text without crashing', (tester) async {
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: '', isUser: true),
        ));

        // Should not crash, should render an empty container
        expect(find.byType(CopilotChatBubble), findsOneWidget);
      });

      testWidgets('renders special characters', (tester) async {
        const specialText = 'Price: \$100 & tax @ 20% "discount" <valid>';
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: specialText, isUser: false),
        ));

        expect(find.text(specialText), findsOneWidget);
      });

      testWidgets('renders URLs in text', (tester) async {
        const urlText = 'Check https://example.com for details';
        await tester.pumpWidget(wrapInApp(
          const CopilotChatBubble(text: urlText, isUser: false),
        ));

        expect(find.text(urlText), findsOneWidget);
      });
    });
  });
}
