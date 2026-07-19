import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:operion_mobile/core/i18n/app_localizations.dart';

void main() {
  // ==========================================================================
  // Supported Locales
  // ==========================================================================
  group('AppLocalizations supported locales', () {
    test('supportedLocales contains ro', () {
      expect(
        AppLocalizations.supportedLocales,
        contains(const Locale('ro')),
      );
    });

    test('supportedLocales contains en', () {
      expect(
        AppLocalizations.supportedLocales,
        contains(const Locale('en')),
      );
    });

    test('supportedLocales has exactly 2 entries', () {
      expect(AppLocalizations.supportedLocales, hasLength(2));
    });
  });

  // ==========================================================================
  // Localizations Delegate
  // ==========================================================================
  group('AppLocalizations delegate', () {
    test('isSupported returns true for ro', () {
      expect(
        AppLocalizations.delegate.isSupported(const Locale('ro')),
        isTrue,
      );
    });

    test('isSupported returns true for en', () {
      expect(
        AppLocalizations.delegate.isSupported(const Locale('en')),
        isTrue,
      );
    });

    test('isSupported returns false for de', () {
      expect(
        AppLocalizations.delegate.isSupported(const Locale('de')),
        isFalse,
      );
    });

    test('isSupported returns false for fr', () {
      expect(
        AppLocalizations.delegate.isSupported(const Locale('fr')),
        isFalse,
      );
    });

    test('isSupported matches by language code (not country)', () {
      expect(
        AppLocalizations.delegate.isSupported(const Locale('en', 'US')),
        isTrue,
      );
      expect(
        AppLocalizations.delegate.isSupported(const Locale('ro', 'RO')),
        isTrue,
      );
    });

    test('load returns AppLocalizations instance', () async {
      final loc = await AppLocalizations.delegate.load(const Locale('en'));
      expect(loc, isA<AppLocalizations>());
    });

    test('shouldReload returns false', () {
      expect(
        AppLocalizations.delegate.shouldReload(
          AppLocalizations.delegate,
        ),
        isFalse,
      );
    });
  });

  // ==========================================================================
  // AppLocalizations.of(context)
  // ==========================================================================
  group('AppLocalizations.of(context)', () {
    testWidgets('returns non-null for English locale', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: [
            AppLocalizations.delegate,
            ...GlobalMaterialLocalizations.delegates,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          locale: const Locale('en'),
          home: Builder(
            builder: (context) {
              final loc = AppLocalizations.of(context);
              return Text(loc.appName);
            },
          ),
        ),
      );
      await tester.pump();
      expect(find.text('Operion'), findsOneWidget);
    });

    testWidgets('returns non-null for Romanian locale', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: [
            AppLocalizations.delegate,
            ...GlobalMaterialLocalizations.delegates,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          locale: const Locale('ro'),
          home: Builder(
            builder: (context) {
              final loc = AppLocalizations.of(context);
              return Text(loc.appName);
            },
          ),
        ),
      );
      await tester.pump();
      expect(find.text('Operion'), findsOneWidget);
    });
  });

  // ==========================================================================
  // Localized Strings - English
  // ==========================================================================
  group('English localized strings', () {
    late AppLocalizations en;

    setUp(() {
      en = AppLocalizations(const Locale('en'));
    });

    test('appName returns "Operion"', () {
      expect(en.appName, 'Operion');
    });

    test('auth_login returns "Sign In"', () {
      expect(en.auth_login, 'Sign In');
    });

    test('auth_email returns "Email"', () {
      expect(en.auth_email, 'Email');
    });

    test('auth_password returns "Password"', () {
      expect(en.auth_password, 'Password');
    });

    test('auth_loginButton returns "Sign In"', () {
      expect(en.auth_loginButton, 'Sign In');
    });

    test('auth_forgotPassword returns "Forgot password?"', () {
      expect(en.auth_forgotPassword, 'Forgot password?');
    });

    test('nav_home returns "Home"', () {
      expect(en.nav_home, 'Home');
    });

    test('nav_transports returns "Transports"', () {
      expect(en.nav_transports, 'Transports');
    });

    test('transport_status_delivered returns "Delivered"', () {
      expect(en.transport_status_delivered, 'Delivered');
    });

    test('general_cancel returns "Cancel"', () {
      expect(en.general_cancel, 'Cancel');
    });

    test('general_confirm returns "Confirm"', () {
      expect(en.general_confirm, 'Confirm');
    });

    test('general_loading returns "Loading..."', () {
      expect(en.general_loading, 'Loading...');
    });

    test('message_send returns "Send"', () {
      expect(en.message_send, 'Send');
    });

    test('all English getters return non-null strings', () {
      // Representative sample across all sections
      expect(en.appTagline, isNotNull);
      expect(en.auth_biometricTitle, isNotNull);
      expect(en.auth_biometricHint, isNotNull);
      expect(en.auth_sessionExpired, isNotNull);
      expect(en.auth_loggedOut, isNotNull);
      expect(en.auth_logout, isNotNull);
      expect(en.auth_logoutConfirm, isNotNull);
      expect(en.nav_documents, isNotNull);
      expect(en.nav_messages, isNotNull);
      expect(en.nav_notifications, isNotNull);
      expect(en.nav_profile, isNotNull);
      expect(en.nav_settings, isNotNull);
      expect(en.nav_jobs, isNotNull);
      expect(en.nav_fleet, isNotNull);
      expect(en.nav_drivers, isNotNull);
      expect(en.nav_alerts, isNotNull);
      expect(en.nav_analytics, isNotNull);
      expect(en.driver_myDay, isNotNull);
      expect(en.driver_assignedTransports, isNotNull);
      expect(en.driver_noTransports, isNotNull);
      expect(en.driver_vehicleInfo, isNotNull);
      expect(en.driver_expenses, isNotNull);
      expect(en.driver_documents, isNotNull);
      expect(en.transport_status_loading, isNotNull);
      expect(en.transport_status_in_progress, isNotNull);
      expect(en.transport_status_in_transit, isNotNull);
      expect(en.transport_status_cancelled, isNotNull);
      expect(en.transport_status_overdue, isNotNull);
      expect(en.transport_status_invoiced, isNotNull);
      expect(en.transport_status_paid, isNotNull);
      expect(en.transport_status_maintenance, isNotNull);
      expect(en.transport_updateStatus, isNotNull);
      expect(en.document_upload, isNotNull);
      expect(en.document_capture, isNotNull);
      expect(en.document_selectGallery, isNotNull);
      expect(en.expense_fuel, isNotNull);
      expect(en.expense_tolls, isNotNull);
      expect(en.expense_perDiem, isNotNull);
      expect(en.expense_amount, isNotNull);
      expect(en.message_noMessages, isNotNull);
      expect(en.message_typeMessage, isNotNull);
      expect(en.notification_newAssignment, isNotNull);
      expect(en.dispatcher_overview, isNotNull);
      expect(en.dispatcher_reassignConfirm, isNotNull);
      expect(en.analytics_profit, isNotNull);
      expect(en.analytics_revenue, isNotNull);
      expect(en.ocr_results, isNotNull);
      expect(en.ocr_processing, isNotNull);
      expect(en.settings_language, isNotNull);
      expect(en.settings_theme, isNotNull);
      expect(en.profile_personalInfo, isNotNull);
      expect(en.profile_driverInfo, isNotNull);
      expect(en.general_save, isNotNull);
      expect(en.general_delete, isNotNull);
      expect(en.general_edit, isNotNull);
      expect(en.general_retry, isNotNull);
      expect(en.general_error, isNotNull);
      expect(en.general_noInternet, isNotNull);
      expect(en.general_offline, isNotNull);
      expect(en.general_lastUpdated, isNotNull);
      expect(en.general_justNow, isNotNull);
      expect(en.general_pendingSync, isNotNull);
      expect(en.general_yes, isNotNull);
      expect(en.general_no, isNotNull);
      expect(en.alert_delay, isNotNull);
      expect(en.alert_maintenance, isNotNull);
      expect(en.alert_documentExpiry, isNotNull);
      expect(en.alert_compliance, isNotNull);
      expect(en.alert_noAlerts, isNotNull);
      expect(en.settings_appVersion, isNotNull);
    });
  });

  // ==========================================================================
  // Localized Strings - Romanian
  // ==========================================================================
  group('Romanian localized strings', () {
    late AppLocalizations ro;

    setUp(() {
      ro = AppLocalizations(const Locale('ro'));
    });

    test('appName returns "Operion"', () {
      expect(ro.appName, 'Operion');
    });

    test('auth_login returns "Autentificare"', () {
      expect(ro.auth_login, 'Autentificare');
    });

    test('auth_email returns "Email"', () {
      expect(ro.auth_email, 'Email');
    });

    test('auth_password returns "Parolă"', () {
      expect(ro.auth_password, 'Parolă');
    });

    test('auth_loginButton returns "Conectare"', () {
      expect(ro.auth_loginButton, 'Conectare');
    });

    test('nav_home returns "Acasă"', () {
      expect(ro.nav_home, 'Acasă');
    });

    test('transport_status_delivered returns "Livrat"', () {
      expect(ro.transport_status_delivered, 'Livrat');
    });

    test('transport_status_in_progress returns "În curs"', () {
      expect(ro.transport_status_in_progress, 'În curs');
    });

    test('general_cancel returns "Anulează"', () {
      expect(ro.general_cancel, 'Anulează');
    });

    test('general_confirm returns "Confirmă"', () {
      expect(ro.general_confirm, 'Confirmă');
    });

    test('all Romanian getters return non-null strings', () {
      // Romanian should have the same keys as English
      expect(ro.appTagline, isNotNull);
      expect(ro.auth_biometricTitle, isNotNull);
      expect(ro.auth_loggingIn, isNotNull);
      expect(ro.auth_loginError, isNotNull);
      expect(ro.nav_documents, isNotNull);
      expect(ro.nav_messages, isNotNull);
      expect(ro.driver_myDay, isNotNull);
      expect(ro.driver_assignedTransports, isNotNull);
      expect(ro.driver_noTransports, isNotNull);
      expect(ro.transport_status_planned, isNotNull);
      expect(ro.transport_status_loading, isNotNull);
      expect(ro.transport_status_in_transit, isNotNull);
      expect(ro.transport_status_cancelled, isNotNull);
      expect(ro.transport_status_overdue, isNotNull);
      expect(ro.document_upload, isNotNull);
      expect(ro.document_cmr, isNotNull);
      expect(ro.document_pod, isNotNull);
      expect(ro.document_invoice, isNotNull);
      expect(ro.document_uploading, isNotNull);
      expect(ro.expense_new, isNotNull);
      expect(ro.expense_type, isNotNull);
      expect(ro.expense_fuel, isNotNull);
      expect(ro.expense_tolls, isNotNull);
      expect(ro.expense_perDiem, isNotNull);
      expect(ro.expense_other, isNotNull);
      expect(ro.expense_submit, isNotNull);
      expect(ro.message_sending, isNotNull);
      expect(ro.message_sent, isNotNull);
      expect(ro.notification_scheduleChange, isNotNull);
      expect(ro.notification_newMessage, isNotNull);
      expect(ro.dispatcher_activeJobs, isNotNull);
      expect(ro.dispatcher_approve, isNotNull);
      expect(ro.dispatcher_reject, isNotNull);
      expect(ro.dispatcher_reassign, isNotNull);
      expect(ro.general_created, isNotNull);
      expect(ro.analytics_costs, isNotNull);
      expect(ro.analytics_openDesktop, isNotNull);
      expect(ro.analytics_thisMonth, isNotNull);
      expect(ro.analytics_trucksActive, isNotNull);
      expect(ro.ocr_confidence, isNotNull);
      expect(ro.settings_languageRo, isNotNull);
      expect(ro.settings_languageEn, isNotNull);
      expect(ro.settings_themeLight, isNotNull);
      expect(ro.settings_themeDark, isNotNull);
      expect(ro.settings_themeSystem, isNotNull);
    });
  });

  // ==========================================================================
  // Extension: context.loc
  // ==========================================================================
  group('context.loc extension', () {
    testWidgets('context.loc returns AppLocalizations', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: [
            AppLocalizations.delegate,
            ...GlobalMaterialLocalizations.delegates,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          locale: const Locale('en'),
          home: Builder(
            builder: (context) {
              final loc = context.loc;
              return Text(loc.auth_login);
            },
          ),
        ),
      );
      await tester.pump();
      expect(find.text('Sign In'), findsOneWidget);
    });

    testWidgets('context.loc works with Romanian locale', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          localizationsDelegates: [
            AppLocalizations.delegate,
            ...GlobalMaterialLocalizations.delegates,
          ],
          supportedLocales: AppLocalizations.supportedLocales,
          locale: const Locale('ro'),
          home: Builder(
            builder: (context) {
              final loc = context.loc;
              return Text(loc.auth_login);
            },
          ),
        ),
      );
      await tester.pump();
      expect(find.text('Autentificare'), findsOneWidget);
    });
  });
}
