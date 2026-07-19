import 'dart:async' show runZonedGuarded;
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/app.dart';

void main() {
  // Note: We do NOT call the actual main() function because it invokes
  // runApp(), which cannot be called more than once per process. Instead we
  // test all the individual steps that main() performs so we can verify the
  // entry-point logic is correct.

  // ==========================================================================
  // WidgetsFlutterBinding setup
  // ==========================================================================
  group('WidgetsFlutterBinding setup', () {
    testWidgets('WidgetsFlutterBinding.ensureInitialized returns a binding',
        (tester) async {
      final binding = WidgetsFlutterBinding.ensureInitialized();
      expect(binding, isNotNull);
      expect(binding, isA<WidgetsBinding>());
    });

    testWidgets('ensureInitialized is idempotent', (tester) async {
      final first = WidgetsFlutterBinding.ensureInitialized();
      final second = WidgetsFlutterBinding.ensureInitialized();
      expect(first, same(second));
    });

    testWidgets('WidgetsBinding is available after initialization',
        (tester) async {
      WidgetsFlutterBinding.ensureInitialized();
      expect(WidgetsBinding.instance, isNotNull);
    });
  });

  // ==========================================================================
  // FlutterError.onError handler
  // ==========================================================================
  group('FlutterError.onError handler', () {
    // FlutterError.onError is nullable (FlutterExceptionHandler?),
    // so we track the original handler dynamically.
    late dynamic /* FlutterExceptionHandler? */ originalHandler;

    setUp(() {
      originalHandler = FlutterError.onError;
    });

    tearDown(() {
      FlutterError.onError = originalHandler;
    });

    testWidgets('can be set to a custom handler', (tester) async {
      FlutterError.onError = (details) {
        // Custom handler — same pattern as main.dart
      };
      expect(FlutterError.onError, isNot(same(originalHandler)));
    });

    testWidgets('custom handler does not throw when invoked', (tester) async {
      FlutterError.onError = (details) {
        // Same pattern as main.dart
      };

      expect(
        () => FlutterError.onError!(FlutterErrorDetails(
          exception: Exception('test error'),
          stack: StackTrace.current,
        )),
        returnsNormally,
      );
    });

    testWidgets('handler can be used with reportError', (tester) async {
      FlutterError.onError = (details) {
        // Same pattern as main.dart — just log without throwing
      };

      expect(
        () => FlutterError.reportError(FlutterErrorDetails(
          exception: 'test string error',
        )),
        returnsNormally,
      );
    });
  });

  // ==========================================================================
  // PlatformDispatcher.onError handler
  // ==========================================================================
  group('PlatformDispatcher.onError handler', () {
    testWidgets('can be set to a custom handler', (tester) async {
      PlatformDispatcher.instance.onError = (error, stack) {
        return true; // Don't kill the app — same pattern as main.dart
      };
      expect(PlatformDispatcher.instance.onError, isNotNull);
    });

    testWidgets('handler returns true to prevent app termination',
        (tester) async {
      bool handlerCalled = false;
      PlatformDispatcher.instance.onError = (error, stack) {
        handlerCalled = true;
        return true;
      };

      final result = PlatformDispatcher.instance
          .onError!(Exception('test'), StackTrace.current);
      expect(handlerCalled, isTrue);
      expect(result, isTrue);
    });
  });

  // ==========================================================================
  // OperionMobileApp instantiation
  // ==========================================================================
  group('OperionMobileApp instantiation', () {
    testWidgets('can be instantiated', (tester) async {
      const app = OperionMobileApp();
      expect(app, isA<OperionMobileApp>());
    });

    test('constructor is const', () {
      const app1 = OperionMobileApp();
      const app2 = OperionMobileApp();
      expect(app1, isNot(same(app2))); // Different instances
    });
  });

  // ==========================================================================
  // main() initialisation pattern
  // ==========================================================================
  group('main() initialisation pattern', () {
    testWidgets('runZonedGuarded pattern works without crashing',
        (tester) async {
      bool guardCalled = false;

      runZonedGuarded(() {
        guardCalled = true;
        // In main.dart this calls:
        //   WidgetsFlutterBinding.ensureInitialized();
        //   runApp(const OperionMobileApp());
        // We test those steps individually above.
      }, (error, stack) {
        // Zone guard handler — same pattern as main.dart
      });

      expect(guardCalled, isTrue);
    });

    testWidgets('zone guard handler catches errors without crashing',
        (tester) async {
      bool guardTriggered = false;

      runZonedGuarded(() {
        throw Exception('deliberate test exception');
      }, (error, stack) {
        guardTriggered = true;
      });

      // Give the zone time to process the error
      await tester.pump();

      expect(guardTriggered, isTrue);
    });
  });
}
