import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_card.dart';
import '../../dispatcher/alerts/alert_inbox_screen.dart';
import '../../dispatcher/analytics/dispatcher_analytics_screen.dart';
import '../../dispatcher/jobs/job_list_screen.dart';
import '../../driver/messages/message_list_screen.dart';
import '../../settings/settings_screen.dart';
import '../../profit_calculator/screens/profit_calculator_screen.dart';
import '../../teams/screens/teams_screen.dart';
import '../../route_planner/screens/route_planner_screen.dart';
import '../../freight_exchange/screens/freight_exchange_screen.dart';
import '../../document_center/screens/document_center_screen.dart';
import '../../local_download/screens/local_download_screen.dart';

/// A scrollable grid of quick-access tiles shown from the More tab.
///
/// Provides 11 tiles for navigating to various dispatcher features and
/// placeholder screens for Phase 2/3 features.
class MoreHubScreen extends ConsumerWidget {
  const MoreHubScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loc = context.loc;

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.nav_more),
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          AppSpacing.md,
          AppSpacing.lg,
          AppSpacing.xxl,
        ),
        children: [
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: AppSpacing.md,
            crossAxisSpacing: AppSpacing.md,
            childAspectRatio: 1.2,
            children: [
              _MoreTile(
                icon: LucideIcons.messageSquare,
                label: loc.nav_messages,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const MessageListScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.users,
                label: loc.nav_teams,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const TeamsScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.barChart3,
                label: loc.nav_analytics,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const DispatcherAnalyticsScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.briefcase,
                label: loc.nav_jobs,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const JobListScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.bell,
                label: loc.nav_alerts,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const AlertInboxScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.calculator,
                label: loc.nav_profitCalculator,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const ProfitCalculatorScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.route,
                label: loc.nav_routePlanner,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const RoutePlannerScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.search,
                label: loc.nav_freightExchange,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const FreightExchangeScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.folderOpen,
                label: loc.nav_documentCenter,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const DocumentCenterScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.download,
                label: loc.nav_localDownload,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const LocalDownloadScreen(),
                  ),
                ),
              ),
              _MoreTile(
                icon: LucideIcons.settings,
                label: loc.nav_settings,
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => const SettingsScreen(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xxl),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm),
            child: SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () => _confirmLogout(context, ref),
                icon: const Icon(Icons.logout, color: AppColors.error),
                label: Text(
                  loc.auth_logout,
                  style: const TextStyle(color: AppColors.error),
                ),
                style: OutlinedButton.styleFrom(
                  side: const BorderSide(color: AppColors.error),
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Shows a confirmation dialog and performs logout on confirm.
  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    final loc = context.loc;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(loc.auth_logout),
        content: Text(loc.auth_logoutConfirm),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: Text(loc.general_cancel),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: Text(loc.general_confirm),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      await ref.read(authServiceProvider).logout();
      ref.read(authStateProvider.notifier).setUnauthenticated();
    }
  }
}

/// A single grid tile inside [MoreHubScreen].
///
/// Displays a Lucide icon and label text on an [AppCard].
class _MoreTile extends StatelessWidget {
  const _MoreTile({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      onTap: onTap,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(icon, size: 28, color: AppColors.primary),
          const SizedBox(height: AppSpacing.sm),
          Text(
            label,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}
