import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/auth/auth_providers.dart';
import '../../core/i18n/app_localizations.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/widgets/app_button.dart';

/// Full-screen modal shown when the server terminates the session
/// (e.g. refresh token expired or session revoked).
///
/// Offers the user to sign in again or, if the device supports it, unlock
/// with biometrics. Back navigation is blocked so the user cannot bypass
/// the expired-session notice.
class SessionExpiredScreen extends ConsumerStatefulWidget {
  const SessionExpiredScreen({super.key});

  @override
  ConsumerState<SessionExpiredScreen> createState() =>
      _SessionExpiredScreenState();
}

class _SessionExpiredScreenState extends ConsumerState<SessionExpiredScreen> {
  bool _biometricAvailable = false;

  @override
  void initState() {
    super.initState();
    _checkBiometricAvailability();
  }

  Future<void> _checkBiometricAvailability() async {
    final available = await ref.read(biometricServiceProvider).isAvailable();
    if (mounted) setState(() => _biometricAvailable = available);
  }

  Future<void> _handleBiometricLogin() async {
    final bioOk = await ref.read(biometricServiceProvider).authenticate(
          reason: context.loc.auth_biometricTitle,
        );

    if (!bioOk || !mounted) return;

    ref.read(authStateProvider.notifier).setAuthenticating();

    final restored = await ref.read(authServiceProvider).restoreSession();

    if (!mounted) return;

    if (restored) {
      final user = await ref.read(authServiceProvider).getCurrentUser();
      if (mounted) {
        ref.read(currentUserProvider.notifier).state = user;
        ref.read(authStateProvider.notifier).setAuthenticated();
      }
    } else {
      // Restore failed — go back to login form.
      ref.read(authStateProvider.notifier).setUnauthenticated();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(context.loc.auth_sessionExpired)),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      child: Scaffold(
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.xxl),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(
                    LucideIcons.lock,
                    size: 64,
                    color: AppColors.error,
                  ),
                  const SizedBox(height: AppSpacing.xxl),
                  Text(
                    context.loc.auth_sessionExpired,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.xxl),
                  AppButton.primary(
                    label: context.loc.auth_loginButton,
                    onPressed: () async {
                      await ref.read(authServiceProvider).logout();
                      ref.read(currentUserProvider.notifier).state = null;
                      ref.read(authStateProvider.notifier).setUnauthenticated();
                    },
                  ),

                  // ── Biometric quick-login ──────────────────────
                  if (_biometricAvailable) ...[
                    const SizedBox(height: AppSpacing.xl),
                    Text(
                      context.loc.auth_biometricHint,
                      style: const TextStyle(
                        fontSize: 12,
                        color: AppColors.textSecondaryLight,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    IconButton(
                      iconSize: 40,
                      onPressed: _handleBiometricLogin,
                      icon: const Icon(
                        LucideIcons.fingerprint,
                        color: AppColors.accent,
                      ),
                      tooltip: context.loc.auth_biometricTitle,
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
