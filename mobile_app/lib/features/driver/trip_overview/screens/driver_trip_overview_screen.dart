import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../../core/auth/auth_providers.dart';
import '../../../../core/i18n/app_localizations.dart';
import '../../../../core/providers/driver_providers.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_spacing.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../../../shared/widgets/empty_state.dart';
import '../../../../shared/widgets/shimmer_loader.dart';
import '../../../../shared/widgets/staleness_indicator.dart';
import '../../../../shared/widgets/status_badge.dart';
import '../../../../shared/widgets/transport_status_actions.dart';
import '../../models/driver_trip_overview.dart';
import '../providers/trip_overview_providers.dart';
import '../providers/trip_overview_state.dart';

/// Maps a [TripStatus] enum to the string key expected by
/// [TransportStatusActions] and [StatusBadge].
String _statusKey(TripStatus? status) => switch (status) {
      TripStatus.planned => 'planned',
      TripStatus.loading => 'loading',
      TripStatus.inTransit => 'in_transit',
      TripStatus.delivered => 'delivered',
      TripStatus.cancelled => 'cancelled',
      null => '',
    };

/// Driver's trip overview screen — shows assigned transport summary, ETA,
/// elapsed time, and status transition buttons.
///
/// Implements all four states: loading (shimmer), error (retry), empty
/// (no active trip), and data (full overview).
class DriverTripOverviewScreen extends ConsumerWidget {
  const DriverTripOverviewScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final overviewAsync = ref.watch(tripOverviewProvider);
    final loc = context.loc;

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(tripOverviewProvider);
        await ref.read(tripOverviewProvider.future);
      },
      child: overviewAsync.when(
        loading: () => const _LoadingShimmer(),
        error: (error, stack) => _ErrorView(
          message: error.toString(),
          onRetry: () => ref.invalidate(tripOverviewProvider),
        ),
        data: (overview) => overview.transportId == null
            ? _EmptyTripView(
                title: loc.driverOverview_emptyState,
                subtitle: loc.driverOverview_emptyStateSubtitle,
              )
            : _TripOverviewContent(overview: overview),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Loading shimmer
// ---------------------------------------------------------------------------

class _LoadingShimmer extends StatelessWidget {
  const _LoadingShimmer();

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      physics: AlwaysScrollableScrollPhysics(),
      padding: EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ShimmerLoader(child: _ShimmerBlock(height: 100, widthFactor: 1)),
          SizedBox(height: AppSpacing.lg),
          ShimmerLoader(child: _ShimmerBlock(height: 80, widthFactor: 1)),
          SizedBox(height: AppSpacing.lg),
          ShimmerLoader(child: _ShimmerBlock(height: 120, widthFactor: 1)),
        ],
      ),
    );
  }
}

class _ShimmerBlock extends StatelessWidget {
  final double height;
  final double widthFactor;
  const _ShimmerBlock({required this.height, this.widthFactor = 1});

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: widthFactor,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(AppRadius.lg),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Error view
// ---------------------------------------------------------------------------

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(LucideIcons.alertCircle, size: 48, color: AppColors.error),
            const SizedBox(height: AppSpacing.lg),
            Text(loc.general_error, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: AppSpacing.sm),
            Text(message, textAlign: TextAlign.center, maxLines: 3),
            const SizedBox(height: AppSpacing.lg),
            OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(LucideIcons.refreshCw, size: 18),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Empty state — no active trip
// ---------------------------------------------------------------------------

class _EmptyTripView extends StatelessWidget {
  final String title;
  final String subtitle;
  const _EmptyTripView({required this.title, required this.subtitle});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: EmptyState(
        icon: const Icon(LucideIcons.truck, size: 56),
        title: title,
        subtitle: subtitle,
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Trip overview content
// ---------------------------------------------------------------------------

class _TripOverviewContent extends ConsumerStatefulWidget {
  final DriverTripOverview overview;
  const _TripOverviewContent({required this.overview});

  @override
  ConsumerState<_TripOverviewContent> createState() =>
      _TripOverviewContentState();
}

class _TripOverviewContentState extends ConsumerState<_TripOverviewContent> {
  final Set<String> _loadingStatuses = {};

  Future<void> _updateStatus(String newStatus) async {
    final isOffline = ref.read(isOfflineProvider);
    if (isOffline) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(context.loc.general_offline),
          backgroundColor: AppColors.warning,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    setState(() => _loadingStatuses.add(newStatus));
    try {
      final endpoints = ref.read(driverEndpointsProvider);
      await endpoints.updateStatus(
        widget.overview.transportId!,
        newStatus,
      );
      ref.invalidate(tripOverviewProvider);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(context.loc.transport_statusUpdated),
          backgroundColor: AppColors.success,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${context.loc.general_error}: $e'),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) setState(() => _loadingStatuses.remove(newStatus));
    }
  }

  @override
  Widget build(BuildContext context) {
    // Trigger rebuild every second so the elapsed-time display stays current.
    ref.watch(elapsedTimerProvider);

    final o = widget.overview;
    final loc = context.loc;
    final theme = Theme.of(context);
    final isOffline = ref.watch(isOfflineProvider);

    return SingleChildScrollView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // ── Transport summary card ──
          AppCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  StatusBadge(statusKey: _statusKey(o.status)),
                  const SizedBox(height: AppSpacing.md),
                  if (o.loadInfo != null)
                    Text(
                      o.loadInfo!,
                      style: theme.textTheme.titleLarge
                          ?.copyWith(fontWeight: FontWeight.bold),
                    ),
                  if (o.loadInfo != null) const SizedBox(height: AppSpacing.sm),
                  if (o.origin != null && o.destination != null)
                    Row(
                      children: [
                        Icon(LucideIcons.mapPin,
                            size: 16, color: AppColors.success),
                        const SizedBox(width: AppSpacing.xs),
                        Expanded(
                          child: Text(
                            '${o.origin} → ${o.destination}',
                            style: theme.textTheme.bodyMedium,
                          ),
                        ),
                      ],
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ── ETA card ──
          AppCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Row(
                children: [
                  Icon(LucideIcons.clock, size: 24, color: AppColors.accent),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(loc.transport_eta,
                            style: theme.textTheme.titleMedium),
                        const SizedBox(height: AppSpacing.xs),
                        _buildEtaText(o, theme),
                      ],
                    ),
                  ),
                  if (o.etaConfidence == EtaConfidence.stale)
                    StalenessIndicator(lastUpdated: o.statusSince),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ── Elapsed time card ──
          AppCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Row(
                children: [
                  Icon(LucideIcons.timer, size: 24, color: AppColors.info),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(loc.transport_elapsedTime,
                            style: theme.textTheme.titleMedium),
                        const SizedBox(height: AppSpacing.xs),
                        Text(
                          _formatElapsed(o.elapsed),
                          style: theme.textTheme.headlineSmall
                              ?.copyWith(fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.lg),

          // ── Status actions ──
          if (!TransportStatusActions.isTerminal(_statusKey(o.status)))
            AppCard(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      loc.transport_updateStatus,
                      style: theme.textTheme.titleMedium
                          ?.copyWith(fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: AppSpacing.md),
                    if (isOffline)
                      Padding(
                        padding:
                            const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: Row(
                          children: [
                            Icon(Icons.cloud_off,
                                size: 14, color: AppColors.warning),
                            const SizedBox(width: AppSpacing.xs),
                            Text(
                              loc.general_offline,
                              style: const TextStyle(
                                  fontSize: 12,
                                  color: AppColors.warning),
                            ),
                          ],
                        ),
                      ),
                    TransportStatusButtons(
                      currentStatus: _statusKey(o.status),
                      loadingStatuses: _loadingStatuses,
                      isOffline: isOffline,
                      onStatusUpdate: _updateStatus,
                      labelResolver: (status) {
                        switch (status) {
                          case 'loading':
                            return loc.transport_action_startLoading;
                          case 'in_transit':
                            return loc.transport_action_depart;
                          case 'delivered':
                            return loc.transport_action_markDelivered;
                          case 'overdue':
                            return loc.transport_action_reportDelay;
                          default:
                            return status;
                        }
                      },
                      noActionsText: loc.transport_action_noActions,
                    ),
                  ],
                ),
              ),
            ),

          const SizedBox(height: AppSpacing.xhuge),
        ],
      ),
    );
  }

  Widget _buildEtaText(DriverTripOverview o, ThemeData theme) {
    switch (o.etaConfidence) {
      case EtaConfidence.live:
        if (o.eta == null) {
          return Text('-', style: theme.textTheme.bodyLarge);
        }
        return Text(
          '${o.eta!.hour.toString().padLeft(2, '0')}:${o.eta!.minute.toString().padLeft(2, '0')}',
          style: theme.textTheme.headlineSmall
              ?.copyWith(fontWeight: FontWeight.bold),
        );
      case EtaConfidence.stale:
        if (o.eta == null) {
          return Text('-', style: theme.textTheme.bodyLarge);
        }
        return Text(
          '${o.eta!.hour.toString().padLeft(2, '0')}:${o.eta!.minute.toString().padLeft(2, '0')}',
          style: theme.textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.bold,
            color: AppColors.warning,
          ),
        );
      case EtaConfidence.unavailable:
        return Text(
          'ETA unavailable',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
          ),
        );
    }
  }

  String _formatElapsed(Duration? elapsed) {
    if (elapsed == null) return '-';
    final hours = elapsed.inHours;
    final minutes = elapsed.inMinutes.remainder(60);
    if (hours > 0) return '${hours}h ${minutes}m';
    return '${minutes}m';
  }
}
