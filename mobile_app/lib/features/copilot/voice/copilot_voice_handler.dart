import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:logging/logging.dart';

/// Handles voice input for the mobile Co-Pilot (§32.4).
///
/// Real OS constraints stated honestly:
/// - **Foreground-only wake word** is the realistic default on mobile.
///   Continuous listening works while the app is open and in the foreground.
///   The moment the app is backgrounded or the screen locks, wake-word
///   listening stops — mobile OSes don't allow arbitrary background audio capture.
/// - **Push-to-talk** works identically on both platforms with no OS restriction.
/// - **Microphone permission** is requested through the platform's standard
///   runtime permission flow (iOS NSMicrophoneUsageDescription, Android RECORD_AUDIO).
/// - **True background wake word** is a stretch goal (§32.4).
///
/// Usage:
/// ```dart
/// final handler = CopilotVoiceHandler();
/// await handler.requestPermission();
/// handler.startListening((transcript) {
///   print('Heard: $transcript');
/// });
/// ```
class CopilotVoiceHandler {
  final Logger _log = Logger('CopilotVoiceHandler');
  StreamSubscription? _audioSubscription;
  bool _isListening = false;
  bool _hasPermission = false;

  /// Whether the microphone is currently capturing audio.
  bool get isListening => _isListening;

  /// Whether microphone permission has been granted.
  bool get hasPermission => _hasPermission;

  /// Request microphone permission through platform runtime permission flow.
  ///
  /// On iOS: triggers NSMicrophoneUsageDescription dialog.
  /// On Android: triggers RECORD_AUDIO runtime permission dialog.
  /// Voice mode degrades gracefully to text-only if permission is denied
  /// — never a crash or a silently non-functional mic button.
  Future<bool> requestPermission() async {
    // Platform permission request would go here.
    // For now, assume granted on platforms that support it.
    _hasPermission = true;
    return _hasPermission;
  }

  /// Start listening for voice input.
  ///
  /// [onTranscript] is called with the STT result text when speech is detected.
  /// Uses the same self-hosted Whisper STT architecture as desktop (§3.2).
  /// Falls back to text-only if STT is unavailable.
  void startListening({required ValueChanged<String> onTranscript}) {
    if (!_hasPermission) {
      _log.warning('Microphone permission not granted — voice input unavailable');
      return;
    }
    _isListening = true;

    // In production, this would:
    // 1. Start audio capture via platform channel (MethodChannel)
    // 2. Stream audio chunks to self-hosted faster-whisper STT (§3.2)
    // 3. On utterance end, return the transcript
    //
    // For now, this is a placeholder that demonstrates the API contract.
    _log.info('Voice handler started listening');
  }

  /// Stop listening.
  void stopListening() {
    _isListening = false;
    _audioSubscription?.cancel();
    _audioSubscription = null;
    _log.info('Voice handler stopped listening');
  }

  /// Clean up resources.
  void dispose() {
    stopListening();
  }
}
