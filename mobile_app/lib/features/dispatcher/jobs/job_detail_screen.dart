import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart' as app_button;
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/confirmation_dialog.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../shared/widgets/status_badge.dart';
import '../home/dispatcher_providers.dart';
import 'job_providers.dart';

/// Full-screen detail view for a single dispatcher job.
///
/// Displays load information, route details, current status with a
/// "Mark Delivered" action, an info grid, and quick actions (reassign driver,
/// message driver).
///
/// The reassign flow opens a bottom sheet showing available drivers from
/// [dispatcherDriversProvider]. After confirmation, it calls
/// [DispatcherEndpoints.reassignTransport] and refreshes the job data.
class JobDetailScreen extends ConsumerStatefulWidget {
  /// The job identifier to load.
  final int jobId;

  const JobDetailScreen({super.key, required this.jobId});

  @override
  ConsumerState<JobDetailScreen> createState() => _JobDetailScreenState();
}

class _JobDetailScreenState extends ConsumerState<JobDetailScreen> {
  /// Tracks whether the "Mark Delivered" action is loading.
  bool _markDeliveredLoading = false;

  /// Tracks whether a reassign operation is in progress.
  bool _reassigning = false;

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /// Placeholder for marking a job as delivered.
  ///
  /// TODO: Implement once the dispatcher status-update endpoint is available.
  Future<void> _markDelivered() async {
    setState(() => _markDeliveredLoading = true);
    try {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${context.loc.dispatcher_markDelivered} — TODO'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) {
        setState(() => _markDeliveredLoading = false);
      }
    }
  }

  /// Placeholder for messaging the driver.
  ///
  /// TODO: Navigate to a chat screen once implemented.
  void _messageDriver(String? driverName) {
    if (!mounted) return;
    final name = driverName ?? context.loc.dispatcher_driver;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Message to $name — coming soon'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Reassign flow
  // ---------------------------------------------------------------------------

  /// Opens a bottom sheet listing available drivers for reassignment.
  ///
  /// Tapping a driver triggers a confirmation dialog before calling the API.
  Future<void> _showReassignSheet() async {
    final drivers = ref.read(dispatcherDriversProvider);
    final loc = context.loc;

    await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.xl)),
      ),
      builder: (sheetContext) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.lg,
            AppSpacing.lg,
            AppSpacing.lg,
            AppSpacing.xxxl,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Title
              Text(
                loc.dispatcher_reassign,
                style: Theme.of(sheetContext)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: AppSpacing.md),
              const Divider(),
              const SizedBox(height: AppSpacing.sm),

              // Driver list
              drivers.when(
                loading: () => const Center(
                  child: Padding(
                    padding: EdgeInsets.all(AppSpacing.xxl),
                    child: CircularProgressIndicator(),
                  ),
                ),
                error: (error, stack) => Center(
                  child: Text(
                    '$error',
                    style: Theme.of(sheetContext).textTheme.bodySmall,
                  ),
                ),
                data: (driverList) {
                  if (driverList.isEmpty) {
                    return Padding(
                      padding: const EdgeInsets.all(AppSpacing.xxl),
                      child: Center(
                        child: Text(
                          'No drivers available',
                          style: Theme.of(sheetContext).textTheme.bodyMedium,
                        ),
                      ),
                    );
                  }

                  return SizedBox(
                    height: MediaQuery.of(sheetContext).size.height * 0.4,
                    child: ListView.separated(
                      itemCount: driverList.length,
                      separatorBuilder: (_, __) => const Divider(height: 1),
                      itemBuilder: (_, index) {
                        final driver = driverList[index];
                        final driverId =
                            (driver['id'] ?? '').toString();
                        final driverName =
                            (driver['name'] as String?) ?? '—';
                        final driverPlate =
                            (driver['vehicle_plate'] as String?);

                        return ListTile(
                          leading: CircleAvatar(
                            backgroundColor: AppColors.accentSubtle,
                            child: Icon(
                              Icons.person,
                              size: 20,
                              color: AppColors.accent,
                            ),
                          ),
                          title: Text(driverName),
                          subtitle: driverPlate != null
                              ? Text(driverPlate)
                              : null,
                          trailing: _reassigning &&
                                  _reassigningDriverId == driverId
                              ? const SizedBox(
                                  width: 20,
                                  height: 20,
                                  child: CircularProgressIndicator(
                                      strokeWidth: 2),
                                )
                              : null,
                          onTap: _reassigning
                              ? null
                              : () =>
                                  _confirmReassign(driverId, driverName),
                        );
                      },
                    ),
                  );
                },
              ),
            ],
          ),
        );
      },
    );
  }

  /// The driver ID currently being reassigned (for per-item loading state).
  String _reassigningDriverId = '';

  /// Shows a confirmation dialog, then calls the reassign API.
  Future<void> _confirmReassign(String driverId, String driverName) async {
    final loc = context.loc;

    // Guard: reject empty driver IDs before showing the dialog.
    if (driverId.isEmpty) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(loc.general_error),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }

    final confirmed = await ConfirmationDialog.show(
      context,
      title: loc.dispatcher_reassign,
      message: loc.dispatcher_reassignConfirm.replaceAll('{driver}', driverName),
      confirmLabel: loc.general_confirm,
      cancelLabel: loc.general_cancel,
    );

    if (confirmed != true) return;
    if (!mounted) return;

    // Close the bottom sheet.
    Navigator.of(context).pop();

    setState(() {
      _reassigning = true;
      _reassigningDriverId = driverId;
    });

    try {
      final endpoints = ref.read(dispatcherEndpointsProvider);
      await endpoints.reassignTransport(
        widget.jobId.toString(),
        driverId,
      );

      // Refresh job data.
      ref.invalidate(dispatcherJobsProvider);
      ref.invalidate(jobDetailProvider(widget.jobId));

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(loc.dispatcher_reassignSuccess),
          backgroundColor: AppColors.success,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('${loc.general_error}: $e'),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _reassigning = false;
          _reassigningDriverId = '';
        });
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final jobAsync = ref.watch(jobDetailProvider(widget.jobId));

    return Scaffold(
      appBar: AppBar(
        title: Text(context.loc.dispatcher_jobDetails),
      ),
      body: jobAsync.when(
        loading: () => const _ShimmerContent(),
        error: (error, stackTrace) => _ErrorContent(
          message: '$error',
          onRetry: () =>
              ref.invalidate(jobDetailProvider(widget.jobId)),
        ),
        data: (job) => job.isEmpty
            ? _ErrorContent(
                message: context.loc.dispatcher_noJobs,
                onRetry: () =>
                    ref.invalidate(jobDetailProvider(widget.jobId)),
              )
            : _buildContent(job),
      ),
    );
  }

  /// Builds the full scrollable content for a loaded [job].
  Widget _buildContent(Map<String, dynamic> job) {
    final loc = context.loc;

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(dispatcherJobsProvider);
        ref.invalidate(jobDetailProvider(widget.jobId));
        await ref.read(jobDetailProvider(widget.jobId).future);
      },
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Section 1: Load Hero ───────────────────
            _buildLoadHero(job),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 2: Route Card ──────────────────
            _buildRouteCard(job),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 3: Status Section ──────────────
            _buildStatusSection(job),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 4: Info Grid ───────────────────
            _buildInfoGrid(job, loc),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 5: Quick Actions ───────────────
            _buildQuickActions(job, loc),

            const SizedBox(height: AppSpacing.xxxl),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Section builders
  // ---------------------------------------------------------------------------

  /// Section 1 — Large load description with indigo left border accent.
  Widget _buildLoadHero(Map<String, dynamic> job) {
    final loadInfo = (job['load_info'] as String?) ?? '';

    return Container(
      decoration: BoxDecoration(
        border: Border(
          left: BorderSide(
            color: AppColors.accent,
            width: 4,
          ),
        ),
      ),
      padding: const EdgeInsets.only(left: AppSpacing.md),
      child: Text(
        loadInfo,
        style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w700,
              height: 1.3,
            ),
      ),
    );
  }

  /// Section 2 — Route card with origin and destination.
  Widget _buildRouteCard(Map<String, dynamic> job) {
    final theme = Theme.of(context);
    final loc = context.loc;

    final origin = (job['origin'] as String?) ?? '';
    final destination = (job['destination'] as String?) ?? '';

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title row
          Row(
            children: [
              const Icon(Icons.route, size: 18, color: AppColors.accent),
              const SizedBox(width: AppSpacing.sm),
              Text(
                loc.transport_route,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),

          // Origin
          _buildStopRow(
            icon: Icons.trip_origin,
            label: origin,
            color: AppColors.success,
          ),

          // Arrow connector
          const Padding(
            padding: EdgeInsets.symmetric(vertical: AppSpacing.xs),
            child: Row(
              children: [
                SizedBox(width: 24),
                Icon(Icons.arrow_downward, size: 18),
              ],
            ),
          ),

          // Destination with navigate button
          _buildStopRow(
            icon: Icons.location_on,
            label: destination,
            color: AppColors.error,
            onNavigate: () {
              // TODO: Extract lat/lng from job data when available.
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                  content: Text('${loc.transport_navigate} → $destination'),
                  behavior: SnackBarBehavior.floating,
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  /// Builds a single stop row (origin / destination) with optional navigate
  /// button.
  Widget _buildStopRow({
    required IconData icon,
    required String label,
    required Color color,
    VoidCallback? onNavigate,
  }) {
    final theme = Theme.of(context);
    final loc = context.loc;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 20, color: color),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            label,
            style: theme.textTheme.bodyMedium,
          ),
        ),
        if (onNavigate != null) ...[
          const SizedBox(width: AppSpacing.sm),
          SizedBox(
            height: 32,
            child: TextButton.icon(
              onPressed: onNavigate,
              icon: const Icon(Icons.navigation, size: 16),
              label: Text(
                loc.transport_navigate,
                style: const TextStyle(fontSize: 12),
              ),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm),
                visualDensity: VisualDensity.compact,
              ),
            ),
          ),
        ],
      ],
    );
  }

  /// Section 3 — Status badge with "Mark Delivered" quick action.
  Widget _buildStatusSection(Map<String, dynamic> job) {
    final theme = Theme.of(context);
    final loc = context.loc;

    final status = (job['status'] as String?) ?? '';
    final isDelivered = status == 'delivered';
    final isCancelled = status == 'cancelled';
    final isFinal = isDelivered || isCancelled;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.accentSubtle,
        borderRadius: AppRadius.xlAll,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Status badge
          Row(
            children: [
              StatusBadge(statusKey: status),
            ],
          ),
          const SizedBox(height: AppSpacing.md),

          // Final status message
          if (isFinal) ...[
            Text(
              isDelivered
                  ? 'Job marcat ca livrat.'
                  : 'Job anulat.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface
                    .withValues(alpha: 0.7),
              ),
            ),
          ],

          // Mark Delivered button
          if (!isFinal) ...[
            app_button.AppButton.primary(
              label: loc.dispatcher_markDelivered,
              isLoading: _markDeliveredLoading,
              onPressed: _markDeliveredLoading
                  ? null
                  : _markDelivered,
            ),
          ],
        ],
      ),
    );
  }

  /// Section 4 — Two-column info grid with Driver, Vehicle plate,
  /// Created, and Last updated.
  Widget _buildInfoGrid(
    Map<String, dynamic> job,
    AppLocalizations loc,
  ) {
    final theme = Theme.of(context);
    final dateFormat = DateFormat.yMd().add_jm();

    final driverName = (job['driver_name'] as String?) ?? '-';
    final vehiclePlate = (job['vehicle_plate'] as String?) ?? '-';
    final lastUpdatedStr = job['last_updated'] as String?;
    final createdStr = job['created'] as String?;

    final lastUpdated = lastUpdatedStr != null
        ? DateTime.tryParse(lastUpdatedStr)
        : null;
    final created = createdStr != null
        ? DateTime.tryParse(createdStr)
        : null;

    final items = <_InfoItem>[
      _InfoItem(
        icon: Icons.person,
        label: loc.dispatcher_driver,
        value: driverName,
      ),
      _InfoItem(
        icon: Icons.directions_car,
        label: loc.vehicle_plate,
        value: vehiclePlate,
      ),
      _InfoItem(
        icon: Icons.calendar_today,
        label: loc.general_created,
        value: created != null ? dateFormat.format(created) : '-',
      ),
      _InfoItem(
        icon: Icons.access_time,
        label: loc.general_lastUpdated,
        value:
            lastUpdated != null ? dateFormat.format(lastUpdated) : '-',
      ),
    ];

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            loc.transport_details,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate:
                const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: AppSpacing.lg,
              mainAxisSpacing: AppSpacing.md,
              childAspectRatio: 2.5,
            ),
            itemCount: items.length,
            itemBuilder: (context, index) {
              final item = items[index];
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(item.icon,
                      size: 18, color: AppColors.accent),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment:
                          CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.label,
                          style: theme.textTheme.bodySmall
                              ?.copyWith(
                            color: theme
                                .colorScheme.onSurface
                                .withValues(alpha: 0.6),
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          item.value,
                          style: theme.textTheme.bodyMedium
                              ?.copyWith(
                            fontWeight: FontWeight.w500,
                          ),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  /// Section 5 — Quick Actions: Reassign Driver and Message Driver.
  Widget _buildQuickActions(
    Map<String, dynamic> job,
    AppLocalizations loc,
  ) {
    final theme = Theme.of(context);
    final driverName = (job['driver_name'] as String?);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(Icons.bolt,
                size: 18, color: theme.colorScheme.primary),
            const SizedBox(width: AppSpacing.sm),
            Text(
              loc.dispatcher_quickActions,
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),
        app_button.AppButton.secondary(
          label: loc.dispatcher_reassign,
          icon: const Icon(Icons.swap_horiz, size: 18),
          isLoading: _reassigning,
          onPressed:
              _reassigning ? null : _showReassignSheet,
        ),
        const SizedBox(height: AppSpacing.sm),
        app_button.AppButton.secondary(
          label: loc.dispatcher_messageDriver,
          icon: const Icon(Icons.message_outlined, size: 18),
          onPressed: () => _messageDriver(driverName),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Supporting widgets
// ---------------------------------------------------------------------------

/// Shimmer loading placeholder matching the detail screen layout.
class _ShimmerContent extends StatelessWidget {
  const _ShimmerContent();

  @override
  Widget build(BuildContext context) {
    return const SingleChildScrollView(
      padding: EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          ShimmerLoader(
            child: _ShimmerBlock(height: 48, widthFactor: 0.8),
          ),
          SizedBox(height: AppSpacing.lg),
          ShimmerCard(),
          SizedBox(height: AppSpacing.lg),
          ShimmerLoader(
            child: _ShimmerBlock(height: 180, widthFactor: 1),
          ),
          SizedBox(height: AppSpacing.lg),
          ShimmerLoader(
            child: _ShimmerBlock(height: 120, widthFactor: 1),
          ),
        ],
      ),
    );
  }
}

/// A coloured rectangle used inside [ShimmerLoader] as a skeleton block.
class _ShimmerBlock extends StatelessWidget {
  const _ShimmerBlock({required this.height, this.widthFactor = 1});

  final double height;
  final double widthFactor;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: widthFactor,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: AppRadius.lgAll,
        ),
      ),
    );
  }
}

/// Full-screen error state with a retry button.
class _ErrorContent extends StatelessWidget {
  const _ErrorContent({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final loc = context.loc;

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.error_outline,
              size: 64,
              color: AppColors.error.withValues(alpha: 0.6),
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              loc.general_error,
              style: theme.textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurface
                    .withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: 200,
              child: app_button.AppButton.primary(
                label: loc.general_retry,
                onPressed: onRetry,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Data class for info grid items.
class _InfoItem {
  final IconData icon;
  final String label;
  final String value;

  const _InfoItem({
    required this.icon,
    required this.label,
    required this.value,
  });
}
