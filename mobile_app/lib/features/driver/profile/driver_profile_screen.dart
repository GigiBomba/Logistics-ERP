import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';
import 'package:lucide_icons_flutter/lucide_icons.dart';

import '../../../core/auth/auth_providers.dart';
import '../../../core/i18n/app_localizations.dart';
import '../../../core/theme/app_colors.dart';
import '../../../core/theme/app_spacing.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_text_field.dart';
import '../../../shared/widgets/confirmation_dialog.dart';
import '../../../shared/widgets/empty_state.dart';
import '../../../shared/widgets/shimmer_loader.dart';
import '../../settings/settings_screen.dart';
import '../documents/document_list_screen.dart';
import '../expenses/expense_list_screen.dart';
import '../notifications/driver_notifications_screen.dart';
import '../vehicle/vehicle_detail_screen.dart';
import 'driver_profile_providers.dart';

/// Driver profile screen with self-service document upload.
///
/// Displays a header with avatar and driver name, followed by sections for
/// **Personal Info**, **Driver Info** (license details), **Documents**
/// (license, passport, ADR certificate with upload capability), and **Quick
/// Links** to vehicle info, documents, notifications, and settings.
///
/// Supports an inline edit mode for personal information fields. The screen
/// handles loading (shimmer skeleton), error (retry panel), and empty states.
///
/// ---
/// ## States
///
/// | State    | Widget                          |
/// |----------|---------------------------------|
/// | loading  | [_ProfileShimmer]               |
/// | error    | Centered error icon + retry     |
/// | empty    | [_ProfileEmpty]                 |
/// | data     | Full scrollable profile layout  |
class DriverProfileScreen extends ConsumerStatefulWidget {
  const DriverProfileScreen({super.key});

  @override
  ConsumerState<DriverProfileScreen> createState() =>
      _DriverProfileScreenState();
}

class _DriverProfileScreenState extends ConsumerState<DriverProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  bool _editing = false;

  /// Original values captured when entering edit mode, used to revert on cancel.
  String _originalName = '';
  String _originalEmail = '';
  String _originalPhone = '';

  @override
  void initState() {
    super.initState();
    // Listen for profile data and pre-populate editing controllers once.
    ref.listenManual(userProfileProvider, (previous, next) {
      next.whenOrNull(
        data: (data) {
          if (!_editing) {
            _nameController.text = data['fullName'] as String? ?? '';
            _emailController.text = data['email'] as String? ?? '';
            _phoneController.text = data['phone'] as String? ?? '';
          }
        },
      );
    });
  }

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    super.dispose();
  }

  // ---------------------------------------------------------------------------
  // Build
  // ---------------------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(userProfileProvider);

    return profileAsync.when(
      loading: () => _buildLoadingShimmer(context),
      error: (error, stack) => _buildError(context, ref, error),
      data: (data) => _buildProfile(context, ref, data),
    );
  }

  // ---------------------------------------------------------------------------
  // Loading shimmer
  // ---------------------------------------------------------------------------

  Widget _buildLoadingShimmer(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(context.loc.nav_profile)),
      body: const _ProfileShimmer(),
    );
  }

  // ---------------------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------------------

  Widget _buildError(BuildContext context, WidgetRef ref, Object error) {
    final loc = context.loc;
    return Scaffold(
      appBar: AppBar(title: Text(loc.nav_profile)),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xxl),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                LucideIcons.alertCircle,
                size: 48,
                color: Theme.of(context).colorScheme.error,
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                loc.general_error,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: Theme.of(context).colorScheme.error,
                    ),
              ),
              const SizedBox(height: AppSpacing.xs),
              Text(
                error.toString(),
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context)
                          .colorScheme
                          .onSurface
                          .withValues(alpha: 0.5),
                    ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: AppSpacing.lg),
              FilledButton.icon(
                onPressed: () => ref.invalidate(userProfileProvider),
                icon: const Icon(LucideIcons.refreshCw, size: 18),
                label: Text(loc.general_retry),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Main profile layout
  // ---------------------------------------------------------------------------

  Widget _buildProfile(
    BuildContext context,
    WidgetRef ref,
    Map<String, dynamic> data,
  ) {
    final loc = context.loc;
    final theme = Theme.of(context);

    final fullName = data['fullName'] as String? ?? '';
    final email = data['email'] as String? ?? '';
    final phone = data['phone'] as String? ?? '';
    final role = data['role'] as String? ?? 'driver';
    final avatarUrl = data['avatarUrl'] as String?;

    // Nested driver profile
    final driverProfile =
        data['driverProfile'] as Map<String, dynamic>? ?? <String, dynamic>{};
    final licenseNumber = driverProfile['licenseNumber'] as String?;
    final licenseCategory = driverProfile['licenseCategory'] as String?;
    final licenseExpiry = driverProfile['licenseExpiry'] as String?;

    // Driver documents
    final documents =
        (data['documents'] as List<dynamic>?)?.cast<Map<String, dynamic>>() ??
            <Map<String, dynamic>>[];

    // Check if we have any meaningful data beyond defaults.
    final hasData = fullName.isNotEmpty || email.isNotEmpty;
    if (!hasData) {
      return Scaffold(
        appBar: AppBar(title: Text(loc.nav_profile)),
        body: const _ProfileEmpty(),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(loc.nav_profile),
        actions: [
          if (!_editing)
            IconButton(
              icon: const Icon(LucideIcons.pencil),
              tooltip: loc.general_edit,
              onPressed: () => _startEditing(data),
            )
          else ...[
            IconButton(
              icon: const Icon(LucideIcons.x),
              tooltip: loc.general_cancel,
              onPressed: _cancelEditing,
            ),
          ],
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          ref.invalidate(userProfileProvider);
          await ref.read(userProfileProvider.future);
        },
        child: ListView(
          padding: const EdgeInsets.only(bottom: AppSpacing.xhuge),
          children: [
            // ── Header ────────────────────────────────────────────
            _buildHeader(context, fullName, role, avatarUrl),

            // ── Personal Info ─────────────────────────────────────
            _SectionHeader(title: loc.profile_personalInfo),
            const SizedBox(height: AppSpacing.sm),
            Form(
              key: _formKey,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                child: _buildPersonalInfoCard(loc, fullName, email, phone),
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            // ── Driver Info ───────────────────────────────────────
            _SectionHeader(title: loc.profile_driverInfo),
            const SizedBox(height: AppSpacing.sm),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              child: _buildDriverInfoCard(
                loc,
                theme,
                licenseNumber,
                licenseCategory,
                licenseExpiry,
              ),
            ),
            const SizedBox(height: AppSpacing.xl),

            // ── Save button (edit mode only) ──────────────────────
            if (_editing)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                child: _buildSaveButton(loc),
              ),
            if (_editing) const SizedBox(height: AppSpacing.xl),

            // ── Documents ─────────────────────────────────────────
            _SectionHeader(title: loc.driver_documents),
            const SizedBox(height: AppSpacing.sm),
            _buildDocumentsSection(context, loc, documents),
            const SizedBox(height: AppSpacing.xl),

            // ── Quick Links ───────────────────────────────────────
            _SectionHeader(title: loc.profile_quickLinks),
            const SizedBox(height: AppSpacing.sm),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              child: _buildQuickLinks(context, loc),
            ),
            const SizedBox(height: AppSpacing.xxl),

            // ── Logout ────────────────────────────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
              child: AppButton.danger(
                label: loc.auth_logout,
                icon: const Icon(Icons.logout, size: 18),
                onPressed: () => _handleLogout(context, ref),
              ),
            ),
            const SizedBox(height: AppSpacing.lg),

            // ── App version ───────────────────────────────────────
            Center(
              child: Text(
                '${loc.settings_appVersion}: 1.0.0',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Header
  // ---------------------------------------------------------------------------

  Widget _buildHeader(
    BuildContext context,
    String fullName,
    String role,
    String? avatarUrl,
  ) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: isDark
              ? [AppColors.darkOverlay, AppColors.darkSurface]
              : [
                  AppColors.accent.withValues(alpha: 0.08),
                  AppColors.accent.withValues(alpha: 0.02),
                ],
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
        ),
      ),
      padding: const EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.xl,
        AppSpacing.lg,
        AppSpacing.xxl,
      ),
      child: Column(
        children: [
          // Avatar
          CircleAvatar(
            radius: 40,
            backgroundColor: AppColors.accent.withValues(alpha: 0.15),
            backgroundImage:
                avatarUrl != null && avatarUrl.isNotEmpty
                    ? NetworkImage(avatarUrl)
                    : null,
            child: (avatarUrl == null || avatarUrl.isEmpty)
                ? Text(
                    _initials(fullName),
                    style: TextStyle(
                      color: AppColors.accent,
                      fontSize: 28,
                      fontWeight: FontWeight.w600,
                    ),
                  )
                : null,
          ),
          const SizedBox(height: AppSpacing.md),
          // Name
          Text(
            fullName.isNotEmpty ? fullName : 'Driver',
            style: theme.textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: AppSpacing.xs),
          // Role
          Text(
            _formatRole(role),
            style: TextStyle(
              fontSize: 13,
              color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Personal Info card
  // ---------------------------------------------------------------------------

  Widget _buildPersonalInfoCard(
    AppLocalizations loc,
    String fullName,
    String email,
    String phone,
  ) {
    return AppCard(
      child: Column(
        children: [
          _InfoRow(
            icon: LucideIcons.user,
            label: loc.profile_displayName,
            value: fullName,
            editing: _editing,
            controller: _nameController,
            validator: (v) =>
                (v == null || v.trim().isEmpty) ? 'Required' : null,
          ),
          const Divider(height: 1, indent: 48, endIndent: 16),
          _InfoRow(
            icon: LucideIcons.mail,
            label: loc.auth_email,
            value: email,
            editing: _editing,
            controller: _emailController,
            keyboardType: TextInputType.emailAddress,
            validator: (v) {
              if (v == null || v.trim().isEmpty) return 'Required';
              if (!v.contains('@')) return 'Invalid email';
              return null;
            },
          ),
          const Divider(height: 1, indent: 48, endIndent: 16),
          _InfoRow(
            icon: LucideIcons.phone,
            label: loc.profile_phone,
            value: phone,
            editing: _editing,
            controller: _phoneController,
            keyboardType: TextInputType.phone,
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Driver Info card
  // ---------------------------------------------------------------------------

  Widget _buildDriverInfoCard(
    AppLocalizations loc,
    ThemeData theme,
    String? licenseNumber,
    String? licenseCategory,
    String? licenseExpiry,
  ) {
    final hasDriverInfo = licenseNumber != null ||
        licenseCategory != null ||
        licenseExpiry != null;

    if (!hasDriverInfo) {
      return AppCard(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.md),
          child: Row(
            children: [
              Icon(
                LucideIcons.info,
                size: 20,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Text(
                  loc.profile_noDriverInfo,
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }

    return AppCard(
      child: Column(
        children: [
          if (licenseNumber != null)
            _InfoRow(
              icon: LucideIcons.idCard,
              label: loc.profile_licenseNumber,
              value: licenseNumber,
              editing: false,
            ),
          if (licenseNumber != null && licenseCategory != null)
            const Divider(height: 1, indent: 48, endIndent: 16),
          if (licenseCategory != null)
            _InfoRow(
              icon: LucideIcons.list,
              label: loc.profile_licenseCategory,
              value: licenseCategory,
              editing: false,
            ),
          if (licenseCategory != null && licenseExpiry != null)
            const Divider(height: 1, indent: 48, endIndent: 16),
          if (licenseExpiry != null)
            _InfoRow(
              icon: LucideIcons.calendar,
              label: loc.profile_licenseExpiry,
              value: licenseExpiry,
              editing: false,
              valueColor: _expiryColor(licenseExpiry),
            ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Save button
  // ---------------------------------------------------------------------------

  Widget _buildSaveButton(AppLocalizations loc) {
    final isUpdating = ref.watch(profileUpdatingProvider);

    return AppButton.primary(
      label: loc.general_save,
      icon: const Icon(LucideIcons.check, size: 18),
      isLoading: isUpdating,
      onPressed: isUpdating ? null : () => _saveProfile(),
    );
  }

  // ---------------------------------------------------------------------------
  // Documents section (horizontal scroll)
  // ---------------------------------------------------------------------------

  Widget _buildDocumentsSection(
    BuildContext context,
    AppLocalizations loc,
    List<Map<String, dynamic>> documents,
  ) {
    // Define the three expected driver document types.
    final docTypes = [
      _DriverDocType(
        key: 'license',
        icon: LucideIcons.idCard,
        label: loc.profile_documentLicense,
      ),
      _DriverDocType(
        key: 'passport',
        icon: LucideIcons.bookOpen,
        label: loc.profile_documentPassport,
      ),
      _DriverDocType(
        key: 'adr',
        icon: LucideIcons.shield,
        label: loc.profile_documentAdr,
      ),
    ];

    if (documents.isEmpty) {
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
        child: EmptyState(
          icon: const Icon(LucideIcons.fileText),
          title: loc.profile_noDocuments,
          subtitle: loc.document_upload,
        ),
      );
    }

    return SizedBox(
      height: 170,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
        itemCount: docTypes.length,
        separatorBuilder: (_, __) => const SizedBox(width: AppSpacing.sm),
        itemBuilder: (context, index) {
          final docType = docTypes[index];
          final existingDoc = documents.cast<Map<String, dynamic>?>().firstWhere(
                (d) => d?['type'] == docType.key,
                orElse: () => null,
              );
          final hasDocument = existingDoc != null;
          final expiryDate = existingDoc?['expiryDate'] as String?;
          final status = existingDoc?['status'] as String? ?? 'missing';

          return _DriverDocumentCard(
            icon: docType.icon,
            label: docType.label,
            expiryDate: expiryDate,
            status: status,
            hasDocument: hasDocument,
            onUpload: () => _pickAndUploadDocument(docType.key),
          );
        },
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Quick Links
  // ---------------------------------------------------------------------------

  Widget _buildQuickLinks(BuildContext context, AppLocalizations loc) {
    return AppCard(
      child: Column(
        children: [
          _LinkTile(
            icon: LucideIcons.truck,
            title: loc.vehicle_assigned,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const VehicleDetailScreen(),
              ),
            ),
          ),
          const Divider(height: 1, indent: 48, endIndent: 16),
          _LinkTile(
            icon: LucideIcons.fileText,
            title: loc.nav_documents,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const DocumentListScreen(),
              ),
            ),
          ),
          const Divider(height: 1, indent: 48, endIndent: 16),
          _LinkTile(
            icon: LucideIcons.receipt,
            title: loc.driver_expenses,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const ExpenseListScreen(),
              ),
            ),
          ),
          const Divider(height: 1, indent: 48, endIndent: 16),
          _LinkTile(
            icon: LucideIcons.bell,
            title: loc.nav_notifications,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const DriverNotificationsScreen(),
              ),
            ),
          ),
          const Divider(height: 1, indent: 48, endIndent: 16),
          _LinkTile(
            icon: LucideIcons.settings,
            title: loc.nav_settings,
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const SettingsScreen(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  /// Toggles edit mode and populates controllers with current profile data.
  void _startEditing(Map<String, dynamic> data) {
    _originalName = data['fullName'] as String? ?? '';
    _originalEmail = data['email'] as String? ?? '';
    _originalPhone = data['phone'] as String? ?? '';
    _nameController.text = _originalName;
    _emailController.text = _originalEmail;
    _phoneController.text = _originalPhone;
    setState(() => _editing = true);
  }

  /// Cancels edit mode and resets controllers to their original values.
  void _cancelEditing() {
    _nameController.text = _originalName;
    _emailController.text = _originalEmail;
    _phoneController.text = _originalPhone;
    setState(() => _editing = false);
  }

  /// Persists the edited profile data via PATCH `/mobile/user/profile`.
  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;

    ref.read(profileUpdatingProvider.notifier).state = true;
    try {
      final client = ref.read(apiClientProvider);
      await client.patch('/mobile/user/profile', data: {
        'fullName': _nameController.text.trim(),
        'email': _emailController.text.trim(),
        'phone': _phoneController.text.trim(),
      });

      // Update the local User model in auth state.
      final currentUser = ref.read(currentUserProvider);
      if (currentUser != null) {
        ref.read(currentUserProvider.notifier).state = currentUser.copyWith(
          fullName: _nameController.text.trim(),
          email: _emailController.text.trim(),
        );
      }

      // Refresh the full profile from the server.
      ref.invalidate(userProfileProvider);

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('${context.loc.general_save} ✓')),
        );
      }

      setState(() => _editing = false);
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Unable to save profile. Check your connection and try again.'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        ref.read(profileUpdatingProvider.notifier).state = false;
      }
    }
  }

  /// Opens an image source bottom sheet and uploads the selected document.
  Future<void> _pickAndUploadDocument(String docType) async {
    if (!context.mounted) return;
    final loc = context.loc;

    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(LucideIcons.camera),
              title: Text(loc.profile_selectCamera),
              onTap: () => Navigator.pop(ctx, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(LucideIcons.image),
              title: Text(loc.profile_selectGallery),
              onTap: () => Navigator.pop(ctx, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );

    if (source == null || !context.mounted) return;

    final picker = ImagePicker();
    final pickedFile = await picker.pickImage(
      source: source,
      maxWidth: 1920,
      maxHeight: 1920,
    );

    if (pickedFile == null || !context.mounted) return;

    // Upload the document.
    ref.read(profileUpdatingProvider.notifier).state = true;
    try {
      final client = ref.read(apiClientProvider);
      final formData = FormData.fromMap({
        'document_type': docType,
        'file': MultipartFile.fromFileSync(
          pickedFile.path,
          filename: pickedFile.name,
        ),
      });
      await client.upload('/mobile/driver/documents/upload-profile-doc', formData);
      ref.invalidate(userProfileProvider);

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(loc.profile_uploadSuccess)),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${loc.profile_uploadError}: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        ref.read(profileUpdatingProvider.notifier).state = false;
      }
    }
  }

  /// Shows a confirmation dialog and signs the user out on confirm.
  Future<void> _handleLogout(BuildContext context, WidgetRef ref) async {
    final loc = context.loc;
    final confirmed = await ConfirmationDialog.show(
      context,
      title: loc.auth_logout,
      message: loc.auth_logoutConfirm,
      confirmLabel: loc.auth_logout,
      cancelLabel: loc.general_cancel,
      isDangerous: true,
    );

    if (confirmed == true && context.mounted) {
      await ref.read(authServiceProvider).logout();
      ref.read(authStateProvider.notifier).setUnauthenticated();
    }
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  /// Extracts up to two initials from [name].
  String _initials(String name) {
    if (name.isEmpty) return 'D';
    final parts = name.trim().split(RegExp(r'\s+'));
    if (parts.length >= 2) {
      return '${parts.first[0]}${parts.last[0]}'.toUpperCase();
    }
    return parts.first[0].toUpperCase();
  }

  /// Returns a human-readable role label.
  String _formatRole(String role) {
    switch (role.toLowerCase()) {
      case 'driver':
        return 'Driver';
      case 'dispatcher':
        return 'Dispatcher';
      case 'fleet_manager':
        return 'Fleet Manager';
      case 'admin':
        return 'Administrator';
      default:
        return role;
    }
  }

  /// Returns a colour based on how close [expiryDate] is.
  Color _expiryColor(String expiryDate) {
    final parsed = DateTime.tryParse(expiryDate);
    if (parsed == null) return AppColors.neutralText;

    final now = DateTime.now();
    final diff = parsed.difference(now);

    if (diff.isNegative) return AppColors.error; // expired
    if (diff.inDays < 30) return AppColors.warning; // < 1 month
    return AppColors.success; // > 1 month
  }
}

// ═════════════════════════════════════════════════════════════════════════════
// Private helper widgets
// ═════════════════════════════════════════════════════════════════════════════

/// Section header label used above grouped cards.
class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(
        left: AppSpacing.lg + AppSpacing.xs,
        bottom: AppSpacing.xs,
      ),
      child: Text(
        title.toUpperCase(),
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          letterSpacing: 0.5,
          color: Theme.of(context)
              .colorScheme
              .onSurface
              .withValues(alpha: 0.5),
        ),
      ),
    );
  }
}

/// A single info row with a leading icon, label, and value.
///
/// When [editing] is `true` the value is rendered as an [AppTextField].
class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
    this.editing = false,
    this.controller,
    this.keyboardType,
    this.validator,
    this.valueColor,
  });

  final IconData icon;
  final String label;
  final String value;
  final bool editing;
  final TextEditingController? controller;
  final TextInputType? keyboardType;
  final FormFieldValidator<String>? validator;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Icon(
            icon,
            size: 20,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: editing && controller != null
                ? AppTextField(
                    controller: controller,
                    labelText: label,
                    keyboardType: keyboardType,
                    validator: validator,
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        label,
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface
                              .withValues(alpha: 0.5),
                          fontSize: 11,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        value,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w500,
                          color: valueColor,
                        ),
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}

/// A tappable ListTile-style row used in the Quick Links card.
class _LinkTile extends StatelessWidget {
  const _LinkTile({
    required this.icon,
    required this.title,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
        child: Row(
          children: [
            Icon(
              icon,
              size: 20,
              color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
            ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Text(
                title,
                style: theme.textTheme.bodyMedium?.copyWith(
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            Icon(
              LucideIcons.chevronRight,
              size: 18,
              color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
            ),
          ],
        ),
      ),
    );
  }
}

/// A card representing a single driver document (license, passport, ADR).
///
/// Shows the document icon, type label, expiry date with colour coding, and
/// either a status badge or an upload button.
class _DriverDocumentCard extends StatelessWidget {
  const _DriverDocumentCard({
    required this.icon,
    required this.label,
    this.expiryDate,
    required this.status,
    required this.hasDocument,
    required this.onUpload,
  });

  final IconData icon;
  final String label;
  final String? expiryDate;
  final String status;
  final bool hasDocument;
  final VoidCallback onUpload;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final loc = context.loc;

    final expiryColor = _docExpiryColor(expiryDate);
    final expiryLabel = _formatExpiryDate(expiryDate);

    return SizedBox(
      width: 160,
      child: Card(
        margin: EdgeInsets.zero,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.md),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Icon
              Container(
                height: 40,
                width: 40,
                decoration: BoxDecoration(
                  color: AppColors.accent.withValues(alpha: 0.1),
                  borderRadius: AppRadius.lgAll,
                ),
                child: Icon(icon, color: AppColors.accent, size: 22),
              ),
              const SizedBox(height: AppSpacing.sm),
              // Label
              Text(
                label,
                style: theme.textTheme.bodySmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: AppSpacing.xs),
              // Expiry date
              if (expiryDate != null)
                Row(
                  children: [
                    Icon(
                      LucideIcons.calendar,
                      size: 12,
                      color: expiryColor,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      expiryLabel,
                      style: TextStyle(
                        fontSize: 11,
                        color: expiryColor,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                )
              else
                Text(
                  loc.document_pending,
                  style: TextStyle(
                    fontSize: 11,
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                  ),
                ),
              const Spacer(),
              // Status or Upload button
              if (hasDocument && status == 'uploaded')
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.success.withValues(alpha: 0.12),
                    borderRadius: AppRadius.pillAll,
                  ),
                  child: Text(
                    loc.document_uploaded,
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                      color: AppColors.success,
                    ),
                  ),
                )
              else
                SizedBox(
                  width: double.infinity,
                  height: 32,
                  child: OutlinedButton.icon(
                    onPressed: onUpload,
                    icon: const Icon(LucideIcons.upload, size: 14),
                    label: Text(
                      loc.document_upload,
                      style: const TextStyle(fontSize: 11),
                    ),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(
                        horizontal: AppSpacing.sm,
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Color _docExpiryColor(String? expiryDate) {
    if (expiryDate == null) return AppColors.neutralText;
    final parsed = DateTime.tryParse(expiryDate);
    if (parsed == null) return AppColors.neutralText;
    final diff = parsed.difference(DateTime.now());
    if (diff.isNegative) return AppColors.error;
    if (diff.inDays < 30) return AppColors.warning;
    return AppColors.success;
  }

  String _formatExpiryDate(String? expiryDate) {
    if (expiryDate == null) return '';
    final parsed = DateTime.tryParse(expiryDate);
    if (parsed == null) return expiryDate;
    return '${parsed.day.toString().padLeft(2, '0')}.'
        '${parsed.month.toString().padLeft(2, '0')}.'
        '${parsed.year}';
  }
}

/// Describes one of the three driver document types shown in the horizontal
/// documents section.
class _DriverDocType {
  const _DriverDocType({
    required this.key,
    required this.icon,
    required this.label,
  });

  final String key;
  final IconData icon;
  final String label;
}

// ---------------------------------------------------------------------------
// Shimmer / Empty / other built-in states
// ---------------------------------------------------------------------------

/// Profile-shaped shimmer skeleton used while the profile is loading.
class _ProfileShimmer extends StatelessWidget {
  const _ProfileShimmer();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: [
        // Header shimmer
        const ShimmerLoader(
          child: Column(
            children: [
              CircleAvatar(radius: 40, backgroundColor: Colors.white),
              SizedBox(height: AppSpacing.sm),
              _ShimmerLine(width: 0.4, height: 18),
              SizedBox(height: AppSpacing.xs),
              _ShimmerLine(width: 0.25, height: 13),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.xxl),
        // Section header
        _shimmerBlock(context, 0.3, 14),
        const SizedBox(height: AppSpacing.sm),
        // Card skeleton
        const ShimmerCard(),
        const SizedBox(height: AppSpacing.xl),
        // Section header
        _shimmerBlock(context, 0.3, 14),
        const SizedBox(height: AppSpacing.sm),
        const ShimmerCard(),
        const SizedBox(height: AppSpacing.xl),
        // Section header
        _shimmerBlock(context, 0.3, 14),
        const SizedBox(height: AppSpacing.sm),
        // Horizontal card row skeleton
        SizedBox(
          height: 160,
          child: Row(
            children: List.generate(
              3,
              (_) => const Expanded(
                child: Padding(
                  padding: EdgeInsets.only(right: AppSpacing.sm),
                  child: ShimmerLoader(
                    child: Card(
                      margin: EdgeInsets.zero,
                      child: SizedBox.expand(),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _shimmerBlock(BuildContext context, double width, double height) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: AppSpacing.xs),
      child: ShimmerLoader(
        child: FractionallySizedBox(
          widthFactor: width,
          child: Container(
            height: height,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
          ),
        ),
      ),
    );
  }
}

/// A thin shimmer line used inside skeleton layouts.
class _ShimmerLine extends StatelessWidget {
  const _ShimmerLine({this.width = 1.0, this.height = 12});

  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    return FractionallySizedBox(
      widthFactor: width,
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}

/// Empty state shown when the profile has no user data at all.
class _ProfileEmpty extends StatelessWidget {
  const _ProfileEmpty();

  @override
  Widget build(BuildContext context) {
    return EmptyState(
      icon: const Icon(LucideIcons.userX),
      title: context.loc.general_error,
      subtitle: 'No profile data available.',
    );
  }
}
