import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/transport.dart';
import '../../../shared/widgets/app_button.dart' as app_button;
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/status_badge.dart';
import '../../../shared/widgets/staleness_indicator.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../shared/widgets/transport_status_actions.dart';
import 'package:url_launcher/url_launcher.dart';
import '../documents/document_list_screen.dart';
import '../documents/document_upload_screen.dart';
import '../home/driver_providers.dart';

// ---------------------------------------------------------------------------
// TransportDetailScreen
// ---------------------------------------------------------------------------

/// Full-screen detail view for a single transport.
///
/// Displays load information, route details, current status with update
/// actions, an info grid, and a documents section placeholder.
///
/// The status update buttons show an independent loading spinner per button
/// so that multiple updates can be visualised concurrently.
class TransportDetailScreen extends ConsumerStatefulWidget {
  /// The transport identifier to load.
  final String transportId;

  const TransportDetailScreen({super.key, required this.transportId});

  @override
  ConsumerState<TransportDetailScreen> createState() =>
      _TransportDetailScreenState();
}

class _TransportDetailScreenState
    extends ConsumerState<TransportDetailScreen> {
  /// Tracks which status targets are currently loading (per-button loading).
  final Set<String> _loadingStatuses = {};

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  /// Opens Google Maps for navigation to [lat],[lng].
  Future<void> _openMaps(double lat, double lng) async {
    final url = Uri.parse(
      'https://www.google.com/maps/dir/?api=1&destination=$lat,$lng',
    );
    try {
      if (await canLaunchUrl(url)) {
        await launchUrl(url, mode: LaunchMode.externalApplication);
      }
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Could not open maps: $e'),
          backgroundColor: AppColors.error,
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  /// Sends a status update request to the API.
  ///
  /// On success the [transportDetailProvider] is invalidated so the UI
  /// refreshes automatically. On failure an error snackbar is shown. If the
  /// device is offline an amber offline snackbar is shown instead.
  Future<void> _updateStatus(String newStatus) async {
    try {
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

      final endpoints = ref.read(driverEndpointsProvider);
      await endpoints.updateStatus(widget.transportId, newStatus);

      // Refresh transport detail from the API.
      ref.invalidate(transportDetailProvider(widget.transportId));

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Status updated to $newStatus'),
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
      if (mounted) {
        setState(() => _loadingStatuses.remove(newStatus));
      }
    }
  }

  // -----------------------------------------------------------------------
  // Build
  // -----------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final transportAsync = ref.watch(transportDetailProvider(widget.transportId));

    return Scaffold(
      appBar: AppBar(
        title: Text(context.loc.transport_details),
      ),
      body: transportAsync.when(
        loading: () => const _ShimmerContent(),
        error: (error, stackTrace) => _ErrorContent(
          message: '$error',
          onRetry: () =>
              ref.invalidate(transportDetailProvider(widget.transportId)),
        ),
        data: (transport) => _buildContent(transport),
      ),
    );
  }

  /// Builds the full scrollable content for a loaded [transport].
  Widget _buildContent(Transport transport) {
    final loc = context.loc;
    final isOffline = ref.watch(isOfflineProvider);

    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(transportDetailProvider(widget.transportId));
        // Wait for the new data to settle.
        await ref.read(transportDetailProvider(widget.transportId).future);
      },
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(AppSpacing.lg),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Section 1: Load Info Hero ─────────────────
            _buildLoadHero(transport),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 2: Route Card ─────────────────────
            _buildRouteCard(transport),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 3: Status Section ─────────────────
            _buildStatusSection(transport, isOffline),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 4: Info Grid ──────────────────────
            _buildInfoGrid(transport, loc),

            const SizedBox(height: AppSpacing.lg),

            // ── Section 5: Documents ──────────────────────
            _buildDocumentsSection(transport, loc),

            const SizedBox(height: AppSpacing.xxxl),
          ],
        ),
      ),
    );
  }

  // -----------------------------------------------------------------------
  // Section builders
  // -----------------------------------------------------------------------

  /// Section 1 — Large load description with coloured accent border.
  Widget _buildLoadHero(Transport transport) {
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
        transport.loadInfo,
        style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w700,
              height: 1.3,
            ),
      ),
    );
  }

  /// Section 2 — Route card with origin, waypoints, and destination.
  Widget _buildRouteCard(Transport transport) {
    final theme = Theme.of(context);
    final loc = context.loc;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Title row
          Row(
            children: [
              Icon(Icons.route, size: 18, color: theme.colorScheme.primary),
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
            label: transport.origin,
            color: AppColors.success,
            onNavigate: (transport.originLat != null &&
                    transport.originLng != null)
                ? () => _openMaps(transport.originLat!, transport.originLng!)
                : null,
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

          // Waypoints
          if (transport.waypoints.isNotEmpty) ...[
            for (int i = 0; i < transport.waypoints.length; i++) ...[
              _buildWaypointRow(index: i + 1, label: transport.waypoints[i]),
              if (i < transport.waypoints.length - 1 ||
                  transport.destination.isNotEmpty)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: AppSpacing.xs),
                  child: Row(
                    children: [
                      SizedBox(width: 24),
                      Icon(Icons.arrow_downward, size: 18),
                    ],
                  ),
                ),
            ],
          ],

          // Destination
          _buildStopRow(
            icon: Icons.location_on,
            label: transport.destination,
            color: AppColors.error,
            onNavigate: (transport.destLat != null &&
                    transport.destLng != null)
                ? () => _openMaps(transport.destLat!, transport.destLng!)
                : null,
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
                context.loc.transport_navigate,
                style: const TextStyle(fontSize: 12),
              ),
              style: TextButton.styleFrom(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
                visualDensity: VisualDensity.compact,
              ),
            ),
          ),
        ],
      ],
    );
  }

  /// Builds a numbered waypoint row with a dot indicator.
  Widget _buildWaypointRow({required int index, required String label}) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 20,
          child: Center(
            child: Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                color: AppColors.accent,
                shape: BoxShape.circle,
              ),
              child: Center(
                child: Text(
                  '$index',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 7,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            label,
            style: theme.textTheme.bodyMedium,
          ),
        ),
      ],
    );
  }

  /// Section 3 — Status card with badge, staleness indicator, and action
  /// buttons.
  Widget _buildStatusSection(Transport transport, bool isOffline) {
    final theme = Theme.of(context);
    final loc = context.loc;
    final isFinalStatus = transport.status == 'delivered' ||
        transport.status == 'cancelled';

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
          // Status badge and staleness
          Row(
            children: [
              StatusBadge(statusKey: transport.status),
              const Spacer(),
              StalenessIndicator(
                lastUpdated: transport.lastUpdated,
                isPending: isOffline,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),

          // Offline warning
          if (isOffline) ...[
            Row(
              children: [
                Icon(Icons.cloud_off, size: 14, color: AppColors.warning),
                const SizedBox(width: AppSpacing.xs),
                Text(
                  loc.general_offline,
                  style: const TextStyle(
                    fontSize: 12,
                    color: AppColors.warning,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
          ],

          // Final status message
          if (isFinalStatus) ...[
            Text(
              transport.status == 'delivered'
                  ? loc.transport_status_delivered
                  : loc.transport_status_cancelled,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ],

          // Action buttons
          TransportStatusButtons(
            currentStatus: transport.status,
            loadingStatuses: _loadingStatuses,
            isOffline: isOffline,
            onStatusUpdate: _updateStatus,
          ),
        ],
      ),
    );
  }

  /// Section 4 — Two-column info grid.
  Widget _buildInfoGrid(Transport transport, AppLocalizations loc) {
    final theme = Theme.of(context);
    final dateFormat = DateFormat.yMd();

    final items = <_InfoItem>[
      _InfoItem(
        icon: Icons.person,
        label: 'Driver',
        value: transport.assignedDriverName ?? '-',
      ),
      _InfoItem(
        icon: Icons.directions_car,
        label: 'Vehicle',
        value: transport.vehiclePlate ?? '-',
      ),
      _InfoItem(
        icon: Icons.calendar_today,
        label: 'Scheduled',
        value: transport.scheduledDate != null
            ? dateFormat.format(transport.scheduledDate!)
            : '-',
      ),
      _InfoItem(
        icon: Icons.check_circle_outline,
        label: loc.transport_status_delivered,
        value: transport.deliveredDate != null
            ? dateFormat.format(transport.deliveredDate!)
            : '-',
      ),
    ];

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Informa\u021bii',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
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
                  Icon(item.icon, size: 18, color: AppColors.accent),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.label,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurface
                                .withValues(alpha: 0.6),
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          item.value,
                          style: theme.textTheme.bodyMedium?.copyWith(
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

  /// Section 5 — Documents placeholder.
  Widget _buildDocumentsSection(Transport transport, AppLocalizations loc) {
    final theme = Theme.of(context);

    // Placeholder document count — in a real implementation this would come
    // from a document provider keyed by transport.id.
    const documentCount = 0;

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.description_outlined,
                  size: 18, color: theme.colorScheme.primary),
              const SizedBox(width: AppSpacing.sm),
              Text(
                loc.driver_documents,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            '$documentCount documente',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Expanded(
                child: app_button.AppButton.secondary(
                  label: 'View Documents',
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => DocumentListScreen(
                          transportId: widget.transportId,
                        ),
                      ),
                    );
                  },
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: app_button.AppButton.primary(
                  label: 'Add Document',
                  onPressed: () {
                    Navigator.push(
                      context,
                      MaterialPageRoute(
                        builder: (_) => DocumentUploadScreen(
                          transportId: widget.transportId,
                        ),
                      ),
                    );
                  },
                ),
              ),
            ],
          ),
        ],
      ),
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
                color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
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
