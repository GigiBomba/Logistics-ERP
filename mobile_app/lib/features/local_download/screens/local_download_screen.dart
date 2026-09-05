import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/sync/sync_providers.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../models/download_manifest.dart';
import '../providers/offline_data_providers.dart';

/// Local Download screen — shows offline-available synced data and
/// supports pull-on-demand document downloads.
///
/// The top section displays the current sync status and cached record counts
/// for each synced collection (transport, message, drivers, fleet). The lower
/// section keeps the existing category-based document download flow.
class LocalDownloadScreen extends ConsumerStatefulWidget {
  const LocalDownloadScreen({super.key});

  @override
  ConsumerState<LocalDownloadScreen> createState() => _LocalDownloadScreenState();
}

class _LocalDownloadScreenState extends ConsumerState<LocalDownloadScreen> {
  DownloadCategory? _selectedCategory;

  static const List<String> _collections = ['transport', 'message', 'drivers', 'fleet'];

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);
    final syncStatus = ref.watch(syncStatusProvider);

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_localDownload)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          // ── Sync status ────────────────────────────────────────────────
          _buildSyncStatusCard(theme, loc, syncStatus),
          const SizedBox(height: AppSpacing.xl),

          // ── Offline data collections ───────────────────────────────────
          ..._collections.map((c) => _CollectionCountCard(collection: c)),
          const SizedBox(height: AppSpacing.xxl),

          // ── Document download section ──────────────────────────────────
          Text(
            loc.localDownload_selectCategory,
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          ...DownloadCategory.values.map((category) {
            final selected = _selectedCategory == category;
            return Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: AppCard(
                onTap: () => setState(() => _selectedCategory = category),
                child: Padding(
                  padding: const EdgeInsets.all(AppSpacing.md),
                  child: Row(
                    children: [
                      Icon(
                        _iconForCategory(category),
                        color: selected ? AppColors.accent : null,
                      ),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Text(
                          _categoryLabel(loc, category),
                          style: theme.textTheme.bodyMedium?.copyWith(
                            fontWeight: selected ? FontWeight.w600 : null,
                          ),
                        ),
                      ),
                      if (selected)
                        const Icon(
                          LucideIcons.check,
                          color: AppColors.accent,
                          size: 20,
                        ),
                    ],
                  ),
                ),
              ),
            );
          }),
          const SizedBox(height: AppSpacing.xl),
          if (_selectedCategory != null)
            AppButton.primary(
              label: loc.localDownload_download,
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text(loc.localDownload_progress)),
                );
              },
            ),
        ],
      ),
    );
  }

  Widget _buildSyncStatusCard(
    ThemeData theme,
    AppLocalizations loc,
    SyncStatus status,
  ) {
    final (icon, color, label) = switch (status) {
      SyncStatus.syncing => (
          LucideIcons.refreshCw,
          AppColors.info,
          loc.general_pendingSync,
        ),
      SyncStatus.error => (
          LucideIcons.alertCircle,
          AppColors.error,
          loc.general_error,
        ),
      SyncStatus.success => (
          LucideIcons.checkCircle,
          AppColors.success,
          loc.general_lastUpdated,
        ),
      SyncStatus.idle => (
          LucideIcons.cloudOff,
          AppColors.neutralText,
          loc.general_offline,
        ),
    };

    return AppCard(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.md),
        child: Row(
          children: [
            Icon(icon, color: color),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Text(
                label,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: color,
                ),
              ),
            ),
            if (status == SyncStatus.syncing)
              SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: color,
                ),
              ),
          ],
        ),
      ),
    );
  }

  String _categoryLabel(AppLocalizations loc, DownloadCategory category) {
    switch (category) {
      case DownloadCategory.documents:
        return loc.localDownload_categoryDocuments;
      case DownloadCategory.invoices:
        return loc.localDownload_categoryInvoices;
      case DownloadCategory.receipts:
        return loc.localDownload_categoryReceipts;
      case DownloadCategory.ocrResults:
        return loc.localDownload_categoryOcrResults;
      case DownloadCategory.tripHistory:
        return loc.localDownload_categoryTripHistory;
    }
  }

  IconData _iconForCategory(DownloadCategory category) {
    switch (category) {
      case DownloadCategory.documents:
        return LucideIcons.fileText;
      case DownloadCategory.invoices:
        return LucideIcons.fileText;
      case DownloadCategory.receipts:
        return LucideIcons.receipt;
      case DownloadCategory.ocrResults:
        return LucideIcons.scanText;
      case DownloadCategory.tripHistory:
        return LucideIcons.history;
    }
  }
}

// ---------------------------------------------------------------------------
// _CollectionCountCard
// ---------------------------------------------------------------------------

/// Displays the cached record count for a single synced collection,
/// with a subtle spinner when a sync is in flight.
class _CollectionCountCard extends ConsumerWidget {
  final String collection;

  const _CollectionCountCard({required this.collection});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final loc = context.loc;
    final stateAsync = ref.watch(offlineCollectionStateProvider(collection));

    final title = switch (collection) {
      'transport' => loc.nav_transports,
      'message' => loc.nav_messages,
      'drivers' => loc.nav_drivers,
      'fleet' => loc.nav_fleet,
      _ => collection,
    };

    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.sm),
      child: AppCard(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
              stateAsync.when(
                loading: () => SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: theme.colorScheme.primary,
                  ),
                ),
                error: (_, __) => Text(
                  '-',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: AppColors.neutralText,
                  ),
                ),
                data: (state) => Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      '${state.count}',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    if (state.isSyncing) ...[
                      const SizedBox(width: AppSpacing.sm),
                      SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: AppColors.info,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
