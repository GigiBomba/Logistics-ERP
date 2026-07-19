import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../../core/auth/auth_providers.dart';
import '../home/dispatcher_providers.dart';

/// Full-screen detail view for a single alert / approval request.
///
/// Dispatchers can review the alert information, then **approve** or
/// **reject** it. Rejection prompts for a mandatory reason via a dialog.
///
/// After a successful action the screen pops back and the alerts list is
/// refreshed.
class ApprovalDetailScreen extends ConsumerWidget {
  const ApprovalDetailScreen({super.key, required this.alertId});

  /// The numeric identifier of the alert to display.
  final int alertId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loc = context.loc;
    final alertAsync = ref.watch(dispatcherAlertDetailProvider(alertId));

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.dispatcher_approve),
      ),
      body: alertAsync.when(
        loading: () => const _DetailShimmer(),
        error: (err, stack) => _ErrorRetry(
          message: err.toString(),
          onRetry: () =>
              ref.invalidate(dispatcherAlertDetailProvider(alertId)),
        ),
        data: (alert) {
          if (alert == null) {
            return Center(
              child: Text(
                loc.general_error,
                style: const TextStyle(color: AppColors.neutralText),
              ),
            );
          }
          return _ApprovalContent(
            alert: alert,
            alertId: alertId,
          );
        },
      ),
    );
  }
}

/// Shimmer loading placeholder for the detail screen.
class _DetailShimmer extends StatelessWidget {
  const _DetailShimmer();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: const [
        ShimmerLoader(child: _ShimmerBlock(height: 24, width: 0.3)),
        SizedBox(height: AppSpacing.md),
        ShimmerLoader(child: _ShimmerBlock(height: 32, width: 0.7)),
        SizedBox(height: AppSpacing.lg),
        ShimmerLoader(child: _ShimmerBlock(height: 60, width: 1.0)),
        SizedBox(height: AppSpacing.lg),
        ShimmerLoader(child: _ShimmerBlock(height: 48, width: 1.0)),
        SizedBox(height: AppSpacing.lg),
        ShimmerLoader(child: _ShimmerBlock(height: 48, width: 1.0)),
      ],
    );
  }
}

/// A rectangular shimmer placeholder with configurable height and width.
class _ShimmerBlock extends StatelessWidget {
  const _ShimmerBlock({required this.height, this.width = 1.0});

  final double height;
  final double width;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: width,
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

/// Error state with retry button.
class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({
    required this.message,
    required this.onRetry,
  });

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xxl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(
              Icons.error_outline,
              size: 48,
              color: AppColors.error,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              loc.general_error,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              message,
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: AppColors.neutralText,
              ),
            ),
            const SizedBox(height: AppSpacing.lg),
            ElevatedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: Text(loc.general_retry),
            ),
          ],
        ),
      ),
    );
  }
}

/// The main approval content with details and action buttons.
class _ApprovalContent extends ConsumerStatefulWidget {
  const _ApprovalContent({
    required this.alert,
    required this.alertId,
  });

  final Map<String, dynamic> alert;
  final int alertId;

  @override
  ConsumerState<_ApprovalContent> createState() => _ApprovalContentState();
}

class _ApprovalContentState extends ConsumerState<_ApprovalContent> {
  bool _isApproving = false;
  bool _isRejecting = false;
  TextEditingController? _reasonController;

  @override
  void dispose() {
    _reasonController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final loc = context.loc;
    final alert = widget.alert;
    final type = alert['type'] as String? ?? '';
    final severity = alert['severity'] as String? ?? 'info';
    final title = alert['title'] as String? ?? '';
    final description = alert['description'] as String? ?? '';
    final relatedEntityId = alert['related_entity_id'] as String?;
    final relatedEntityType = alert['related_entity_type'] as String?;
    final createdAtStr = alert['created_at'] as String?;

    return Column(
      children: [
        // ── Scrollable detail content ──────────────
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Alert type + severity badge ──────
                Row(
                  children: [
                    Icon(
                      _typeIcon(type),
                      size: 28,
                      color: _severityColor(severity),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    _SeverityBadge(severity: severity),
                    const Spacer(),
                    Text(
                      _typeLabel(type, loc),
                      style: TextStyle(
                        fontSize: 13,
                        color: AppColors.neutralText,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.lg),

                // ── Title ───────────────────────────
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: AppSpacing.md),

                // ── Description ─────────────────────
                Text(
                  description,
                  style: TextStyle(
                    fontSize: 15,
                    height: 1.5,
                    color: AppColors.neutralText,
                  ),
                ),
                const SizedBox(height: AppSpacing.xxl),

                // ── Related entity ──────────────────
                if (relatedEntityId != null &&
                    relatedEntityId.isNotEmpty) ...[
                  AppCard(
                    child: Row(
                      children: [
                        const Icon(
                          Icons.link,
                          size: 18,
                          color: AppColors.accent,
                        ),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(
                          child: Text(
                            '${_entityLabel(relatedEntityType, loc)} #$relatedEntityId',
                            style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                        const Icon(
                          Icons.open_in_new,
                          size: 16,
                          color: AppColors.accent,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xxl),
                ],

                // ── Created at ─────────────────────
                Row(
                  children: [
                    const Icon(
                      Icons.schedule,
                      size: 16,
                      color: AppColors.neutralText,
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Text(
                      _formatTimestamp(createdAtStr, loc),
                      style: TextStyle(
                        fontSize: 13,
                        color: AppColors.neutralText,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),

        // ── Bottom action buttons ───────────────────
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(
              AppSpacing.lg,
              AppSpacing.sm,
              AppSpacing.lg,
              AppSpacing.md,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                AppButton.primary(
                  label: loc.dispatcher_approve,
                  isLoading: _isApproving,
                  onPressed:
                      _isApproving || _isRejecting ? null : () => _approve(loc),
                ),
                const SizedBox(height: AppSpacing.sm),
                AppButton.danger(
                  label: loc.dispatcher_reject,
                  isLoading: _isRejecting,
                  onPressed:
                      _isApproving || _isRejecting ? null : () => _reject(loc),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  /// Calls the approve endpoint and handles success/error.
  Future<void> _approve(AppLocalizations loc) async {
    setState(() => _isApproving = true);
    try {
      final endpoints = ref.read(dispatcherEndpointsProvider);
      await endpoints.approveAction(widget.alertId.toString());
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Approved')),
      );
      ref.invalidate(dispatcherAlertsProvider);
      final alerts = await ref.read(dispatcherAlertsProvider.future);
      final unreadCount = alerts.where((a) => a['is_read'] != true).length;
      ref.read(unreadAlertsCountProvider.notifier).state = unreadCount;
      Navigator.of(context).pop();
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${loc.general_error}: $e')),
      );
    } finally {
      if (context.mounted) setState(() => _isApproving = false);
    }
  }

  /// Shows a dialog for the rejection reason, then calls the reject endpoint.
  Future<void> _reject(AppLocalizations loc) async {
    _reasonController?.dispose();
    _reasonController = TextEditingController();
    final reasonController = _reasonController!;
    final reason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(loc.dispatcher_reject),
        content: TextField(
          controller: reasonController,
          autofocus: true,
          decoration: InputDecoration(
            hintText: loc.general_edit,
            labelText: loc.general_edit,
            border: const OutlineInputBorder(),
          ),
          maxLines: 3,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: Text(loc.general_cancel),
          ),
          ElevatedButton(
            onPressed: () =>
                Navigator.of(ctx).pop(reasonController.text),
            child: Text(loc.general_confirm),
          ),
        ],
      ),
    );

    if (reason == null || reason.trim().isEmpty) return;

    setState(() => _isRejecting = true);
    try {
      final endpoints = ref.read(dispatcherEndpointsProvider);
      await endpoints.rejectAction(
        widget.alertId.toString(),
        reason: reason.trim(),
      );
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Rejected')),
      );
      ref.invalidate(dispatcherAlertsProvider);
      final alerts = await ref.read(dispatcherAlertsProvider.future);
      final unreadCount = alerts.where((a) => a['is_read'] != true).length;
      ref.read(unreadAlertsCountProvider.notifier).state = unreadCount;
      Navigator.of(context).pop();
    } catch (e) {
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${loc.general_error}: $e')),
      );
    } finally {
      if (context.mounted) setState(() => _isRejecting = false);
    }
  }

  /// Returns the icon for the given alert type.
  IconData _typeIcon(String type) {
    return switch (type) {
      'delay' => Icons.access_time,
      'maintenance' => Icons.build_outlined,
      'document_expiry' => Icons.description_outlined,
      'compliance' => Icons.shield_outlined,
      _ => Icons.notifications_outlined,
    };
  }

  /// Returns the severity color.
  Color _severityColor(String severity) {
    return switch (severity) {
      'critical' || 'high' => AppColors.error,
      'medium' => AppColors.warning,
      'low' || 'info' => AppColors.info,
      _ => AppColors.neutralText,
    };
  }

  /// Returns the localized label for an alert type.
  String _typeLabel(String type, AppLocalizations loc) {
    return switch (type) {
      'delay' => loc.alert_delay,
      'maintenance' => loc.alert_maintenance,
      'document_expiry' => loc.alert_documentExpiry,
      'compliance' => loc.alert_compliance,
      _ => type,
    };
  }

  /// Returns the localized entity type label.
  String _entityLabel(String? entityType, AppLocalizations loc) {
    return switch (entityType) {
      'transport' => loc.nav_transports,
      'vehicle' => loc.nav_fleet,
      _ => entityType ?? '',
    };
  }

  /// Formats a timestamp for display.
  String _formatTimestamp(String? isoString, AppLocalizations loc) {
    if (isoString == null) return '';
    final date = DateTime.tryParse(isoString);
    if (date == null) return isoString;
    final dateFormat = DateFormat.yMd(loc.locale.languageCode)
        .add_jm();
    return dateFormat.format(date);
  }
}

/// A small coloured badge indicating the alert severity level.
class _SeverityBadge extends StatelessWidget {
  const _SeverityBadge({required this.severity});

  final String severity;

  @override
  Widget build(BuildContext context) {
    final (Color textColor, Color bgColor, String label) = switch (severity) {
      'critical' => (AppColors.errorText, AppColors.errorSubtle, 'Critical'),
      'high' => (AppColors.errorText, AppColors.errorSubtle, 'High'),
      'medium' => (AppColors.warningText, AppColors.warningSubtle, 'Medium'),
      'low' => (AppColors.infoText, AppColors.infoSubtle, 'Low'),
      _ => (AppColors.infoText, AppColors.infoSubtle, 'Info'),
    };

    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: AppRadius.smAll,
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: textColor,
        ),
      ),
    );
  }
}
