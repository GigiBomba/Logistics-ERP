import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/theme/app_spacing.dart';

/// Displays how recently the data was updated.
///
/// Shows "Pending sync..." when [isPending] is true, otherwise shows
/// a relative timestamp like "Just now", "5 min ago", "2 hours ago".
class StalenessIndicator extends StatelessWidget {
  const StalenessIndicator({
    super.key,
    this.lastUpdated,
    this.isPending = false,
    this.pendingText,
    this.neverText,
  });

  final DateTime? lastUpdated;
  final bool isPending;
  final String? pendingText;
  final String? neverText;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final secondary = theme.colorScheme.onSurface.withValues(alpha: 0.6);

    IconData icon;
    String text;

    if (isPending) {
      icon = LucideIcons.cloudOff;
      text = pendingText ?? 'Pending sync...';
    } else if (lastUpdated == null) {
      icon = LucideIcons.clock;
      text = neverText ?? 'Never';
    } else {
      final delta = DateTime.now().difference(lastUpdated!);
      text = _formatDelta(delta);
      icon = delta.isNegative || delta.inMinutes < 1
          ? LucideIcons.checkCircle2
          : LucideIcons.clock;
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 14, color: secondary),
        const SizedBox(width: AppSpacing.xs),
        Text(
          text,
          style: TextStyle(
            fontSize: 11,
            color: secondary,
            fontWeight: FontWeight.w400,
          ),
        ),
      ],
    );
  }

  String _formatDelta(Duration delta) {
    if (delta.isNegative) return 'Just now';
    if (delta.inMinutes < 1) return 'Just now';
    if (delta.inMinutes < 60) return '${delta.inMinutes} min ago';
    if (delta.inHours < 24) return '${delta.inHours} hours ago';
    return '${delta.inDays} days ago';
  }
}
