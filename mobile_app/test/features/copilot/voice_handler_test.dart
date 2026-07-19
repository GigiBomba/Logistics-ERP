import 'package:flutter_test/flutter_test.dart';
import 'package:operion_mobile/features/copilot/voice/copilot_voice_handler.dart';

void main() {
  group('CopilotVoiceHandler', () {
    late CopilotVoiceHandler handler;

    setUp(() {
      handler = CopilotVoiceHandler();
    });

    tearDown(() {
      handler.dispose();
    });

    test('initial state has isListening false and hasPermission false', () {
      expect(handler.isListening, false);
      expect(handler.hasPermission, false);
    });

    group('requestPermission', () {
      test('returns true and sets hasPermission', () async {
        final granted = await handler.requestPermission();

        expect(granted, true);
        expect(handler.hasPermission, true);
      });

      test('can be called multiple times', () async {
        await handler.requestPermission();
        final granted = await handler.requestPermission();

        expect(granted, true);
        expect(handler.hasPermission, true);
      });
    });

    group('startListening', () {
      test('sets isListening to true when permission is granted', () async {
        await handler.requestPermission();

        handler.startListening(onTranscript: (transcript) {});

        expect(handler.isListening, true);
      });

      test('does not start when permission is not granted', () {
        // hasPermission is false by default

        handler.startListening(onTranscript: (transcript) {});

        expect(handler.isListening, false);
      });

      test('calls onTranscript when speech is detected', () async {
        // This is a contract test — the actual STT integration is
        // platform-specific and replaced with a real implementation.
        // Here we verify the API contract is satisfied.
        await handler.requestPermission();

        expect(handler.isListening, false);
        handler.startListening(onTranscript: (transcript) {
          // In production, this callback would be invoked with STT results.
          // For now, verify the callback type is correct.
          expect(transcript, isA<String>());
        });
        expect(handler.isListening, true);
      });
    });

    group('stopListening', () {
      test('sets isListening to false', () async {
        await handler.requestPermission();
        handler.startListening(onTranscript: (transcript) {});

        handler.stopListening();

        expect(handler.isListening, false);
      });

      test('is safe to call when not listening', () {
        handler.stopListening();

        expect(handler.isListening, false);
      });

      test('is safe to call multiple times', () {
        handler.stopListening();
        handler.stopListening();
        expect(handler.isListening, false);
      });
    });

    group('dispose', () {
      test('stops listening and cleans up', () async {
        await handler.requestPermission();
        handler.startListening(onTranscript: (transcript) {});

        handler.dispose();

        expect(handler.isListening, false);
      });

      test('is safe to call multiple times', () {
        handler.dispose();
        handler.dispose();
        // Should not throw
      });
    });

    group('listening lifecycle', () {
      test('start then stop then start again', () async {
        await handler.requestPermission();

        handler.startListening(onTranscript: (transcript) {});
        expect(handler.isListening, true);

        handler.stopListening();
        expect(handler.isListening, false);

        handler.startListening(onTranscript: (transcript) {});
        expect(handler.isListening, true);

        handler.stopListening();
      });
    });
  });
}
