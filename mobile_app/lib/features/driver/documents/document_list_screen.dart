import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/models/document.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/empty_state.dart';
import 'document_upload_screen.dart';

/// Displays a list of documents uploaded by the driver for the current
/// transport.
///
/// For now uses mock data. A FAB navigates to [DocumentUploadScreen].
class DocumentListScreen extends StatelessWidget {
  const DocumentListScreen({super.key, this.transportId});

  /// Optional transport ID to filter documents by.
  final String? transportId;

  /// Mock documents for placeholder UI.
  static const _mockDocuments = [
    Document(
      id: 'doc_1',
      transportId: 't1',
      type: 'cmr',
      fileName: 'cmr_transport_1234.pdf',
      fileUrl: '',
      uploadStatus: 'uploaded',
      uploadedAt: null,
    ),
    Document(
      id: 'doc_2',
      transportId: 't1',
      type: 'pod',
      fileName: 'pod_signature.jpg',
      fileUrl: '',
      uploadStatus: 'uploaded',
      uploadedAt: null,
    ),
    Document(
      id: 'doc_3',
      transportId: 't2',
      type: 'invoice',
      fileName: 'invoice_feb2026.pdf',
      fileUrl: '',
      uploadStatus: 'pending',
      uploadedAt: null,
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: Text(loc.driver_documents)),
      body: _mockDocuments.isEmpty
          ? _buildEmptyState(context, loc, theme)
          : _buildDocumentList(loc, theme),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _navigateToUpload(context),
        icon: const Icon(LucideIcons.upload),
        label: Text(loc.document_upload),
      ),
    );
  }

  /// Navigates to the [DocumentUploadScreen].
  void _navigateToUpload(BuildContext context) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => DocumentUploadScreen(
          transportId: transportId ?? 'default',
        ),
      ),
    );
  }

  /// Empty state shown when no documents exist.
  Widget _buildEmptyState(BuildContext context, AppLocalizations loc, ThemeData theme) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          EmptyState(
            icon: const Icon(LucideIcons.fileText),
            title: loc.document_noDocuments,
          ),
          const SizedBox(height: AppSpacing.lg),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxl),
            child: AppButton.primary(
              label: loc.document_upload,
              icon: const Icon(LucideIcons.upload),
              onPressed: () => _navigateToUpload(context),
            ),
          ),
        ],
      ),
    );
  }

  /// Builds the list of document items.
  Widget _buildDocumentList(AppLocalizations loc, ThemeData theme) {
    return ListView.separated(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: _mockDocuments.length,
      separatorBuilder: (_, __) => const SizedBox(height: AppSpacing.sm),
      itemBuilder: (context, index) {
        final doc = _mockDocuments[index];
        return _DocumentListItem(doc: doc);
      },
    );
  }
}

/// A single document row in the list.
class _DocumentListItem extends StatelessWidget {
  const _DocumentListItem({required this.doc});

  final Document doc;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final theme = Theme.of(context);

    final statusColor = switch (doc.uploadStatus) {
      'uploaded' => AppColors.success,
      'pending' => AppColors.warning,
      'failed' => AppColors.error,
      _ => AppColors.neutralText,
    };

    final statusLabel = switch (doc.uploadStatus) {
      'uploaded' => loc.document_uploaded,
      'pending' => loc.document_pending,
      'failed' => loc.document_failed,
      _ => doc.uploadStatus,
    };

    final icon = switch (doc.type) {
      'cmr' => LucideIcons.fileText,
      'pod' => LucideIcons.clipboardCheck,
      'invoice' => LucideIcons.receipt,
      _ => LucideIcons.file,
    };

    return AppCard(
      child: Row(
        children: [
          Container(
            height: 44,
            width: 44,
            decoration: BoxDecoration(
              color: theme.colorScheme.primaryContainer,
              borderRadius: AppRadius.lgAll,
            ),
            child: Icon(
              icon,
              color: theme.colorScheme.primary,
              size: 22,
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  doc.fileName,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(
                      _formatType(loc, doc.type),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AppColors.textSecondaryLight,
                      ),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                      '•',
                      style: TextStyle(color: AppColors.textSecondaryLight),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                      _formatDate(doc.uploadedAt),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AppColors.textSecondaryLight,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.sm,
              vertical: AppSpacing.xs,
            ),
            decoration: BoxDecoration(
              color: statusColor.withValues(alpha: 0.12),
              borderRadius: AppRadius.pillAll,
            ),
            child: Text(
              statusLabel,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w600,
                color: statusColor,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatType(AppLocalizations loc, String type) {
    return switch (type) {
      'cmr' => loc.document_cmr,
      'pod' => loc.document_pod,
      'invoice' => loc.document_invoice,
      _ => loc.document_other,
    };
  }

  String _formatDate(DateTime? date) {
    if (date == null) return '';
    return '${date.day.toString().padLeft(2, '0')}.'
        '${date.month.toString().padLeft(2, '0')}.'
        '${date.year}';
  }
}
