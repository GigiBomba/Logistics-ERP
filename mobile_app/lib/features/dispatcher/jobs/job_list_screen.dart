import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../shared/widgets/status_badge.dart';
import '../home/dispatcher_providers.dart';
import 'job_detail_screen.dart';

/// Filter options for the job list.
enum _JobFilter {
  /// Show all jobs regardless of status.
  all,

  /// Filter by `in_transit` status.
  inTransit,

  /// Filter by `loading` status.
  loading,

  /// Filter by `overdue` status.
  delayed,
}

/// Maps a [_JobFilter] to its corresponding API status key.
/// Returns `null` for [_JobFilter.all] meaning no filter is applied.
String? _statusKeyForFilter(_JobFilter filter) {
  switch (filter) {
    case _JobFilter.all:
      return null;
    case _JobFilter.inTransit:
      return 'in_transit';
    case _JobFilter.loading:
      return 'loading';
    case _JobFilter.delayed:
      return 'overdue';
  }
}

/// Returns the localised label for a given filter.
String _filterLabel(_JobFilter filter, AppLocalizations loc) {
  switch (filter) {
    case _JobFilter.all:
      return loc.dispatcher_all;
    case _JobFilter.inTransit:
      return loc.transport_status_in_transit;
    case _JobFilter.loading:
      return loc.transport_status_loading;
    case _JobFilter.delayed:
      return loc.transport_status_overdue;
  }
}

/// Full-screen list of active dispatcher jobs with filter chips.
///
/// Watches [dispatcherJobsProvider] and handles loading (shimmer list),
/// error (retry), empty (EmptyState), and populated states.
///
/// A row of [ChoiceChip] filters at the top lets the user narrow results by
/// status: All | In Transit | Loading | Delayed.
///
/// Supports pull-to-refresh to invalidate the provider.
class JobListScreen extends ConsumerStatefulWidget {
  const JobListScreen({super.key});

  @override
  ConsumerState<JobListScreen> createState() => _JobListScreenState();
}

class _JobListScreenState extends ConsumerState<JobListScreen> {
  _JobFilter _selectedFilter = _JobFilter.all;

  @override
  Widget build(BuildContext context) {
    final jobsAsync = ref.watch(dispatcherJobsProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(context.loc.nav_jobs),
        centerTitle: true,
      ),
      body: jobsAsync.when(
        loading: () => _buildLoadingShimmer(context),
        error: (error, stack) => _buildError(context, ref, error),
        data: (jobs) {
          final filtered = _applyFilter(jobs, _selectedFilter);
          return Column(
            children: [
              _buildFilterChips(context),
              Expanded(
                child: filtered.isEmpty
                    ? _buildEmpty(context)
                    : _buildList(context, ref, filtered),
              ),
            ],
          );
        },
      ),
    );
  }

  /// Filters the [jobs] list by the currently selected [_selectedFilter].
  List<Map<String, dynamic>> _applyFilter(
    List<Map<String, dynamic>> jobs,
    _JobFilter filter,
  ) {
    final statusKey = _statusKeyForFilter(filter);
    if (statusKey == null) return jobs;
    return jobs.where((j) => j['status'] == statusKey).toList();
  }

  // ---------------------------------------------------------------------------
  // Filter chips
  // ---------------------------------------------------------------------------

  /// Horizontal row of [ChoiceChip] widgets for status filtering.
  Widget _buildFilterChips(BuildContext context) {
    final loc = context.loc;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.sm,
        AppSpacing.lg,
        AppSpacing.xs,
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: _JobFilter.values.map((filter) {
            final isSelected = _selectedFilter == filter;
            return Padding(
              padding: const EdgeInsets.only(right: AppSpacing.sm),
              child: ChoiceChip(
                label: Text(_filterLabel(filter, loc)),
                selected: isSelected,
                onSelected: (_) => setState(() => _selectedFilter = filter),
                labelStyle: TextStyle(
                  fontSize: 12,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                ),
                visualDensity: VisualDensity.compact,
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Loading / Error / Empty
  // ---------------------------------------------------------------------------

  /// Shimmer skeleton list (5 cards).
  Widget _buildLoadingShimmer(BuildContext context) {
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: 5,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (_, __) => const ShimmerCard(),
    );
  }

  /// Centered error panel with retry button.
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
              onPressed: () => ref.invalidate(dispatcherJobsProvider),
              icon: const Icon(LucideIcons.refreshCw, size: 18),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }

  /// Empty state when no jobs match the current filter.
  Widget _buildEmpty(BuildContext context) {
    final loc = context.loc;
    return EmptyState(
      icon: const Icon(LucideIcons.clipboardList),
      title: loc.dispatcher_noJobs,
      subtitle: _selectedFilter != _JobFilter.all
          ? loc.general_retry
          : null,
    );
  }

  // ---------------------------------------------------------------------------
  // List
  // ---------------------------------------------------------------------------

  /// Pull-to-refresh list of job cards.
  Widget _buildList(
    BuildContext context,
    WidgetRef ref,
    List<Map<String, dynamic>> jobs,
  ) {
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(dispatcherJobsProvider);
        await ref.read(dispatcherJobsProvider.future);
      },
      child: ListView.separated(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.sm,
          AppSpacing.lg,
          AppSpacing.xhuge,
        ),
        itemCount: jobs.length,
        separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
        itemBuilder: (context, index) {
          final job = jobs[index];
          return _JobCard(
            job: job,
            onTap: () {
              final id = job['id'];
              final jobId = id is int ? id : (id is String ? int.tryParse(id) ?? 0 : 0);
              _openDetail(context, jobId);
            },
          );
        },
      ),
    );
  }

  void _openDetail(BuildContext context, int jobId) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => JobDetailScreen(jobId: jobId),
      ),
    );
  }
}

/// A single job card in the dispatcher job list.
///
/// Displays load info, origin → destination, driver + vehicle plate,
/// status badge, and last-updated timestamp.
class _JobCard extends StatelessWidget {
  const _JobCard({
    required this.job,
    required this.onTap,
  });

  /// The job data map. Expected keys:
  /// `id`, `load_info`, `driver_name`, `vehicle_plate`, `status`, `origin`,
  /// `destination`, `last_updated`.
  final Map<String, dynamic> job;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final loadInfo = (job['load_info'] as String?) ?? '';
    final origin = (job['origin'] as String?) ?? '';
    final destination = (job['destination'] as String?) ?? '';
    final driverName = (job['driver_name'] as String?) ?? '';
    final vehiclePlate = (job['vehicle_plate'] as String?) ?? '';
    final status = (job['status'] as String?) ?? '';
    final lastUpdated = job['last_updated'] as String?;

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
                  loadInfo,
                  style: theme.textTheme.bodyLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              StatusBadge(statusKey: status),
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
                  '${_abbreviate(origin)} → ${_abbreviate(destination)}',
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

          // Bottom row: driver name + vehicle plate + last updated
          Row(
            children: [
              if (driverName.isNotEmpty) ...[
                Icon(
                  LucideIcons.user,
                  size: 14,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                ),
                const SizedBox(width: AppSpacing.xs),
                Flexible(
                  child: Text(
                    driverName,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
              ],
              if (vehiclePlate.isNotEmpty) ...[
                Icon(
                  LucideIcons.truck,
                  size: 14,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                ),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  vehiclePlate,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                ),
              ],
              const Spacer(),
              if (lastUpdated != null && lastUpdated.isNotEmpty)
                Text(
                  _formatTimestamp(lastUpdated),
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                    fontSize: 11,
                  ),
                ),
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
    const separators = [',', '|', ' - ', ' – '];
    for (final sep in separators) {
      final idx = location.indexOf(sep);
      if (idx > 0) return location.substring(0, idx).trim();
    }
    return location.length > 25
        ? '${location.substring(0, 22)}...'
        : location;
  }

  /// Formats an ISO-8601 timestamp into a short relative string.
  String _formatTimestamp(String isoDate) {
    final date = DateTime.tryParse(isoDate);
    if (date == null) return '';
    final delta = DateTime.now().difference(date);
    if (delta.inMinutes < 1) return 'just now';
    if (delta.inMinutes < 60) return '${delta.inMinutes}m';
    if (delta.inHours < 24) return '${delta.inHours}h';
    return '${delta.inDays}d';
  }
}
