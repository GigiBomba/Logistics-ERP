import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/features/copilot/voice/copilot_voice_handler.dart';

void main() {
  group('CopilotVoiceHandler background behavior (§32.4)', () {
    late CopilotVoiceHandler handler;

    setUp(() {
      handler = CopilotVoiceHandler();
    });

    tearDown(() {
      handler.dispose();
    });

    group('foreground-only wake word', () {
      testWidgets('lifecycle pause stops wake-word listening',
          (tester) async {
        handler.attachLifecycleObserver();
        await handler.requestPermission();
        handler.startListening(onTranscript: (_) {});

        expect(handler.isListening, true);

        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();

        expect(handler.isListening, false);
      });

      testWidgets('inactive and detached also stop wake-word listening',
          (tester) async {
        handler.attachLifecycleObserver();
        await handler.requestPermission();

        for (final state in <AppLifecycleState>[
          AppLifecycleState.inactive,
          AppLifecycleState.hidden,
          AppLifecycleState.detached,
        ]) {
          handler.startListening(onTranscript: (_) {});
          expect(handler.isListening, true);

          tester.binding.handleAppLifecycleStateChanged(state);
          await tester.pump();

          expect(handler.isListening, false,
              reason: 'listening must stop on $state (§32.4)');
        }
      });

      testWidgets('resume does not auto-restart wake-word listening',
          (tester) async {
        handler.attachLifecycleObserver();
        await handler.requestPermission();
        handler.startListening(onTranscript: (_) {});

        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await tester.pump();

        // Foreground-only: returning to the foreground requires an explicit
        // start from the UI — the handler never silently re-opens the mic.
        expect(handler.isListening, false);
      });

      testWidgets('resume allows wake-word listening to start again explicitly',
          (tester) async {
        handler.attachLifecycleObserver();
        await handler.requestPermission();
        handler.startListening(onTranscript: (_) {});

        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
        await tester.pump();

        handler.startListening(onTranscript: (_) {});
        expect(handler.isListening, true);
      });

      testWidgets('lifecycle guard is ignored until attachLifecycleObserver',
          (tester) async {
        // Handler not attached to the binding: lifecycle events must not
        // affect it (e.g. unit tests that never initialize a binding).
        await handler.requestPermission();
        handler.startListening(onTranscript: (_) {});

        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();

        expect(handler.isListening, true);
      });

      testWidgets('detachLifecycleObserver stops the guard', (tester) async {
        handler.attachLifecycleObserver();
        handler.detachLifecycleObserver();
        await handler.requestPermission();
        handler.startListening(onTranscript: (_) {});

        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();

        expect(handler.isListening, true);
      });
    });

    group('permission denied — graceful text-only fallback', () {
      test('startListening no-ops instead of throwing when permission denied',
          () async {
        await handler.requestPermission();
        handler.debugSetPermission(false);

        expect(handler.hasPermission, false);

        // Voice is unavailable but never crashes: the UI falls back to
        // text-only input while the mic button stays safe to press.
        expect(() => handler.startListening(onTranscript: (_) {}),
            returnsNormally);
        expect(handler.isListening, false);
      });

      test('push-to-talk also falls back gracefully when permission denied',
          () async {
        await handler.requestPermission();
        handler.debugSetPermission(false);

        expect(() => handler.startPushToTalk(onTranscript: (_) {}),
            returnsNormally);
        expect(handler.isPushToTalkActive, false);
      });

      test('handler recovers once permission is granted later', () async {
        await handler.requestPermission();
        handler.debugSetPermission(false);
        handler.startListening(onTranscript: (_) {});
        expect(handler.isListening, false);

        handler.debugSetPermission(true);
        handler.startListening(onTranscript: (_) {});
        expect(handler.isListening, true);
      });
    });

    group('push-to-talk across foreground transitions', () {
      testWidgets('push-to-talk is not interrupted by lifecycle transitions',
          (tester) async {
        handler.attachLifecycleObserver();
        await handler.requestPermission();
        handler.startPushToTalk(onTranscript: (_) {});

        expect(handler.isPushToTalkActive, true);

        for (final state in <AppLifecycleState>[
          AppLifecycleState.inactive,
          AppLifecycleState.hidden,
          AppLifecycleState.paused,
          AppLifecycleState.resumed,
        ]) {
          tester.binding.handleAppLifecycleStateChanged(state);
          await tester.pump();
          expect(handler.isPushToTalkActive, true,
              reason: 'push-to-talk must survive $state (§32.4)');
        }

        handler.stopPushToTalk();
        expect(handler.isPushToTalkActive, false);
      });

      testWidgets('wake-word stops while push-to-talk continues mid-press',
          (tester) async {
        handler.attachLifecycleObserver();
        await handler.requestPermission();
        handler.startListening(onTranscript: (_) {});
        handler.startPushToTalk(onTranscript: (_) {});

        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        await tester.pump();

        // The pause hook only stops the wake-word/listening path; the held
        // push-to-talk press keeps running.
        expect(handler.isListening, false);
        expect(handler.isPushToTalkActive, true);
      });

      test('push-to-talk works independently of wake-word state', () async {
        await handler.requestPermission();
        handler.startListening(onTranscript: (_) {});

        expect(handler.isPushToTalkActive, false);
        handler.startPushToTalk(onTranscript: (_) {});
        expect(handler.isPushToTalkActive, true);
        expect(handler.isListening, true);

        handler.stopListening();
        expect(handler.isPushToTalkActive, true);
        handler.stopPushToTalk();
        expect(handler.isPushToTalkActive, false);
      });
    });
  });
}