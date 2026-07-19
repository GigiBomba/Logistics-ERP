import 'dart:developer' as developer;

import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'push_service.dart';

// ── Service provider ──────────────────────────────────────────────────

/// Provides the singleton [PushService] instance.
///
/// **Important**: This provider must be overridden during app initialisation
/// because [PushService] depends on Firebase having been initialised.
///
/// ```dart
/// final pushService = PushService();
/// await pushService.initialize();
/// ref.read(pushServiceProvider.notifier).overrideWithValue(pushService);
/// ```
final pushServiceProvider = Provider<PushService>((ref) {
  throw UnimplementedError(
    'PushService must be initialised and overridden in ProviderScope overrides.\n'
    'See notification_providers.dart for instructions.',
  );
});

// ── Simple state providers ────────────────────────────────────────────

/// Whether the user has granted notification permissions.
final notificationPermissionProvider = StateProvider<bool>((ref) => false);

/// The current FCM device token, if available.
///
/// Updated automatically when [PushService.onTokenRefresh] fires.
final deviceTokenProvider = StateProvider<String?>((ref) => null);

// ── In-app notification centre ────────────────────────────────────────

/// A single in-app notification shown in the notification centre screen.
class InAppNotification {
  /// Unique identifier for this notification.
  final String id;

  /// Title text.
  final String title;

  /// Body / description text.
  final String body;

  /// Notification type — one of `'new_assignment'`, `'new_message'`,
  /// `'alert'`, `'status_change'`, `'approval'`, etc.
  final String type;

  /// Navigation parameters extracted from the push payload.
  final Map<String, String>? routeParams;

  /// Whether the user has viewed this notification.
  final bool isRead;

  /// When the notification was received or created.
  final DateTime createdAt;

  const InAppNotification({
    required this.id,
    required this.title,
    required this.body,
    required this.type,
    this.routeParams,
    this.isRead = false,
    required this.createdAt,
  });

  /// Creates a copy with the given fields replaced.
  InAppNotification copyWith({bool? isRead}) {
    return InAppNotification(
      id: id,
      title: title,
      body: body,
      type: type,
      routeParams: routeParams,
      isRead: isRead ?? this.isRead,
      createdAt: createdAt,
    );
  }

  @override
  String toString() =>
      'InAppNotification(id: $id, type: $type, read: $isRead)';
}

/// [StateNotifier] managing the list of in-app notifications.
class InAppNotificationNotifier
    extends StateNotifier<List<InAppNotification>> {
  InAppNotificationNotifier() : super([]);

  /// Adds a new [notification] to the top of the list.
  void add(InAppNotification notification) {
    state = [notification, ...state];
    developer.log(
      'InAppNotificationNotifier: added "${notification.title}" '
      '(total: ${state.length})',
      name: 'Notifications',
    );
  }

  /// Marks the notification with [id] as read.
  void markAsRead(String id) {
    state = state.map((n) {
      return n.id == id ? n.copyWith(isRead: true) : n;
    }).toList();
  }

  /// Marks every notification as read.
  void markAllAsRead() {
    state = state.map((n) => n.copyWith(isRead: true)).toList();
  }

  /// Removes the notification with [id] from the list.
  void remove(String id) {
    state = state.where((n) => n.id != id).toList();
  }

  /// Clears all notifications.
  void clear() {
    state = [];
  }
}

/// Provides the [InAppNotificationNotifier] that powers the notification
/// centre screen.
final inAppNotificationsProvider =
    StateNotifierProvider<InAppNotificationNotifier, List<InAppNotification>>(
        (ref) {
  return InAppNotificationNotifier();
});
