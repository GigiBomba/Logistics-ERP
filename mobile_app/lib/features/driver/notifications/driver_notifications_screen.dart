import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/notifications/notification_providers.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';

/// Notification centre screen for the driver.
///
/// Displays in-app notifications grouped by date (Today, Yesterday, Older).
/// Each notification shows a type-based icon, title, body preview, timestamp,
/// and a read/unread dot indicator. Tap marks the notification as read and
/// optionally navigates.
///
/// Uses [inAppNotificationsProvider] from the notification layer.
class DriverNotificationsScreen extends ConsumerWidget {
  const DriverNotificationsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifications = ref.watch(inAppNotificationsProvider);
    final loc = context.loc;

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.nav_notifications),
        actions: [
          if (notifications.any((n) => !n.isRead))
            IconButton(
              icon: const Icon(LucideIcons.checkCheck),
              tooltip: 'Mark all as read',
              onPressed: () {
                ref
                    .read(inAppNotificationsProvider.notifier)
                    .markAllAsRead();
              },
            ),
        ],
      ),
      body: notifications.isEmpty
          ? _buildEmptyState(loc)
          : _buildNotificationList(context, ref, notifications),
    );
  }

  /// Empty state with a bell icon.
  Widget _buildEmptyState(AppLocalizations loc) {
    return const EmptyState(
      icon: Icon(LucideIcons.bell),
      title: 'No notifications',
      subtitle: 'You\'re all caught up!',
    );
  }

  /// Builds the grouped notification list with pull-to-refresh.
  Widget _buildNotificationList(
    BuildContext context,
    WidgetRef ref,
    List<InAppNotification> notifications,
  ) {
    final grouped = _groupByDate(notifications);
    final loc = context.loc;

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(inAppNotificationsProvider);
      },
      child: ListView(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.sm,
        ),
        children: [
          for (final entry in grouped.entries) ...[
            _SectionHeader(label: entry.key),
            const SizedBox(height: AppSpacing.xs),
            ...entry.value.map(
              (notification) => _NotificationItem(
                notification: notification,
                onTap: () {
                  ref
                      .read(inAppNotificationsProvider.notifier)
                      .markAsRead(notification.id);
                  // Future: navigate using notification.routeParams
                },
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
          ],
        ],
      ),
    );
  }

  /// Groups notifications by date category: Today, Yesterday, Older.
  Map<String, List<InAppNotification>> _groupByDate(
    List<InAppNotification> notifications,
  ) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    final grouped = <String, List<InAppNotification>>{};

    for (final n in notifications) {
      final date = DateTime(
        n.createdAt.year,
        n.createdAt.month,
        n.createdAt.day,
      );
      String key;
      if (date == today) {
        key = 'Today';
      } else if (date == yesterday) {
        key = 'Yesterday';
      } else {
        key = 'Older';
      }
      grouped.putIfAbsent(key, () => []).add(n);
    }

    // Maintain a consistent order.
    final ordered = <String, List<InAppNotification>>{};
    for (final key in ['Today', 'Yesterday', 'Older']) {
      if (grouped.containsKey(key)) {
        ordered[key] = grouped[key]!;
      }
    }
    return ordered;
  }
}

/// Header label for a date group section.
class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(
        top: AppSpacing.sm,
        bottom: AppSpacing.xs,
      ),
      child: Text(
        label,
        style: theme.textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w600,
          color: AppColors.textSecondaryLight,
        ),
      ),
    );
  }
}

/// A single notification list item.
class _NotificationItem extends StatelessWidget {
  const _NotificationItem({
    required this.notification,
    required this.onTap,
  });

  final InAppNotification notification;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final typeStyle = _typeStyle(notification.type);

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xs),
      child: AppCard(
        onTap: onTap,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Icon
            Container(
              height: 40,
              width: 40,
              decoration: BoxDecoration(
                color: typeStyle.color.withValues(alpha: 0.12),
                borderRadius: AppRadius.lgAll,
              ),
              child: Icon(
                typeStyle.icon,
                size: 20,
                color: typeStyle.color,
              ),
            ),
            const SizedBox(width: AppSpacing.md),
            // Title + body
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          notification.title,
                          style: theme.textTheme.bodyMedium?.copyWith(
                            fontWeight: notification.isRead
                                ? FontWeight.w400
                                : FontWeight.w600,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      if (!notification.isRead)
                        Container(
                          height: 8,
                          width: 8,
                          margin: const EdgeInsets.only(left: AppSpacing.sm),
                          decoration: const BoxDecoration(
                            color: AppColors.accent,
                            shape: BoxShape.circle,
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 2),
                  Text(
                    notification.body,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondaryLight,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: AppSpacing.xs),
                  Text(
                    _formatTimestamp(notification.createdAt),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: AppColors.neutralText,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Formats the notification timestamp as a relative or absolute string.
  String _formatTimestamp(DateTime dateTime) {
    final now = DateTime.now();
    final diff = now.difference(dateTime);

    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';

    return '${dateTime.day.toString().padLeft(2, '0')}.'
        '${dateTime.month.toString().padLeft(2, '0')}.'
        '${dateTime.year}';
  }
}

/// Resolved icon and colour for a given notification type.
({IconData icon, Color color}) _typeStyle(String type) {
  return switch (type) {
    'new_assignment' => (icon: LucideIcons.truck, color: AppColors.info),
    'schedule_change' =>
      (icon: LucideIcons.calendar, color: AppColors.warning),
    'new_message' => (icon: LucideIcons.messageSquare, color: Colors.indigo),
    'alert' => (icon: LucideIcons.alertTriangle, color: AppColors.error),
    _ => (icon: LucideIcons.bell, color: AppColors.neutralText),
  };
}
