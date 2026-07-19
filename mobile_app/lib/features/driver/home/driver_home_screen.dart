import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/message.dart';
import '../../../shared/models/transport.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../shared/widgets/staleness_indicator.dart';
import '../../../shared/widgets/status_badge.dart';
import '../messages/message_list_screen.dart';
import '../transports/transport_detail_screen.dart';
import '../transports/transport_list_screen.dart';
import 'driver_providers.dart';

/// The driver's "My Day" home screen — a scrollable dashboard showing a
/// summary of the current day's work: active-transport counts, next stop,
/// assigned transports, and recent messages.
///
/// Watches [myDayProvider] and handles loading (shimmer), error (retry),
/// and empty states.
class DriverHomeScreen extends ConsumerWidget {
  const DriverHomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final myDayAsync = ref.watch(myDayProvider);

    return myDayAsync.when(
      loading: () => _buildLoadingShimmer(context),
      error: (error, stack) => _buildError(context, ref, error),
      data: (data) => _buildDashboard(context, ref, data),
    );
  }

  /// Shimmer skeleton that mimics the dashboard layout while data loads.
  Widget _buildLoadingShimmer(BuildContext context) {
    final theme = Theme.of(context);
    return SingleChildScrollView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header shimmer
          _ShimmerBlock(height: 20, width: 0.4),
          const SizedBox(height: AppSpacing.md),
          _ShimmerBlock(height: 14, width: 0.25),
          const SizedBox(height: AppSpacing.lg),
          // Summary cards shimmer row
          SizedBox(
            height: 100,
            child: Row(
              children: const [
                Expanded(child: ShimmerLoader(child: _SummaryCardSkeleton())),
                SizedBox(width: AppSpacing.sm),
                Expanded(child: ShimmerLoader(child: _SummaryCardSkeleton())),
                SizedBox(width: AppSpacing.sm),
                Expanded(child: ShimmerLoader(child: _SummaryCardSkeleton())),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.xxl),
          // Section header shimmer
          _ShimmerBlock(height: 16, width: 0.45),
          const SizedBox(height: AppSpacing.md),
          // Transport card shimmers
          ...List.generate(3, (_) => const Padding(
            padding: EdgeInsets.only(bottom: AppSpacing.sm),
            child: ShimmerCard(),
          )),
          const SizedBox(height: AppSpacing.lg),
          _ShimmerBlock(height: 16, width: 0.35),
          const SizedBox(height: AppSpacing.md),
          // Message shimmer
          const ShimmerCard(),
        ],
      ),
    );
  }

  /// Centered error panel with a retry button.
  Widget _buildError(BuildContext context, WidgetRef ref, Object error) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              LucideIcons.alertCircle,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              loc.general_error,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Theme.of(context).colorScheme.error,
                  ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              error.toString(),
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context)
                        .colorScheme
                        .onSurface
                        .withValues(alpha: 0.5),
                  ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: AppSpacing.lg),
            FilledButton.icon(
              onPressed: () => ref.invalidate(myDayProvider),
              icon: const Icon(LucideIcons.refreshCw, size: 18),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }

  /// Full dashboard when data is available.
  Widget _buildDashboard(
      BuildContext context, WidgetRef ref, Map<String, dynamic> data) {
    final loc = context.loc;
    final theme = Theme.of(context);
    final today = DateTime.now();

    // Extract data from myDay response with safe fallbacks.
    final activeTransports = (data['activeTransports'] as num?)?.toInt() ?? 0;
    final nextStopMap = data['nextStop'] as Map<String, dynamic>?;
    final transportsList = (data['transports'] as List<dynamic>?)
            ?.map((j) => j is Map<String, dynamic> ? Transport.fromJson(j) : null)
            .whereType<Transport>().toList() ??
        <Transport>[];
    final messagesList = (data['messages'] as List<dynamic>?)
            ?.map((j) => Message.fromJson(j as Map<String, dynamic>))
            .toList() ??
        <Message>[];
    final lastUpdated = DateTime.tryParse(data['lastUpdated']?.toString() ?? '');

    // Unread messages count from the auth-level provider.
    final unreadCount = ref.watch(unreadMessagesCountProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(myDayProvider);
        // Wait for the provider to settle.
        await ref.read(myDayProvider.future);
      },
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header row with title + staleness ─────────────
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        loc.driver_myDay,
                        style: theme.textTheme.headlineSmall?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        '${today.day}.${today.month}.${today.year}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.5),
                        ),
                      ),
                    ],
                  ),
                ),
                StalenessIndicator(
                  lastUpdated: lastUpdated,
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),

            // ── Summary cards row ─────────────────────────────
            SizedBox(
              height: 116,
              child: Row(
                children: [
                  Expanded(
                    child: _SummaryCard(
                      icon: LucideIcons.truck,
                      label: loc.driver_assignedTransports,
                      value: '$activeTransports',
                      color: AppColors.accent,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: _SummaryCard(
                      icon: LucideIcons.mapPin,
                      label: loc.transport_route,
                      value: nextStopMap?['destination'] as String? ??
                          '--',
                      color: AppColors.info,
                    ),
                  ),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: _SummaryCard(
                      icon: LucideIcons.messageSquare,
                      label: loc.nav_messages,
                      value: '$unreadCount',
                      color: AppColors.warning,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xxl),

            // ── Assigned transports section ───────────────────
            _SectionHeader(
              title: loc.driver_assignedTransports,
              count: transportsList.length,
            ),
            const SizedBox(height: AppSpacing.md),
            if (transportsList.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
                child: EmptyState(
                  icon: const Icon(LucideIcons.packageOpen),
                  title: loc.driver_noTransports,
                ),
              )
            else
              // Preview first 4 transports.
              ...List.generate(
                transportsList.length > 4 ? 4 : transportsList.length,
                (i) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: _TransportPreviewCard(
                    transport: transportsList[i],
                    onTap: () => _openTransportDetail(context, transportsList[i].id),
                  ),
                ),
              ),
            if (transportsList.length > 4) ...[
              const SizedBox(height: AppSpacing.xs),
              // "View all" link
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const TransportListScreen(),
                      ),
                    );
                  },
                  icon: const Icon(LucideIcons.arrowRight, size: 16),
                  label: Text(loc.nav_transports),
                ),
              ),
            ],

            const SizedBox(height: AppSpacing.lg),

            // ── Latest messages section ───────────────────────
            _SectionHeader(
              title: loc.nav_messages,
              count: messagesList.length,
            ),
            const SizedBox(height: AppSpacing.md),
            if (messagesList.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg),
                child: EmptyState(
                  icon: const Icon(LucideIcons.messageSquareOff),
                  title: loc.message_noMessages,
                ),
              )
            else
              // Preview first 2 messages.
              ...List.generate(
                messagesList.length > 2 ? 2 : messagesList.length,
                (i) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: _MessagePreviewCard(message: messagesList[i]),
                ),
              ),
            if (messagesList.length > 2)
              Align(
                alignment: Alignment.centerLeft,
                child: TextButton.icon(
                  onPressed: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => const MessageListScreen(),
                      ),
                    );
                  },
                  icon: const Icon(LucideIcons.arrowRight, size: 16),
                  label: Text(loc.nav_messages),
                ),
              ),

            // Bottom spacing for nav bar clearance.
            const SizedBox(height: AppSpacing.xhuge),
          ],
        ),
      ),
    );
  }

  void _openTransportDetail(BuildContext context, String transportId) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TransportDetailScreen(transportId: transportId),
      ),
    );
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// Private helper widgets
// ═════════════════════════════════════════════════════════════════════════════

/// A summary stat card for the top row (active transports, next stop, etc.).
class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.color,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 20, color: color),
          const SizedBox(height: AppSpacing.sm),
          Text(
            value,
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: color,
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(
            label,
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
            ),
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
          ),
        ],
      ),
    );
  }
}

/// Skeleton placeholder for [_SummaryCard] during loading.
class _SummaryCardSkeleton extends StatelessWidget {
  const _SummaryCardSkeleton();

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(width: 20, height: 20, color: Colors.white),
            const SizedBox(height: AppSpacing.sm),
            Container(
              width: 40,
              height: 18,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Container(
              width: 60,
              height: 12,
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(4),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// A generic shimmer block used in the loading skeleton.
class _ShimmerBlock extends StatelessWidget {
  const _ShimmerBlock({required this.height, required this.width});

  final double height;
  final double width;

  @override
  Widget build(BuildContext context) {
    return ShimmerLoader(
      child: FractionallySizedBox(
        widthFactor: width,
        child: Container(
          height: height,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(AppRadius.sm),
          ),
        ),
      ),
    );
  }
}

/// Section header with an optional count badge.
class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, this.count});

  final String title;
  final int? count;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Text(
          title,
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
        if ((count ?? 0) > 0) ...[
          const SizedBox(width: AppSpacing.sm),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.sm,
              vertical: AppSpacing.xs,
            ),
            decoration: BoxDecoration(
              color: AppColors.accentSubtle,
              borderRadius: BorderRadius.circular(AppRadius.pill),
            ),
            child: Text(
              '$count',
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: AppColors.accent,
              ),
            ),
          ),
        ],
      ],
    );
  }
}

/// Compact transport card used in the dashboard preview list.
class _TransportPreviewCard extends StatelessWidget {
  const _TransportPreviewCard({
    required this.transport,
    required this.onTap,
  });

  final Transport transport;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return AppCard(
      onTap: onTap,
      child: Row(
        children: [
          // Leading indicator
          Container(
            width: 4,
            height: 48,
            decoration: BoxDecoration(
              color: _statusColor(transport.status),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          // Content
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  transport.loadInfo,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: AppSpacing.xs),
                Row(
                  children: [
                    Icon(
                      LucideIcons.mapPin,
                      size: 12,
                      color: theme.colorScheme.onSurface
                          .withValues(alpha: 0.4),
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Expanded(
                      child: Text(
                        transport.destination,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.6),
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          StatusBadge(statusKey: transport.status),
        ],
      ),
    );
  }

  Color _statusColor(String status) {
    switch (status) {
      case 'delivered':
        return AppColors.success;
      case 'planned':
        return AppColors.accent;
      case 'in_transit':
      case 'in_progress':
        return AppColors.warning;
      case 'loading':
        return AppColors.tertiary;
      case 'cancelled':
        return AppColors.neutralText;
      case 'overdue':
        return AppColors.error;
      case 'invoiced':
      case 'paid':
        return AppColors.info;
      default:
        return AppColors.neutralText;
    }
  }
}

/// Compact message preview card for the dashboard.
class _MessagePreviewCard extends StatelessWidget {
  const _MessagePreviewCard({required this.message});

  final Message message;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final timeStr = _formatTime(message.timestamp);

    return AppCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: AppColors.accentSubtle,
              borderRadius: BorderRadius.circular(AppRadius.pill),
            ),
            child: Center(
              child: Text(
                message.senderName.isNotEmpty
                    ? message.senderName[0].toUpperCase()
                    : '?',
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  color: AppColors.accent,
                  fontSize: 14,
                ),
              ),
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        message.senderName,
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                      timeStr,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurface
                            .withValues(alpha: 0.4),
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  message.text,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface
                        .withValues(alpha: 0.6),
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          if (!message.isRead)
            Container(
              width: 8,
              height: 8,
              decoration: const BoxDecoration(
                color: AppColors.accent,
                shape: BoxShape.circle,
              ),
            ),
        ],
      ),
    );
  }

  String _formatTime(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m';
    if (diff.inHours < 24) return '${diff.inHours}h';
    return '${dt.day}/${dt.month}';
  }
}


