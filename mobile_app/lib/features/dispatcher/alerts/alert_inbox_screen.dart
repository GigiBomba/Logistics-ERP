import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../home/dispatcher_providers.dart';
import 'approval_detail_screen.dart';

/// Screen displaying all alerts in an inbox-style list.
///
/// Alerts are grouped by type and shown as cards with severity-colored
/// left borders. Each card displays an icon, title, description, relative
/// time, and an unread indicator.
///
/// Features:
/// - Pull-to-refresh (also updates [unreadAlertsCountProvider])
/// - Grouping by alert type
/// - Tap to navigate to [ApprovalDetailScreen]
/// - Loading / error / empty states
class AlertInboxScreen extends ConsumerWidget {
  const AlertInboxScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loc = context.loc;
    final alertsAsync = ref.watch(dispatcherAlertsProvider);

    return alertsAsync.when(
      loading: () => const _AlertListShimmer(),
      error: (err, stack) => _ErrorRetry(
        message: err.toString(),
        onRetry: () => ref.invalidate(dispatcherAlertsProvider),
      ),
      data: (alerts) {
        if (alerts.isEmpty) {
          return const _EmptyAlerts();
        }
        return _AlertListView(
          alerts: alerts,
          onRefresh: () => _refreshAlerts(ref),
        );
      },
    );
  }

  /// Refreshes the alert list and updates the unread count.
  Future<void> _refreshAlerts(WidgetRef ref) async {
    ref.invalidate(dispatcherAlertsProvider);
    final alerts = await ref.read(dispatcherAlertsProvider.future);
    final unreadCount = alerts.where((a) => a['is_read'] != true).length;
    ref.read(unreadAlertsCountProvider.notifier).state = unreadCount;
  }
}

/// Shimmer loading placeholder for the alert list.
class _AlertListShimmer extends StatelessWidget {
  const _AlertListShimmer();

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: 5,
      separatorBuilder: (_, __) =>
          const SizedBox(height: AppSpacing.sm),
      itemBuilder: (_, __) => const ShimmerCard(),
    );
  }
}

/// Error state with retry button.
class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.error_outline,
              size: 48,
              color: AppColors.error,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              loc.general_error,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppColors.neutralText,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }
}

/// Empty state when no alerts exist.
class _EmptyAlerts extends StatelessWidget {
  const _EmptyAlerts();

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return EmptyState(
      icon: const Icon(Icons.notifications_none),
      title: loc.alert_noAlerts,
    );
  }
}

/// Scrollable alert list with pull-to-refresh.
class _AlertListView extends StatelessWidget {
  const _AlertListView({
    required this.alerts,
    required this.onRefresh,
  });

  final List<Map<String, dynamic>> alerts;
  final Future<void> Function() onRefresh;

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: onRefresh,
      child: ListView.separated(
        padding: const EdgeInsets.all(AppSpacing.lg),
        itemCount: alerts.length,
        separatorBuilder: (_, __) =>
            const SizedBox(height: AppSpacing.sm),
        itemBuilder: (context, index) =>
            _AlertCard(alert: alerts[index]),
      ),
    );
  }
}

/// A single alert card with type icon, severity border, title, description,
/// relative time, and unread indicator.
class _AlertCard extends StatelessWidget {
  const _AlertCard({required this.alert});

  final Map<String, dynamic> alert;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final type = alert['type'] as String? ?? '';
    final severity = alert['severity'] as String? ?? 'info';
    final title = alert['title'] as String? ?? '';
    final description = alert['description'] as String? ?? '';
    final isRead = alert['is_read'] as bool? ?? true;
    final createdAtStr = alert['created_at'] as String?;
    final alertId = alert['id'];

    // Parse id as int for navigation
    final int id;
    if (alertId is int) {
      id = alertId;
    } else if (alertId is String) {
      id = int.tryParse(alertId) ?? 0;
    } else {
      id = 0;
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {
            Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) =>
                    ApprovalDetailScreen(alertId: id),
              ),
            );
          },
          borderRadius: AppRadius.lgAll,
          child: AppCard(
            padding: EdgeInsets.zero,
            child: IntrinsicHeight(
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // ── Severity left border ─────────
                  Container(
                    width: 4,
                    decoration: BoxDecoration(
                      color: _severityColor(severity),
                      borderRadius: const BorderRadius.only(
                        topLeft: Radius.circular(AppRadius.lg),
                        bottomLeft:
                            Radius.circular(AppRadius.lg),
                      ),
                    ),
                  ),

                  // ── Content ──────────────────────
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.all(
                          AppSpacing.md),
                      child: Row(
                        crossAxisAlignment:
                            CrossAxisAlignment.start,
                        children: [
                          // ── Type icon ──────────────
                          Icon(
                            _typeIcon(type),
                            size: 24,
                            color: _severityColor(severity),
                          ),
                          const SizedBox(
                              width: AppSpacing.md),

                          // ── Text content ───────────
                          Expanded(
                            child: Column(
                              crossAxisAlignment:
                                  CrossAxisAlignment.start,
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Text(
                                  title,
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w600,
                                    fontSize: 14,
                                  ),
                                  maxLines: 1,
                                  overflow:
                                      TextOverflow.ellipsis,
                                ),
                                const SizedBox(
                                    height: AppSpacing.xs),
                                Text(
                                  description,
                                  style: TextStyle(
                                    fontSize: 12,
                                    color: AppColors
                                        .neutralText,
                                  ),
                                  maxLines: 1,
                                  overflow:
                                      TextOverflow.ellipsis,
                                ),
                                const SizedBox(
                                    height: AppSpacing.xs),
                                Text(
                                  _formatRelativeTime(
                                    createdAtStr,
                                    loc,
                                  ),
                                  style: TextStyle(
                                    fontSize: 11,
                                    color: AppColors
                                        .neutralText
                                        .withValues(
                                            alpha: 0.7),
                                  ),
                                ),
                              ],
                            ),
                          ),

                          // ── Unread dot ─────────────
                          if (!isRead)
                            Container(
                              width: 8,
                              height: 8,
                              margin: const EdgeInsets.only(
                                  top: 4),
                              decoration:
                                  const BoxDecoration(
                                color: AppColors.info,
                                shape: BoxShape.circle,
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  /// Returns the icon for the given alert type.
  IconData _typeIcon(String type) {
    return switch (type) {
      'delay' => Icons.access_time,
      'maintenance' => Icons.build_outlined,
      'document_expiry' => Icons.description_outlined,
      'compliance' => Icons.shield_outlined,
      _ => Icons.notifications_outlined,
    };
  }

  /// Returns the severity color for the left border.
  Color _severityColor(String severity) {
    return switch (severity) {
      'critical' || 'high' => AppColors.error,
      'medium' => AppColors.warning,
      'low' || 'info' => AppColors.info,
      _ => AppColors.neutralText,
    };
  }

  /// Formats a relative time string from an ISO-8601 timestamp.
  /// Falls back to a short date format when the timestamp is older than 24h.
  String _formatRelativeTime(
    String? isoString,
    AppLocalizations loc,
  ) {
    if (isoString == null) return '';
    final date = DateTime.tryParse(isoString);
    if (date == null) return '';

    final now = DateTime.now();
    final diff = now.difference(date);

    if (diff.inMinutes < 1) return loc.general_justNow;
    if (diff.inMinutes < 60) {
      return '${diff.inMinutes} min';
    }
    if (diff.inHours < 2) return loc.general_hourAgo;
    if (diff.inHours < 24) {
      return '${diff.inHours} h';
    }

    final dateFormat = DateFormat.yMd(loc.locale.languageCode);
    return dateFormat.format(date);
  }
}
