import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/auth/auth_providers.dart';
import '../../core/auth/auth_service.dart';
import '../../core/i18n/app_localizations.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/widgets/confirmation_dialog.dart';

/// Settings screen accessible from both Driver and Dispatcher modes.
///
/// Provides:
/// * **Language** selector — Română / English (radio buttons).
/// * **Theme** selector — System / Light / Dark (radio buttons).
/// * **App version** display.
/// * **Logout** button — red, at the bottom, with a confirmation dialog.
///
/// Uses an iOS-style grouped list layout with section headers and cards.
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loc = context.loc;
    final theme = Theme.of(context);
    final locale = ref.watch(localeProvider);
    final themeMode = ref.watch(themeModeProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.nav_settings),
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          // ── Language section ─────────────────────────────────────
          _SectionHeader(title: loc.settings_language),
          const SizedBox(height: AppSpacing.sm),
          Card(
            child: Column(
              children: [
                RadioListTile<Locale>(
                  title: Text(loc.settings_languageRo),
                  subtitle: const Text('Română'),
                  value: const Locale('ro'),
                  groupValue: locale,
                  onChanged: (value) {
                    if (value != null) {
                      ref.read(localeProvider.notifier).state = value;
                      // TODO: Update MaterialApp locale dynamically.
                      // This requires the locale to be lifted to a
                      // ChangeNotifierProvider and consumed by
                      // MaterialApp.locale in app.dart.
                    }
                  },
                ),
                const Divider(height: 1, indent: 16, endIndent: 16),
                RadioListTile<Locale>(
                  title: Text(loc.settings_languageEn),
                  subtitle: const Text('English'),
                  value: const Locale('en'),
                  groupValue: locale,
                  onChanged: (value) {
                    if (value != null) {
                      ref.read(localeProvider.notifier).state = value;
                      // TODO: Update MaterialApp locale dynamically.
                    }
                  },
                ),
              ],
            ),
          ),

          const SizedBox(height: AppSpacing.xxl),

          // ── Theme section ────────────────────────────────────────
          _SectionHeader(title: loc.settings_theme),
          const SizedBox(height: AppSpacing.sm),
          Card(
            child: Column(
              children: [
                RadioListTile<ThemeMode>(
                  title: Text(loc.settings_themeSystem),
                  subtitle: Text(
                    theme.brightness == Brightness.light ? 'Light' : 'Dark',
                    style: TextStyle(
                      color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                  value: ThemeMode.system,
                  groupValue: themeMode,
                  onChanged: (value) {
                    if (value != null) {
                      ref.read(themeModeProvider.notifier).state = value;
                    }
                  },
                ),
                const Divider(height: 1, indent: 16, endIndent: 16),
                RadioListTile<ThemeMode>(
                  title: Text(loc.settings_themeLight),
                  value: ThemeMode.light,
                  groupValue: themeMode,
                  onChanged: (value) {
                    if (value != null) {
                      ref.read(themeModeProvider.notifier).state = value;
                    }
                  },
                ),
                const Divider(height: 1, indent: 16, endIndent: 16),
                RadioListTile<ThemeMode>(
                  title: Text(loc.settings_themeDark),
                  value: ThemeMode.dark,
                  groupValue: themeMode,
                  onChanged: (value) {
                    if (value != null) {
                      ref.read(themeModeProvider.notifier).state = value;
                    }
                  },
                ),
              ],
            ),
          ),

          const SizedBox(height: AppSpacing.xxl),

          // ── App version ──────────────────────────────────────────
          _SectionHeader(title: loc.settings_appVersion),
          const SizedBox(height: AppSpacing.sm),
          Card(
            child: ListTile(
              title: Text(loc.settings_appVersion),
              trailing: Text(
                '1.0.0+1',
                style: TextStyle(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
            ),
          ),

          const SizedBox(height: AppSpacing.xxxl),

          // ── Logout button ────────────────────────────────────────
          SizedBox(
            width: double.infinity,
            height: 48,
            child: ElevatedButton.icon(
              onPressed: () => _handleLogout(context, ref),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.error,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
              ),
              icon: const Icon(Icons.logout),
              label: Text(loc.auth_logout),
            ),
          ),

          const SizedBox(height: AppSpacing.xxl),
        ],
      ),
    );
  }

  /// Shows a confirmation dialog and, on confirm, clears tokens and auth state.
  Future<void> _handleLogout(BuildContext context, WidgetRef ref) async {
    final confirmed = await ConfirmationDialog.show(context,
      title: context.loc.auth_logout,
      message: context.loc.auth_logoutConfirm,
      confirmLabel: context.loc.auth_logout,
      isDangerous: true,
    );
    if (confirmed == true) {
      try {
        await ref.read(authServiceProvider).logout();
      } catch (_) {
        // Best-effort logout — clear local state regardless
      }
      ref.read(currentUserProvider.notifier).state = null;
      ref.read(authStateProvider.notifier).setUnauthenticated();
    }
  }
}

/// A styled section header used in settings groups (iOS-style).
class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: AppSpacing.xs),
      child: Text(
        title.toUpperCase(),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.5,
          color: Theme.of(context).colorScheme.onSurface.withValues(alpha: 0.5),
        ),
      ),
    );
  }
}
