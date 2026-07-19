import 'dart:async' show runZonedGuarded;
import 'dart:developer' as developer;
import 'dart:ui' show PlatformDispatcher;

import 'package:flutter/material.dart';
import 'app.dart';

void main() {
  // ── Global error handlers ─────────────────────────────────────────
  // Every unhandled error — Flutter framework, async, and plain Dart —
  // gets dumped to the debug console with full stack trace.

  FlutterError.onError = (details) {
    developer.log(
      '[FLUTTER ERROR] ${details.exception}\n${details.stack}',
      name: 'FlutterError',
    );
  };

  PlatformDispatcher.instance.onError = (error, stack) {
    developer.log(
      '[UNHANDLED ERROR] $error\n$stack',
      name: 'PlatformDispatcher',
    );
    return true; // Don't kill the app
  };

  runZonedGuarded(() {
    WidgetsFlutterBinding.ensureInitialized();
    runApp(const OperionMobileApp());
  }, (error, stack) {
    developer.log(
      '[ZONED GUARD] $error\n$stack',
      name: 'ZoneGuard',
    );
  });
}
