import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/transport.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../shared/widgets/status_badge.dart';
import '../home/driver_providers.dart';
import 'transport_detail_screen.dart';

/// Full-screen list of transports assigned to the current driver.
///
/// Watches [transportsProvider] and handles loading (shimmer list),
/// error (retry), empty (EmptyState), and populated states.
///
/// Supports pull-to-refresh to invalidate the provider.
class TransportListScreen extends ConsumerWidget {
  const TransportListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final transportsAsync = ref.watch(transportsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(context.loc.nav_transports),
        centerTitle: true,
      ),
      body: transportsAsync.when(
        loading: () => _buildLoadingShimmer(context),
        error: (error, stack) => _buildError(context, ref, error),
        data: (transports) => transports.isEmpty
            ? _buildEmpty(context)
            : _buildList(context, ref, transports),
      ),
    );
  }

  /// Shimmer skeleton list (5 cards).
  Widget _buildLoadingShimmer(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: 5,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (_, __) => const ShimmerCard(),
    );
  }

  /// Centered error panel with retry.
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
              onPressed: () => ref.invalidate(transportsProvider),
              icon: const Icon(LucideIcons.refreshCw, size: 18),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }

  /// Empty state when no transports are assigned.
  Widget _buildEmpty(BuildContext context) {
    final loc = context.loc;
    return EmptyState(
      icon: const Icon(LucideIcons.truck),
      title: loc.driver_noTransports,
      subtitle: loc.transport_navigate,
    );
  }

  /// Pull-to-refresh list of transport cards.
  Widget _buildList(
    BuildContext context,
    WidgetRef ref,
    List<Transport> transports,
  ) {
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(transportsProvider);
        await ref.read(transportsProvider.future);
      },
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.sm,
          AppSpacing.lg,
          AppSpacing.xhuge,
        ),
        itemCount: transports.length,
        separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
        itemBuilder: (context, index) {
          final transport = transports[index];
          return _TransportCard(
            transport: transport,
            onTap: () => _openDetail(context, transport.id),
          );
        },
      ),
    );
  }

  void _openDetail(BuildContext context, String transportId) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => TransportDetailScreen(transportId: transportId),
      ),
    );
  }
}

/// A single transport card in the list.
class _TransportCard extends StatelessWidget {
  const _TransportCard({
    required this.transport,
    required this.onTap,
  });

  final Transport transport;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final t = transport;

    return AppCard(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Top row: load info + status badge
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  t.loadInfo,
                  style: theme.textTheme.bodyLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              StatusBadge(statusKey: t.status),
            ],
          ),
          const SizedBox(height: AppSpacing.md),

          // Origin → Destination
          Row(
            children: [
              Icon(
                LucideIcons.arrowRightLeft,
                size: 14,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(
                  '${_abbreviate(t.origin)} → ${_abbreviate(t.destination)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),

          // Bottom row: date + vehicle plate
          Row(
            children: [
              Icon(
                LucideIcons.calendar,
                size: 14,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
              ),
              const SizedBox(width: AppSpacing.xs),
              Text(
                t.scheduledDate != null
                    ? '${t.scheduledDate!.day}.${t.scheduledDate!.month}.${t.scheduledDate!.year}'
                    : '--',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                ),
              ),
              if (t.vehiclePlate != null && t.vehiclePlate!.isNotEmpty) ...[
                const SizedBox(width: AppSpacing.lg),
                Icon(
                  LucideIcons.truck,
                  size: 14,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                ),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  t.vehiclePlate!,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  /// Shorten a location string to a city-level portion (before first comma
  /// or pipe).
  String _abbreviate(String location) {
    if (location.isEmpty) return location;
    // Try to extract the city part (before comma, dash, or pipe).
    final separators = [',', '|', ' - ', ' – '];
    for (final sep in separators) {
      final idx = location.indexOf(sep);
      if (idx > 0) return location.substring(0, idx).trim();
    }
    // If the string is very long, truncate.
    return location.length > 25
        ? '${location.substring(0, 22)}...'
        : location;
  }
}
