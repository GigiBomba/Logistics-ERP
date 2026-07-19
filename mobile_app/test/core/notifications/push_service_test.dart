import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

import 'package:operion_mobile/core/notifications/push_service.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Minimal FirebaseMessaging stub via noSuchMethod
// ─────────────────────────────────────────────────────────────────────────────

class StubFirebaseMessaging implements FirebaseMessaging {
  final _tokenRefreshController = StreamController<String>.broadcast();

  String? stubbedToken;
  NotificationSettings stubbedPermissionSettings = NotificationSettings(
    authorizationStatus: AuthorizationStatus.authorized,
    alert: AppleNotificationSetting.enabled,
    announcement: AppleNotificationSetting.enabled,
    badge: AppleNotificationSetting.enabled,
    carPlay: AppleNotificationSetting.enabled,
    criticalAlert: AppleNotificationSetting.enabled,
    lockScreen: AppleNotificationSetting.enabled,
    notificationCenter: AppleNotificationSetting.enabled,
    providesAppNotificationSettings: AppleNotificationSetting.enabled,
    showPreviews: AppleShowPreviewSetting.always,
    sound: AppleNotificationSetting.enabled,
    timeSensitive: AppleNotificationSetting.enabled,
  );

  Object? getTokenError;
  Object? permissionError;
  bool getTokenCalled = false;
  bool permissionCalled = false;

  @override
  Future<String?> getToken({String? vapidKey}) async {
    getTokenCalled = true;
    if (getTokenError != null) throw getTokenError!;
    return stubbedToken;
  }

  @override
  Future<NotificationSettings> requestPermission({
    bool alert = true,
    bool announcement = false,
    bool badge = true,
    bool carPlay = false,
    bool criticalAlert = false,
    bool provisional = false,
    bool providesAppNotificationSettings = false,
    bool sound = true,
  }) async {
    permissionCalled = true;
    if (permissionError != null) throw permissionError!;
    return stubbedPermissionSettings;
  }

  @override
  Stream<String> get onTokenRefresh => _tokenRefreshController.stream;

  void simulateTokenRefresh(String token) {
    _tokenRefreshController.add(token);
  }

  void disposeService() => _tokenRefreshController.close();

  @override
  dynamic noSuchMethod(Invocation i) {
    // Satisfy remaining FirebaseMessaging interface members.
    // None of these are used by PushService.
    if (i.isGetter) return null;
    if (i.isMethod) return Future.value();
    return null;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

void main() {
  group('PushService', () {
    late StubFirebaseMessaging stubMessaging;
    late PushService pushService;

    setUp(() {
      stubMessaging = StubFirebaseMessaging();
      stubMessaging.stubbedToken = 'fcm-token-abc123';
      pushService = PushService(messaging: stubMessaging);
    });

    tearDown(() {
      pushService.dispose();
      stubMessaging.disposeService();
    });

    // ── Token management ─────────────────────────

    group('token', () {
      test('getToken returns the stubbed token', () async {
        final token = await pushService.getToken();
        expect(token, 'fcm-token-abc123');
        expect(pushService.token, 'fcm-token-abc123');
      });

      test('getToken returns null on failure', () async {
        stubMessaging.getTokenError = Exception('network error');
        final token = await pushService.getToken();
        expect(token, isNull);
        expect(pushService.token, isNull);
      });

      test('getToken delegates to Firebase getToken', () async {
        await pushService.getToken();
        expect(stubMessaging.getTokenCalled, isTrue);
      });

      test('token is null before any getToken call', () {
        expect(pushService.token, isNull);
      });
    });

    // ── Permission requests ──────────────────────

    group('requestPermission', () {
      test('returns true when authorised', () async {
        expect(await pushService.requestPermission(), isTrue);
      });

      test('returns false when denied', () async {
        stubMessaging.stubbedPermissionSettings = NotificationSettings(
          authorizationStatus: AuthorizationStatus.denied,
          alert: AppleNotificationSetting.enabled,
          announcement: AppleNotificationSetting.enabled,
          badge: AppleNotificationSetting.enabled,
          carPlay: AppleNotificationSetting.enabled,
          criticalAlert: AppleNotificationSetting.enabled,
          lockScreen: AppleNotificationSetting.enabled,
          notificationCenter: AppleNotificationSetting.enabled,
          providesAppNotificationSettings: AppleNotificationSetting.enabled,
          showPreviews: AppleShowPreviewSetting.always,
          sound: AppleNotificationSetting.enabled,
          timeSensitive: AppleNotificationSetting.enabled,
        );
        expect(await pushService.requestPermission(), isFalse);
      });

      test('returns false on exception', () async {
        stubMessaging.permissionError = Exception('fail');
        expect(await pushService.requestPermission(), isFalse);
      });

      test('delegates to Firebase', () async {
        await pushService.requestPermission();
        expect(stubMessaging.permissionCalled, isTrue);
      });
    });

    // ── Notification handling ────────────────────

    group('handleNotificationTap', () {
      test('creates PushNotification with title and body', () async {
        final received = <PushNotification>[];
        pushService.onNotification.listen(received.add);

        pushService.handleNotificationTap(RemoteMessage(
          notification: RemoteNotification(title: 'Title', body: 'Body'),
          data: {'k': 'v'},
        ));

        await Future(() {});
        expect(received, hasLength(1));
        expect(received[0].title, 'Title');
        expect(received[0].body, 'Body');
        expect(received[0].data, {'k': 'v'});
      });

      test('data-only notification has null title/body', () async {
        final received = <PushNotification>[];
        pushService.onNotification.listen(received.add);

        pushService.handleNotificationTap(RemoteMessage(
          notification: null,
          data: {'type': 'silent'},
        ));

        await Future(() {});
        expect(received, hasLength(1));
        expect(received[0].title, isNull);
        expect(received[0].body, isNull);
        expect(received[0].data, {'type': 'silent'});
      });

      test('title-only notification', () async {
        final received = <PushNotification>[];
        pushService.onNotification.listen(received.add);

        pushService.handleNotificationTap(RemoteMessage(
          notification: RemoteNotification(title: 'Only Title'),
          data: const {},
        ));

        await Future(() {});
        expect(received, hasLength(1));
        expect(received[0].title, 'Only Title');
        expect(received[0].body, isNull);
      });

      test('body-only notification', () async {
        final received = <PushNotification>[];
        pushService.onNotification.listen(received.add);

        pushService.handleNotificationTap(RemoteMessage(
          notification: RemoteNotification(body: 'Only Body'),
          data: const {},
        ));

        await Future(() {});
        expect(received, hasLength(1));
        expect(received[0].title, isNull);
        expect(received[0].body, 'Only Body');
      });

      test('notifications arrive in order', () async {
        final received = <PushNotification>[];
        pushService.onNotification.listen(received.add);

        pushService.handleNotificationTap(
          RemoteMessage(
            notification: RemoteNotification(title: 'First'),
            data: {'seq': '1'},
          ),
        );
        pushService.handleNotificationTap(
          RemoteMessage(
            notification: RemoteNotification(title: 'Second'),
            data: {'seq': '2'},
          ),
        );

        await Future(() {});
        expect(received, hasLength(2));
        expect(received[0].title, 'First');
        expect(received[1].title, 'Second');
      });

      test('receivedAt is set to current time', () async {
        final received = <PushNotification>[];
        pushService.onNotification.listen(received.add);

        final before = DateTime.now();
        pushService.handleNotificationTap(RemoteMessage(
          notification: RemoteNotification(title: 'Now'),
          data: const {},
        ));
        final after = DateTime.now();

        await Future(() {});
        expect(received, hasLength(1));
        expect(
          received[0].receivedAt.isAfter(
            before.subtract(const Duration(seconds: 1)),
          ),
          isTrue,
        );
        expect(
          received[0].receivedAt.isBefore(
            after.add(const Duration(seconds: 1)),
          ),
          isTrue,
        );
      });
    });

    // ── Error resilience & lifecycle ─────────────

    group('error resilience', () {
      test('handleNotificationTap with null notification does not crash', () {
        pushService.onNotification.listen((_) {});
        pushService.handleNotificationTap(
          RemoteMessage(notification: null, data: const {}),
        );
      });

      test('dispose is idempotent', () {
        pushService.dispose();
        expect(() => pushService.dispose(), returnsNormally);
      });
    });

    // ── Constructor ──────────────────────────────

    group('constructor', () {
      test('accepts custom FirebaseMessaging instance', () {
        final service = PushService(messaging: stubMessaging);
        expect(service.token, isNull);
        service.dispose();
      });
    });
  });
}
