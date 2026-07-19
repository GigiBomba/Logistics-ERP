import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../models/download_manifest.dart';

/// Local Download screen — pull-on-demand document downloads.
///
/// Select a category + optional date range → request manifest →
/// download each file with per-file progress bars.
class LocalDownloadScreen extends ConsumerStatefulWidget {
  const LocalDownloadScreen({super.key});

  @override
  ConsumerState<LocalDownloadScreen> createState() => _LocalDownloadScreenState();
}

class _LocalDownloadScreenState extends ConsumerState<LocalDownloadScreen> {
  DownloadCategory? _selectedCategory;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_localDownload)),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          Text(loc.localDownload_selectCategory,
              style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: AppSpacing.md),
          // Category grid
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
                        const Icon(LucideIcons.check, color: AppColors.accent, size: 20),
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

  String _categoryLabel(AppLocalizations loc, DownloadCategory category) {
    switch (category) {
      case DownloadCategory.documents: return loc.localDownload_categoryDocuments;
      case DownloadCategory.invoices: return loc.localDownload_categoryInvoices;
      case DownloadCategory.receipts: return loc.localDownload_categoryReceipts;
      case DownloadCategory.ocrResults: return loc.localDownload_categoryOcrResults;
      case DownloadCategory.tripHistory: return loc.localDownload_categoryTripHistory;
    }
  }

  IconData _iconForCategory(DownloadCategory category) {
    switch (category) {
      case DownloadCategory.documents: return LucideIcons.fileText;
      case DownloadCategory.invoices: return LucideIcons.fileText;
      case DownloadCategory.receipts: return LucideIcons.receipt;
      case DownloadCategory.ocrResults: return LucideIcons.scanText;
      case DownloadCategory.tripHistory: return LucideIcons.history;
    }
  }
}
