import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'auth_providers.dart';
import 'user_role.dart';
import '../../features/auth/login_screen.dart';
import '../../features/auth/session_expired_screen.dart';
import '../../features/driver/driver_shell.dart';
import '../../features/dispatcher/dispatcher_shell.dart';

/// Top-level gate that renders the correct navigation shell based on the
/// current user's role.
///
/// Shows [LoginScreen] when the user is not authenticated.
/// Once authenticated, uses [currentUserRoleProvider] to choose between
/// [DriverShell] and [DispatcherShell].
///
/// On startup, attempts to restore any persisted session so that returning
/// users are automatically signed in without re-entering credentials.
class ModeRouter extends ConsumerStatefulWidget {
  const ModeRouter({super.key});

  @override
  ConsumerState<ModeRouter> createState() => _ModeRouterState();
}

class _ModeRouterState extends ConsumerState<ModeRouter> {
  @override
  void initState() {
    super.initState();
    // Attempt session restoration after the first frame so that all
    // providers (TokenManager, AuthService, etc.) are fully initialized.
    WidgetsBinding.instance.addPostFrameCallback((_) => _restoreSession());
  }

  Future<void> _restoreSession() async {
    final tokenManager = ref.read(tokenManagerProvider);
    final authService = ref.read(authServiceProvider);

    // Quick check: do we even have a stored refresh token?
    final refreshToken = await tokenManager.getRefreshToken();
    if (refreshToken == null || refreshToken.isEmpty) {
      return; // No stored session — stay on LoginScreen
    }

    ref.read(authStateProvider.notifier).setAuthenticating();

    final restored = await authService.restoreSession();
    if (!mounted) return;

    if (restored) {
      final user = await authService.getCurrentUser();
      if (mounted) {
        ref.read(currentUserProvider.notifier).state = user;
        ref.read(authStateProvider.notifier).setAuthenticated();
      }
    } else {
      ref.read(authStateProvider.notifier).setUnauthenticated();
    }
  }

  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authStateProvider);
    final user = ref.watch(currentUserProvider);

    if (authState == AuthState.sessionExpired) {
      return const SessionExpiredScreen();
    }
    if (authState == AuthState.unauthenticated || user == null) {
      return const LoginScreen();
    }
    if (authState == AuthState.authenticating) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }

    // authenticated + user exists
    final role = ref.watch(currentUserRoleProvider);
    return switch (role?.shellVariant) {
      AppShellVariant.driverShell => const DriverShell(),
      AppShellVariant.managerShell => const DispatcherShell(),
      null => const LoginScreen(),
    };
  }
}

/// Convenience alias so that `app.dart` can reference it as `AuthGate`.
typedef AuthGate = ModeRouter;
