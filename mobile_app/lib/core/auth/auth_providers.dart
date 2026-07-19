import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../shared/models/user.dart';
import '../constants.dart';
import '../network/api_client.dart';
import '../network/endpoints/auth_endpoints.dart';
import '../network/message_bus.dart';
import '../storage/secure_token_store.dart';
import 'auth_service.dart';
import 'biometric_service.dart';
import 'token_manager.dart';
import 'user_role.dart';

// ---------------------------------------------------------------------------
// Foundation providers
// ---------------------------------------------------------------------------

/// Singleton [SecureTokenStore] for encrypted token persistence.
final secureTokenStoreProvider = Provider<SecureTokenStore>((ref) {
  return SecureTokenStore();
});

/// Singleton [MessageBus] for in-app event distribution.
final messageBusProvider = Provider<MessageBus>((ref) {
  return MessageBus();
});

/// Fully-configured [ApiClient] that reads tokens directly from secure
/// storage and emits [ForceLogoutEvent] when the auth interceptor detects a
/// forced logout.
final apiClientProvider = Provider<ApiClient>((ref) {
  final store = ref.read(secureTokenStoreProvider);
  final bus = ref.read(messageBusProvider);

  assert(
    AppConstants.apiKey.isNotEmpty,
    'OPERION_API_KEY not set. Pass it at build time:\n'
    '  flutter run --dart-define=OPERION_API_KEY=<key>',
  );

  return ApiClient.create(
    baseUrl: AppConstants.baseUrl,
    apiKey: AppConstants.apiKey,
    getAccessToken: () => store.getAccessToken(),
    getRefreshToken: () => store.getRefreshToken(),
    saveTokens: (access, refresh) => store.saveTokens(access, refresh),
    clearTokens: () => store.clearTokens(),
    onForceLogout: () => bus.emit(const ForceLogoutEvent()),
  );
});

/// Wraps [ApiClient] with endpoint-specific methods.
final authEndpointsProvider = Provider<AuthEndpoints>((ref) {
  return AuthEndpoints(ref.read(apiClientProvider));
});

// ---------------------------------------------------------------------------
// Auth service providers
// ---------------------------------------------------------------------------

/// Singleton [TokenManager] that manages token lifecycle.
///
/// Calls [TokenManager.initialize] eagerly so that [TokenManager.isAuthenticated]
/// reflects the persisted session state as soon as the async init completes.
final tokenManagerProvider = Provider<TokenManager>((ref) {
  final manager = TokenManager(
    ref.read(secureTokenStoreProvider),
    ref.read(authEndpointsProvider),
    ref.read(messageBusProvider),
  );
  // Fire-and-forget: populates the in-memory `_hasTokens` flag.
  manager.initialize();
  return manager;
});

/// Singleton [AuthService] for high-level authentication operations.
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(
    ref.read(authEndpointsProvider),
    ref.read(tokenManagerProvider),
    ref.read(secureTokenStoreProvider),
  );
});

/// Singleton [BiometricService] for local biometric authentication.
final biometricServiceProvider = Provider<BiometricService>((ref) {
  return BiometricService();
});

// ---------------------------------------------------------------------------
// Auth state management
// ---------------------------------------------------------------------------

/// Possible authentication states.
enum AuthState {
  /// No valid session exists.
  unauthenticated,

  /// A login or session-restoration request is in progress.
  authenticating,

  /// The user has a valid session.
  authenticated,

  /// The session was terminated by the server (e.g. refresh token expired
  /// or session revoked).
  sessionExpired,
}

/// [StateNotifier] that drives the current [AuthState].
///
/// Listens to the [MessageBus] for [ForceLogoutEvent] so that forced logouts
/// triggered by the auth interceptor automatically transition to
/// [AuthState.sessionExpired].
final authStateProvider =
    StateNotifierProvider<AuthStateNotifier, AuthState>((ref) {
  return AuthStateNotifier(ref);
});

class AuthStateNotifier extends StateNotifier<AuthState> {
  final Ref _ref;
  StreamSubscription? _messageBusSubscription;

  AuthStateNotifier(this._ref) : super(AuthState.unauthenticated) {
    _messageBusSubscription = _ref.read(messageBusProvider).stream.listen(
      (event) {
        if (event is ForceLogoutEvent) {
          state = AuthState.sessionExpired;
        }
      },
    );
  }

  @override
  void dispose() {
    _messageBusSubscription?.cancel();
    super.dispose();
  }

  void setAuthenticating() => state = AuthState.authenticating;
  void setAuthenticated() => state = AuthState.authenticated;
  void setUnauthenticated() => state = AuthState.unauthenticated;
  void setSessionExpired() => state = AuthState.sessionExpired;
}

/// The currently signed-in [User], or `null` when no session exists.
final currentUserProvider = StateProvider<User?>((ref) => null);

/// The current user's role derived from [currentUserProvider].
final currentUserRoleProvider = Provider<UserRole?>((ref) {
  final user = ref.watch(currentUserProvider);
  if (user == null) return null;
  return userRoleFromString(user.role);
});

// ---------------------------------------------------------------------------
// Navigation / app preferences
// ---------------------------------------------------------------------------

/// The current locale selected by the user (default: Romanian).
final localeProvider = StateProvider<Locale>((ref) => const Locale('ro'));

/// The current theme mode (default: system).
final themeModeProvider = StateProvider<ThemeMode>((ref) => ThemeMode.system);

/// Unread messages badge count.
final unreadMessagesCountProvider = StateProvider<int>((ref) => 0);

/// Unread alerts badge count.
final unreadAlertsCountProvider = StateProvider<int>((ref) => 0);

/// Whether the device currently has internet connectivity.
final isOfflineProvider = StateProvider<bool>((ref) => false);
