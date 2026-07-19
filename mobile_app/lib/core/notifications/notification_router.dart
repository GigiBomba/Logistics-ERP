/// Enum of known deep-link destinations that a push notification can lead to.
enum NotificationRoute {
  /// Navigates to the transport detail screen.
  transportDetail,

  /// Navigates to a message thread / chat screen.
  messageThread,

  /// Navigates to an alert detail or approval screen.
  alertDetail,

  /// Navigates to the driver home screen.
  driverHome,

  /// Navigates to the dispatcher home screen.
  dispatcherHome,
}

/// Stateless router that resolves push notification data to a specific screen
/// destination and its associated parameters.
///
/// ### Usage
///
/// ```dart
/// final route = NotificationRouter.resolveRoute(message.data);
/// final params = NotificationRouter.resolveParams(message.data);
///
/// if (route == NotificationRoute.transportDetail) {
///   navigator.pushNamed('/transport', arguments: params);
/// }
/// ```
class NotificationRouter {
  NotificationRouter._();

  /// Inspects the `type` field in [data] and returns the matching
  /// [NotificationRoute], or `null` when the type is unknown.
  ///
  /// ### Recognised types
  ///
  /// | `type` value           | Returned route               |
  /// |------------------------|------------------------------|
  /// | `new_assignment`       | [NotificationRoute.transportDetail] |
  /// | `status_change`        | [NotificationRoute.transportDetail] |
  /// | `new_message`          | [NotificationRoute.messageThread]   |
  /// | `alert`                | [NotificationRoute.alertDetail]     |
  /// | `approval`             | [NotificationRoute.alertDetail]     |
  /// | `check_in_expiring`    | `null` (no navigation)              |
  static NotificationRoute? resolveRoute(Map<String, dynamic> data) {
    final type = data['type'] as String?;
    switch (type) {
      case 'new_assignment':
      case 'status_change':
        return NotificationRoute.transportDetail;
      case 'new_message':
        return NotificationRoute.messageThread;
      case 'alert':
      case 'approval':
        return NotificationRoute.alertDetail;
      case 'dispatcher_home':
        return NotificationRoute.dispatcherHome;
      case 'driver_home':
        return NotificationRoute.driverHome;
      default:
        // Unknown / data-only notifications yield no navigation.
        return null;
    }
  }

  /// Extracts navigation parameters from the notification [data].
  ///
  /// The returned map contains only the keys that are present and non-null:
  /// - `transportId`
  /// - `threadId`
  /// - `alertId`
  /// - `driverId`
  ///
  /// These can be passed as route arguments when pushing a named route.
  static Map<String, String>? resolveParams(Map<String, dynamic> data) {
    final params = <String, String>{
      if (data['transport_id'] != null) 'transportId': data['transport_id'].toString(),
      if (data['thread_id'] != null) 'threadId': data['thread_id'].toString(),
      if (data['alert_id'] != null) 'alertId': data['alert_id'].toString(),
      if (data['driver_id'] != null) 'driverId': data['driver_id'].toString(),
    };
    return params.isNotEmpty ? params : null;
  }
}
