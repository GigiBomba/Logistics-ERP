import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/vehicle.dart';
import '../../../shared/models/vehicle_document.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import 'vehicle_providers.dart';

/// Displays detailed information about the driver's currently assigned
/// vehicle, including its documents and their expiry status.
///
/// Uses [vehicleProvider] to fetch data and handles loading, error, and
/// empty (no vehicle assigned) states.
class VehicleDetailScreen extends ConsumerWidget {
  const VehicleDetailScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final vehicleAsync = ref.watch(vehicleProvider);
    final loc = context.loc;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.vehicle_assigned)),
      body: vehicleAsync.when(
        loading: () => const _VehicleShimmer(),
        error: (error, _) => _buildError(loc, ref),
        data: (vehicle) {
          if (vehicle == null) return _buildNoVehicle(loc, theme);
          return _buildContent(vehicle, loc, theme, ref);
        },
      ),
    );
  }

  /// Error state with retry button that invalidates the vehicle provider.
  Widget _buildError(AppLocalizations loc, WidgetRef ref) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              LucideIcons.alertCircle,
              size: 56,
              color: AppColors.error,
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              loc.general_error,
              style: const TextStyle(fontSize: 16),
            ),
            const SizedBox(height: AppSpacing.xl),
            AppButton.primary(
              label: loc.general_retry,
              onPressed: () => ref.invalidate(vehicleProvider),
            ),
          ],
        ),
      ),
    );
  }

  /// Empty state when no vehicle is assigned.
  Widget _buildNoVehicle(AppLocalizations loc, ThemeData theme) {
    return const EmptyState(
      icon: Icon(LucideIcons.truck),
      title: 'No vehicle assigned',
      subtitle: 'Contact your dispatcher to get assigned to a vehicle.',
    );
  }

  /// Main vehicle content: hero card, info section, and documents list.
  Widget _buildContent(
    Vehicle vehicle,
    AppLocalizations loc,
    ThemeData theme,
    WidgetRef ref,
  ) {
    return RefreshIndicator(
      onRefresh: () async {
        ref.invalidate(vehicleProvider);
      },
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          _buildHeroCard(vehicle, theme, loc),
          const SizedBox(height: AppSpacing.lg),
          _buildInfoSection(vehicle, theme, loc),
          const SizedBox(height: AppSpacing.lg),
          _buildDocumentsSection(vehicle, theme, loc),
        ],
      ),
    );
  }

  /// Large hero card featuring the plate number and status indicator.
  Widget _buildHeroCard(Vehicle vehicle, ThemeData theme, AppLocalizations loc) {
    final statusColor = _statusColor(vehicle.status);

    return AppCard(
      child: Column(
        children: [
          // Plate number
          Text(
            vehicle.plate,
            style: theme.textTheme.headlineLarge?.copyWith(
              fontWeight: FontWeight.w700,
              letterSpacing: 3,
              fontFamily: 'monospace',
            ),
          ),
          const SizedBox(height: AppSpacing.sm),
          // Type and brand
          Text(
            '${vehicle.type} • ${vehicle.brand}',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: AppColors.textSecondaryLight,
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          // Status indicator
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.md,
              vertical: AppSpacing.xs,
            ),
            decoration: BoxDecoration(
              color: statusColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(AppRadius.pill),
            ),
            child: Text(
              _localizedStatus(vehicle.status, loc),
              style: TextStyle(
                color: statusColor,
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Info section: brand, model, and year.
  Widget _buildInfoSection(
    Vehicle vehicle,
    ThemeData theme,
    AppLocalizations loc,
  ) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Details',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          _InfoRow(
            label: 'Brand',
            value: vehicle.brand,
            icon: LucideIcons.factory,
          ),
          const SizedBox(height: AppSpacing.sm),
          _InfoRow(
            label: 'Model',
            value: vehicle.model,
            icon: LucideIcons.settings,
          ),
          const SizedBox(height: AppSpacing.sm),
          _InfoRow(
            label: loc.vehicle_type,
            value: vehicle.type,
            icon: LucideIcons.tag,
          ),
        ],
      ),
    );
  }

  /// Documents section: lists each vehicle document with colour-coded
  /// expiry status.
  Widget _buildDocumentsSection(
    Vehicle vehicle,
    ThemeData theme,
    AppLocalizations loc,
  ) {
    if (vehicle.documents.isEmpty) {
      return AppCard(
        child: Row(
          children: [
            const Icon(LucideIcons.fileText, color: AppColors.neutralText),
            const SizedBox(width: AppSpacing.sm),
            Text(loc.vehicle_documents),
            const Spacer(),
            Text(
              loc.document_noDocuments,
              style: TextStyle(color: AppColors.textSecondaryLight),
            ),
          ],
        ),
      );
    }

    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            loc.vehicle_documents,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          ...vehicle.documents.map(
            (doc) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: _VehicleDocumentRow(doc: doc),
            ),
          ),
        ],
      ),
    );
  }

  /// Returns a colour for the vehicle status.
  Color _statusColor(String status) {
    return switch (status) {
      'available' => AppColors.success,
      'in_use' => AppColors.info,
      'maintenance' => AppColors.warning,
      'out_of_service' => AppColors.error,
      _ => AppColors.neutralText,
    };
  }

  /// Localizes the vehicle status string.
  String _localizedStatus(String status, AppLocalizations loc) {
    return switch (status) {
      'available' => 'Available',
      'in_use' => 'In Use',
      'maintenance' => 'Maintenance',
      'out_of_service' => 'Out of Service',
      _ => status,
    };
  }

}

/// A single info row: icon, label, and value.
class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.label,
    required this.value,
    required this.icon,
  });

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Icon(icon, size: 18, color: AppColors.textSecondaryLight),
        const SizedBox(width: AppSpacing.sm),
        Text(
          '$label: ',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: AppColors.textSecondaryLight,
          ),
        ),
        Text(
          value,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

/// A single vehicle document row with colour-coded expiry status.
class _VehicleDocumentRow extends StatelessWidget {
  const _VehicleDocumentRow({required this.doc});

  final VehicleDocument doc;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final (Color color, String label) = _expiryStatus();

    return Row(
      children: [
        Container(
          height: 36,
          width: 36,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: AppRadius.lgAll,
          ),
          child: Icon(
            LucideIcons.fileText,
            size: 18,
            color: color,
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                doc.documentType,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
              if (doc.expiryDate != null)
                Text(
                  'Expires: ${_formatDate(doc.expiryDate!)}',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondaryLight,
                  ),
                ),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.sm,
            vertical: 2,
          ),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: AppRadius.pillAll,
          ),
          child: Text(
            label,
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ),
      ],
    );
  }

  /// Determines the status colour and label based on expiry proximity.
  (Color, String) _expiryStatus() {
    if (doc.expiryDate == null) {
      return (AppColors.neutralText, 'No expiry');
    }

    final daysUntilExpiry = doc.expiryDate!.difference(DateTime.now()).inDays;

    if (daysUntilExpiry < 0) {
      return (AppColors.error, 'Expired');
    } else if (daysUntilExpiry <= 30 || doc.isExpiringSoon) {
      return (AppColors.warning, 'Expiring soon');
    }
    return (AppColors.success, 'Valid');
  }

  String _formatDate(DateTime date) {
    return '${date.day.toString().padLeft(2, '0')}.'
        '${date.month.toString().padLeft(2, '0')}.'
        '${date.year}';
  }
}

/// Shimmer loading placeholders for the vehicle detail screen.
class _VehicleShimmer extends StatelessWidget {
  const _VehicleShimmer();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: const [
        ShimmerLoader(
          child: Card(
            margin: EdgeInsets.zero,
            child: Padding(
              padding: EdgeInsets.all(AppSpacing.xxl),
              child: Column(
                children: [
                  _ShimmerBlock(height: 32, widthFactor: 0.5),
                  SizedBox(height: AppSpacing.sm),
                  _ShimmerBlock(height: 14, widthFactor: 0.3),
                  SizedBox(height: AppSpacing.lg),
                  _ShimmerBlock(height: 24, widthFactor: 0.25),
                ],
              ),
            ),
          ),
        ),
        SizedBox(height: AppSpacing.lg),
        ShimmerCard(),
        SizedBox(height: AppSpacing.lg),
        ShimmerCard(),
      ],
    );
  }
}

/// A rectangular shimmer placeholder with configurable height and width.
class _ShimmerBlock extends StatelessWidget {
  const _ShimmerBlock({
    required this.height,
    this.widthFactor = 1.0,
  });

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
          borderRadius: BorderRadius.circular(AppRadius.sm),
        ),
      ),
    );
  }
}
