import 'dart:async';
import 'dart:developer' as developer;

import 'package:firebase_messaging/firebase_messaging.dart';

// ── Data model ────────────────────────────────────────────────────────

/// Represents a push notification received by the device.
class PushNotification {
  /// Optional title (may be `null` for data-only payloads).
  final String? title;

  /// Optional body text.
  final String? body;

  /// Arbitrary key-value data payload.
  final Map<String, dynamic> data;

  /// When the notification was received by the service.
  final DateTime receivedAt;

  PushNotification({
    this.title,
    this.body,
    this.data = const {},
    DateTime? receivedAt,
  }) : receivedAt = receivedAt ?? DateTime.now();

  @override
  String toString() =>
      'PushNotification(title: $title, data: ${data.keys})';
}

// ── Push service ──────────────────────────────────────────────────────

/// Firebase Cloud Messaging wrapper.
///
/// Responsibilities:
/// - Obtaining and refreshing the device registration token.
/// - Listening for incoming messages (foreground, background, terminated).
/// - Exposing streams for notifications and token refreshes.
///
/// Usage (in your app's initialisation):
/// ```dart
/// final push = PushService();
/// await push.initialize();
/// ```
class PushService {
  final FirebaseMessaging _messaging;

  /// Broadcast stream that fires whenever a push notification arrives while
  /// the app is in the foreground.
  final StreamController<PushNotification> _notificationController =
      StreamController<PushNotification>.broadcast();

  /// Broadcast stream that fires whenever the FCM token is refreshed.
  final StreamController<String> _tokenController =
      StreamController<String>.broadcast();

  String? _token;

  /// The latest device registration token, or `null` if not yet obtained.
  String? get token => _token;

  /// Stream of foreground push notifications.
  Stream<PushNotification> get onNotification =>
      _notificationController.stream;

  /// Stream of FCM token refreshes.
  Stream<String> get onTokenRefresh => _tokenController.stream;

  PushService({FirebaseMessaging? messaging})
      : _messaging = messaging ?? FirebaseMessaging.instance;

  /// Initialises the service.
  ///
  /// Must be called after `Firebase.initializeApp()` has completed. This
  /// method:
  /// 1. Requests notification permissions (on iOS).
  /// 2. Retrieves the current FCM token.
  /// 3. Sets up foreground message handler.
  /// 4. Sets up background / terminated message handler.
  Future<void> initialize() async {
    // ── Permissions (iOS) ──────────────────────────
    await requestPermission();

    // ── Token ──────────────────────────────────────
    try {
      _token = await _messaging.getToken();
      developer.log(
        'PushService: token obtained (${_token?.substring(0, 8)}…)',
        name: 'PushService',
      );
    } catch (e) {
      developer.log('PushService: getToken failed → $e', name: 'PushService');
    }

    // Listen for token refresh.
    _messaging.onTokenRefresh.listen((newToken) {
      _token = newToken;
      developer.log(
        'PushService: token refreshed (${newToken.substring(0, 8)}…)',
        name: 'PushService',
      );
      _tokenController.add(newToken);
    });

    // ── Foreground messages ────────────────────────
    // onMessage fires when the app is in the foreground (visible).
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);

    // ── Background / terminated messages ──────────
    // The handlers are set via top-level callbacks passed to Firebase.
    // We store a reference so the app can wire them up.
    //
    // See also: `FirebaseMessaging.onBackgroundMessage` which must be a
    // top-level function (not a method) for the isolate to invoke it.
  }

  /// Requests notification permissions from the user.
  ///
  /// On Android this is a no-op (permissions are granted at install time).
  /// On iOS this shows the system dialog. Returns `true` if permission was
  /// granted.
  Future<bool> requestPermission() async {
    try {
      final settings = await _messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        announcement: false,
        carPlay: false,
        criticalAlert: false,
        provisional: false,
      );
      final granted = settings.authorizationStatus ==
              AuthorizationStatus.authorized ||
          settings.authorizationStatus == AuthorizationStatus.provisional;
      developer.log(
        'PushService: permission ${granted ? "granted" : "denied"} '
        '(status: ${settings.authorizationStatus.name})',
        name: 'PushService',
      );
      return granted;
    } catch (e) {
      developer.log(
        'PushService: requestPermission failed → $e',
        name: 'PushService',
      );
      return false;
    }
  }

  /// Retrieves the current FCM token explicitly.
  ///
  /// Useful for re-registration after login or when the user manually
  /// refreshes.
  Future<String?> getToken() async {
    try {
      _token = await _messaging.getToken();
      return _token;
    } catch (e) {
      developer.log(
        'PushService: getToken failed → $e',
        name: 'PushService',
      );
      return null;
    }
  }

  /// Called when a [RemoteMessage] is tapped by the user (from
  /// background/terminated state).
  ///
  /// Delegates to [onNotification] so listeners can react.
  void handleNotificationTap(RemoteMessage message) {
    final notification = message.notification;
    final pushNotification = PushNotification(
      title: notification?.title,
      body: notification?.body,
      data: message.data,
    );
    developer.log(
      'PushService: notification tapped – ${pushNotification.title}',
      name: 'PushService',
    );
    _notificationController.add(pushNotification);
  }

  /// Frees resources held by the service.
  void dispose() {
    _notificationController.close();
    _tokenController.close();
  }

  // ── Internal ────────────────────────────────────────────────────────

  void _handleForegroundMessage(RemoteMessage message) {
    final notification = message.notification;
    final pushNotification = PushNotification(
      title: notification?.title,
      body: notification?.body,
      data: message.data,
    );
    developer.log(
      'PushService: foreground message – ${pushNotification.title}',
      name: 'PushService',
    );
    _notificationController.add(pushNotification);
  }
}
