import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../core/auth/auth_providers.dart';
import '../../core/i18n/app_localizations.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../shared/widgets/app_button.dart';
import '../../shared/widgets/app_text_field.dart';

/// Full-screen login page with Operion branding, email/password form, and
/// optional biometric unlock.
///
/// On successful authentication the [AuthState] is updated to `authenticated`
/// and the parent [AuthGate] automatically replaces this screen with the
/// authenticated shell.
class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen>
    with SingleTickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();

  bool _obscurePassword = true;
  bool _isLoading = false;
  String? _errorMessage;
  bool _biometricAvailable = false;

  late final AnimationController _errorAnimCtrl;
  late final Animation<Offset> _errorSlide;

  // ── Lifecycle ─────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();

    _errorAnimCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    );
    _errorSlide = Tween<Offset>(
      begin: const Offset(0, -1),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _errorAnimCtrl,
      curve: Curves.easeOut,
    ));

    _checkBiometricAvailability();
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _errorAnimCtrl.dispose();
    super.dispose();
  }

  // ── Biometric check ───────────────────────────────────────────────────

  Future<void> _checkBiometricAvailability() async {
    final available = await ref.read(biometricServiceProvider).isAvailable();
    if (mounted) setState(() => _biometricAvailable = available);
  }

  // ── Error display ─────────────────────────────────────────────────────

  void _showError(String message) {
    setState(() => _errorMessage = message);
    _errorAnimCtrl.forward();

    // Auto-dismiss after 5 seconds.
    Future.delayed(const Duration(seconds: 5), () {
      if (mounted) {
        _errorAnimCtrl.reverse().then((_) {
          if (mounted && _errorMessage == message) {
            setState(() => _errorMessage = null);
          }
        });
      }
    });
  }

  // ── Login actions ─────────────────────────────────────────────────────

  Future<void> _handleLogin() async {
    if (_isLoading) return;
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    ref.read(authStateProvider.notifier).setAuthenticating();

    final result = await ref.read(authServiceProvider).login(
          _emailController.text.trim(),
          _passwordController.text,
        );

    if (!mounted) return;
    setState(() => _isLoading = false);

    if (result.success) {
      ref.read(currentUserProvider.notifier).state = result.user;
      ref.read(authStateProvider.notifier).setAuthenticated();
    } else {
      ref.read(authStateProvider.notifier).setUnauthenticated();
      _showError(result.errorMessage ?? context.loc.auth_loginError);
    }
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
      ref.read(authStateProvider.notifier).setUnauthenticated();
      _showError(context.loc.auth_sessionExpired);
    }
  }

  // ── Build ─────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final isTablet = screenWidth >= 600;
    final contentWidth = isTablet ? 400.0 : screenWidth;

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.xxl),
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: contentWidth),
              child: Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // ── Branding ────────────────────────────────
                    const Icon(LucideIcons.truck, size: 48, color: AppColors.accent),
                    const SizedBox(height: AppSpacing.md),
                    Text(
                      context.loc.appName,
                      style: GoogleFonts.inter(
                        fontSize: 32,
                        fontWeight: FontWeight.bold,
                        color: AppColors.accent,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.xxxl),

                    // ── Login card ──────────────────────────────
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(AppSpacing.xxl),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            // Error banner (slide-in)
                            if (_errorMessage != null)
                              SlideTransition(
                                position: _errorSlide,
                                child: Container(
                                  padding: const EdgeInsets.all(AppSpacing.md),
                                  margin:
                                      const EdgeInsets.only(bottom: AppSpacing.lg),
                                  decoration: BoxDecoration(
                                    color: AppColors.errorSubtle,
                                    borderRadius: BorderRadius.circular(AppRadius.lg),
                                  ),
                                  child: Row(
                                    children: [
                                      const Icon(
                                      LucideIcons.alertCircle,
                                      color: AppColors.error,
                                      size: 18,
                                    ),
                                    const SizedBox(width: AppSpacing.sm),
                                    Expanded(
                                      child: Text(
                                        _errorMessage!,
                                        style: const TextStyle(
                                          color: AppColors.error,
                                          fontSize: 13,
                                        ),
                                      ),
                                    ),
                                  ],
                                  ),
                                ),
                              ),

                            // Email
                            AppTextField(
                              controller: _emailController,
                              labelText: context.loc.auth_email,
                              hintText: 'email@example.com',
                              prefixIcon:
                                  const Icon(LucideIcons.mail, size: 20),
                              keyboardType: TextInputType.emailAddress,
                              textInputAction: TextInputAction.next,
                              validator: (v) {
                                if (v == null || v.trim().isEmpty) {
                                  return 'Email is required';
                                }
                                if (!v.contains('@')) {
                                  return 'Enter a valid email';
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: AppSpacing.lg),

                            // Password
                            AppTextField(
                              controller: _passwordController,
                              labelText: context.loc.auth_password,
                              prefixIcon:
                                  const Icon(LucideIcons.lock, size: 20),
                              obscureText: _obscurePassword,
                              textInputAction: TextInputAction.done,
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _obscurePassword
                                      ? LucideIcons.eyeOff
                                      : LucideIcons.eye,
                                  size: 20,
                                ),
                                onPressed: () => setState(
                                    () => _obscurePassword = !_obscurePassword),
                              ),
                              validator: (v) {
                                if (v == null || v.isEmpty) {
                                  return 'Password is required';
                                }
                                return null;
                              },
                              onChanged: (_) => setState(() {}),
                            ),
                            const SizedBox(height: AppSpacing.xxl),

                            // Sign In button
                            AppButton.primary(
                              label: _isLoading
                                  ? context.loc.auth_loggingIn
                                  : context.loc.auth_loginButton,
                              isLoading: _isLoading,
                              onPressed: _handleLogin,
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),

                    // ── Forgot password ─────────────────────────
                    TextButton(
                      onPressed: () {
                        // TODO: implement forgot-password flow
                      },
                      child: Text(
                        context.loc.auth_forgotPassword,
                        style: const TextStyle(color: AppColors.accent),
                      ),
                    ),

                    // ── Biometric unlock ────────────────────────
                    if (_biometricAvailable) ...[
                      const SizedBox(height: AppSpacing.lg),
                      const Divider(),
                      const SizedBox(height: AppSpacing.md),
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
      ),
    );
  }
}
