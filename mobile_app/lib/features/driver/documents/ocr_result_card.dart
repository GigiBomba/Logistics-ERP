import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';

/// Displays OCR-extracted fields from a document upload.
///
/// Use after document upload completes and OCR results are available.
/// Shows extracted fields as key-value rows inside an [AppCard] with a green
/// left border accent. Includes optional confidence indicator and action
/// buttons for confirming or editing the extracted data.
///
/// If [ocrData] is null or empty, returns [SizedBox.shrink].
class OcrResultCard extends StatelessWidget {
  const OcrResultCard({
    super.key,
    required this.ocrData,
    this.onConfirm,
    this.onEdit,
  });

  /// The extracted OCR fields from [Document.ocrData].
  final Map<String, dynamic> ocrData;

  /// Called when the user taps "Confirm" to accept the OCR results.
  final VoidCallback? onConfirm;

  /// Called when the user taps "Edit" to modify the extracted values.
  final VoidCallback? onEdit;

  @override
  Widget build(BuildContext context) {
    if (ocrData.isEmpty) return const SizedBox.shrink();

    final loc = context.loc;
    final theme = Theme.of(context);

    // Separate confidence from regular fields.
    final confidence = ocrData['confidence'];
    final regularFields = <String, dynamic>{};
    for (final entry in ocrData.entries) {
      if (entry.key != 'confidence') {
        regularFields[entry.key] = entry.value;
      }
    }

    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.lg),
      child: AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Header ───────────────────────────────
            Row(
              children: [
                const Icon(
                  LucideIcons.sparkles,
                  size: 20,
                  color: AppColors.success,
                ),
                const SizedBox(width: AppSpacing.sm),
                Text(
                  loc.ocr_results,
                  style: theme.textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (confidence != null) ...[
                  const Spacer(),
                  _ConfidenceBadge(confidence: confidence),
                ],
              ],
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Green left-accent divider ────────────
            Container(
              height: 3,
              width: 48,
              decoration: BoxDecoration(
                color: AppColors.success,
                borderRadius: BorderRadius.circular(AppRadius.pill),
              ),
            ),
            const SizedBox(height: AppSpacing.md),

            // ── Extracted fields ─────────────────────
            if (regularFields.isNotEmpty)
              ...regularFields.entries.map(
                (entry) => Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                  child: _FieldRow(
                    label: _prettifyKey(entry.key),
                    value: '${entry.value}',
                  ),
                ),
              )
            else
              Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
                child: Text(
                  loc.ocr_processing,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondaryLight,
                  ),
                ),
              ),

            // ── Action buttons ───────────────────────
            if (onConfirm != null || onEdit != null) ...[
              const SizedBox(height: AppSpacing.lg),
              Row(
                children: [
                  if (onConfirm != null)
                    Expanded(
                      child: AppButton.primary(
                        label: loc.general_confirm,
                        icon: const Icon(LucideIcons.check, size: 18),
                        onPressed: onConfirm,
                      ),
                    ),
                  if (onConfirm != null && onEdit != null)
                    const SizedBox(width: AppSpacing.md),
                  if (onEdit != null)
                    Expanded(
                      child: AppButton.secondary(
                        label: loc.general_edit,
                        icon: const Icon(LucideIcons.pencil, size: 18),
                        onPressed: onEdit,
                      ),
                    ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Converts a snake_case or camelCase key into a human-readable label.
  ///
  /// Examples:
  /// - `cmr_number` → "CMR Number"
  /// - `sender_company` → "Sender Company"
  /// - `invoiceDate` → "Invoice Date"
  static String _prettifyKey(String key) {
    // Insert space before uppercase letters (camelCase → Camel Case)
    final withSpaces = key.replaceAllMapped(
      RegExp(r'([a-z])([A-Z])'),
      (m) => '${m[1]} ${m[2]}',
    );
    // Replace underscores with spaces
    final withSpaces2 = withSpaces.replaceAll('_', ' ');
    // Capitalize first letter of each word
    return withSpaces2.split(' ').map((word) {
      if (word.isEmpty) return word;
      // Preserve all-caps words like "CMR"
      if (word.length > 1 && word == word.toUpperCase()) return word;
      return word[0].toUpperCase() + word.substring(1);
    }).join(' ');
  }
}

/// A single extracted-field row with a label and value.
class _FieldRow extends StatelessWidget {
  const _FieldRow({
    required this.label,
    required this.value,
  });

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: theme.textTheme.bodySmall?.copyWith(
            color: AppColors.textSecondaryLight,
            fontSize: 11,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          value,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }
}

/// Displays the OCR confidence score as a small colored badge.
class _ConfidenceBadge extends StatelessWidget {
  const _ConfidenceBadge({required this.confidence});

  final dynamic confidence;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;

    // Convert confidence to a percentage value (0–100).
    final percent = confidence is num
        ? (confidence is double
            ? (confidence * 100).round()
            : confidence.toInt())
        : double.tryParse('$confidence')
                ?.let((v) => v > 1 ? v.round() : (v * 100).round()) ??
            0;

    final color = percent >= 90
        ? AppColors.success
        : percent >= 70
            ? AppColors.warning
            : AppColors.error;

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            percent >= 90
                ? LucideIcons.checkCircle
                : percent >= 70
                    ? LucideIcons.alertTriangle
                    : LucideIcons.xCircle,
            size: 14,
            color: color,
          ),
          const SizedBox(width: 4),
          Text(
            loc.ocr_confidence.replaceAll('{percent}', '$percent'),
            style: TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

/// Extension to enable `.let` for nullable values.
extension _LetExtension<T> on T {
  R let<R>(R Function(T) block) => block(this);
}
