import 'package:flutter/material.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/theme/app_spacing.dart';

/// A thin banner that shows when the device is offline.
///
/// Accepts a plain [isOffline] boolean. In production this would be
/// driven by [ConnectivityMonitor] from `core/sync/connectivity_monitor.dart`.
class OfflineBanner extends StatelessWidget {
  const OfflineBanner({
    super.key,
    required this.isOffline,
  });

  final bool isOffline;

  @override
  Widget build(BuildContext context) {
    return AnimatedCrossFade(
      firstChild: const SizedBox.shrink(),
      secondChild: Container(
        width: double.infinity,
        color: Colors.amber.shade700,
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.sm,
        ),
        child: const SafeArea(
          bottom: false,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(LucideIcons.wifiOff, size: 16, color: Colors.white),
              SizedBox(width: AppSpacing.sm),
              Text(
                'You are offline',
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
      crossFadeState:
          isOffline ? CrossFadeState.showSecond : CrossFadeState.showFirst,
      duration: const Duration(milliseconds: 300),
    );
  }
}
