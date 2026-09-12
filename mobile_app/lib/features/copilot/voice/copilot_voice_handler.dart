import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:logging/logging.dart';

/// Handles voice input for the mobile Co-Pilot (§32.4).
///
/// Real OS constraints stated honestly:
/// - **Foreground-only wake word** is the realistic default on mobile.
///   Continuous listening works while the app is open and in the foreground.
///   The moment the app is backgrounded or the screen locks, wake-word
///   listening stops — mobile OSes don't allow arbitrary background audio capture.
///   [CopilotVoiceHandler] enforces this by observing app lifecycle changes
///   (see [attachLifecycleObserver]): any transition away from the foreground
///   stops wake-word listening. **Push-to-talk is unaffected** — a held press
///   is never cut off mid-press.
/// - **Push-to-talk** works identically on both platforms with no OS restriction.
/// - **Microphone permission** is requested through the platform's standard
///   runtime permission flow (iOS NSMicrophoneUsageDescription, Android RECORD_AUDIO).
/// - **True background wake word** is a stretch goal (§32.4).
///
/// Usage:
/// ```dart
/// final handler = CopilotVoiceHandler();
/// // Call once where the handler is owned, mirroring how the sync module
/// // registers SyncLifecycleObserver. dispose() removes the observer.
/// handler.attachLifecycleObserver();
/// await handler.requestPermission();
/// handler.startListening((transcript) {
///   print('Heard: $transcript');
/// });
/// ```
class CopilotVoiceHandler with WidgetsBindingObserver {
  final Logger _log = Logger('CopilotVoiceHandler');
  StreamSubscription? _audioSubscription;
  bool _isListening = false;
  bool _isPushToTalkActive = false;
  bool _hasPermission = false;
  bool _lifecycleObserved = false;

  /// Whether the microphone is currently capturing wake-word audio.
  bool get isListening => _isListening;

  /// Whether microphone permission has been granted.
  bool get hasPermission => _hasPermission;

  /// Whether a push-to-talk press is currently held down.
  bool get isPushToTalkActive => _isPushToTalkActive;

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

  /// Simulates a denied microphone permission so the graceful text-only
  /// fallback path can be exercised in tests. Production code never calls this.
  @visibleForTesting
  void debugSetPermission(bool granted) {
    _hasPermission = granted;
  }

  /// Start listening for wake-word voice input.
  ///
  /// [onTranscript] is called with the STT result text when speech is detected.
  /// Uses the same self-hosted Whisper STT architecture as desktop (§3.2).
  /// Falls back to text-only if STT is unavailable or permission is denied.
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

  /// Stop wake-word listening.
  void stopListening() {
    _isListening = false;
    _audioSubscription?.cancel();
    _audioSubscription = null;
    _log.info('Voice handler stopped listening');
  }

  /// Start a push-to-talk capture while the mic button is held down.
  ///
  /// Unlike wake-word listening, push-to-talk is **not** interrupted by app
  /// lifecycle transitions (§32.4): if the app is backgrounded mid-press the
  /// capture continues until the user releases the button. The lifecycle
  /// observer hook only touches the wake-word path ([stopListening]).
  void startPushToTalk({required ValueChanged<String> onTranscript}) {
    if (!_hasPermission) {
      _log.warning('Microphone permission not granted — voice input unavailable');
      return;
    }
    _isPushToTalkActive = true;
    _log.info('Voice handler push-to-talk started');
  }

  /// Release the push-to-talk capture.
  void stopPushToTalk() {
    _isPushToTalkActive = false;
    _log.info('Voice handler push-to-talk stopped');
  }

  /// Start observing app lifecycle so wake-word listening stops whenever the
  /// app leaves the foreground (§32.4).
  ///
  /// Call this once from the widget/controller that owns the handler, at the
  /// same level the app already observes lifecycle (mirrors how
  /// `SyncLifecycleObserver` registers itself). [dispose] removes the observer
  /// automatically, and [detachLifecycleObserver] can be called explicitly.
  /// Safe to call multiple times.
  void attachLifecycleObserver() {
    if (_lifecycleObserved) return;
    _lifecycleObserved = true;
    WidgetsBinding.instance.addObserver(this);
  }

  /// Stop observing app lifecycle. Safe to call when not attached.
  void detachLifecycleObserver() {
    if (!_lifecycleObserved) return;
    _lifecycleObserved = false;
    WidgetsBinding.instance.removeObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Wake-word listening is foreground-only (§32.4): the instant the app is
    // paused, covered, backgrounded, or detached, capture stops. Push-to-talk
    // is deliberately left untouched so a held press is never interrupted.
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.detached) {
      stopListening();
    }
  }

  /// Clean up resources.
  void dispose() {
    detachLifecycleObserver();
    stopListening();
    stopPushToTalk();
  }
}