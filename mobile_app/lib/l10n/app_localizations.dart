import 'dart:ui';

import 'package:flutter/widgets.dart';

// ignore_for_file: non_constant_identifier_names

/// Manually-maintained localization class for Operion Mobile.
///
/// Supports Romanian (ro) and English (en).
class AppLocalizations {
  final Locale locale;

  AppLocalizations(this.locale);

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  static const List<Locale> supportedLocales = [
    Locale('ro'),
    Locale('en'),
  ];

  String _get(String key) {
    final strings = _localizedStrings[locale.languageCode] ?? _localizedStrings['en']!;
    return strings[key] ?? key;
  }

  String get appName => _get('appName');
  String get appTagline => _get('appTagline');
  String get auth_login => _get('auth_login');
  String get auth_email => _get('auth_email');
  String get auth_password => _get('auth_password');
  String get auth_loginButton => _get('auth_loginButton');
  String get auth_loggingIn => _get('auth_loggingIn');
  String get auth_loginError => _get('auth_loginError');
  String get auth_biometricTitle => _get('auth_biometricTitle');
  String get auth_biometricHint => _get('auth_biometricHint');
  String get auth_sessionExpired => _get('auth_sessionExpired');
  String get auth_loggedOut => _get('auth_loggedOut');
  String get auth_logout => _get('auth_logout');
  String get auth_logoutConfirm => _get('auth_logoutConfirm');
  String get auth_forgotPassword => _get('auth_forgotPassword');
  String get nav_home => _get('nav_home');
  String get nav_transports => _get('nav_transports');
  String get nav_documents => _get('nav_documents');
  String get nav_messages => _get('nav_messages');
  String get nav_notifications => _get('nav_notifications');
  String get nav_profile => _get('nav_profile');
  String get nav_settings => _get('nav_settings');
  String get nav_jobs => _get('nav_jobs');
  String get nav_fleet => _get('nav_fleet');
  String get nav_drivers => _get('nav_drivers');
  String get nav_alerts => _get('nav_alerts');
  String get nav_analytics => _get('nav_analytics');
  String get nav_map => _get('nav_map');
  String get nav_overview => _get('nav_overview');
  String get nav_copilot => _get('nav_copilot');
  String get nav_fleetTracker => _get('nav_fleetTracker');
  String get nav_more => _get('nav_more');
  String get nav_teams => _get('nav_teams');
  String get nav_profitCalculator => _get('nav_profitCalculator');
  String get nav_routePlanner => _get('nav_routePlanner');
  String get nav_freightExchange => _get('nav_freightExchange');
  String get nav_documentCenter => _get('nav_documentCenter');
  String get nav_localDownload => _get('nav_localDownload');

  // ── Route Planner ─────────────────────────────────────────────
  String get routePlanner_origin => _get('routePlanner_origin');
  String get routePlanner_originHint => _get('routePlanner_originHint');
  String get routePlanner_destination => _get('routePlanner_destination');
  String get routePlanner_destinationHint => _get('routePlanner_destinationHint');
  String get routePlanner_stops => _get('routePlanner_stops');
  String get routePlanner_addStop => _get('routePlanner_addStop');
  String get routePlanner_noStops => _get('routePlanner_noStops');
  String get routePlanner_noStopsHint => _get('routePlanner_noStopsHint');
  String get routePlanner_optimize => _get('routePlanner_optimize');
  String get routePlanner_stopNumber => _get('routePlanner_stopNumber');

  // ── Freight Exchange ──────────────────────────────────────────
  String get freightExchange_searchHint => _get('freightExchange_searchHint');
  String get freightExchange_empty => _get('freightExchange_empty');
  String get freightExchange_emptyHint => _get('freightExchange_emptyHint');

  String get driver_myDay => _get('driver_myDay');
  String get driver_assignedTransports => _get('driver_assignedTransports');
  String get driver_noTransports => _get('driver_noTransports');
  String get driver_vehicleInfo => _get('driver_vehicleInfo');
  String get driver_expenses => _get('driver_expenses');
  String get driver_documents => _get('driver_documents');
  String get transport_status_planned => _get('transport_status_planned');
  String get transport_status_loading => _get('transport_status_loading');
  String get transport_status_in_progress => _get('transport_status_in_progress');
  String get transport_status_in_transit => _get('transport_status_in_transit');
  String get transport_status_delivered => _get('transport_status_delivered');
  String get transport_status_cancelled => _get('transport_status_cancelled');
  String get transport_status_overdue => _get('transport_status_overdue');
  String get transport_status_invoiced => _get('transport_status_invoiced');
  String get transport_status_paid => _get('transport_status_paid');
  String get transport_status_maintenance => _get('transport_status_maintenance');
  String get transport_updateStatus => _get('transport_updateStatus');
  String get transport_navigate => _get('transport_navigate');
  String get transport_route => _get('transport_route');
  String get transport_details => _get('transport_details');
  String get document_upload => _get('document_upload');
  String get document_capture => _get('document_capture');
  String get document_selectGallery => _get('document_selectGallery');
  String get document_cmr => _get('document_cmr');
  String get document_pod => _get('document_pod');
  String get document_invoice => _get('document_invoice');
  String get document_other => _get('document_other');
  String get document_uploading => _get('document_uploading');
  String get document_uploaded => _get('document_uploaded');
  String get document_pending => _get('document_pending');
  String get document_failed => _get('document_failed');
  String get document_noDocuments => _get('document_noDocuments');
  String get expense_new => _get('expense_new');
  String get expense_type => _get('expense_type');
  String get expense_fuel => _get('expense_fuel');
  String get expense_tolls => _get('expense_tolls');
  String get expense_perDiem => _get('expense_perDiem');
  String get expense_other => _get('expense_other');
  String get expense_amount => _get('expense_amount');
  String get expense_date => _get('expense_date');
  String get expense_receipt => _get('expense_receipt');
  String get expense_submit => _get('expense_submit');
  String get vehicle_assigned => _get('vehicle_assigned');
  String get vehicle_plate => _get('vehicle_plate');
  String get vehicle_type => _get('vehicle_type');
  String get vehicle_documents => _get('vehicle_documents');
  String get vehicle_expiry => _get('vehicle_expiry');
  String get message_noMessages => _get('message_noMessages');
  String get message_typeMessage => _get('message_typeMessage');
  String get message_send => _get('message_send');
  String get message_sending => _get('message_sending');
  String get message_sent => _get('message_sent');
  String get message_you => _get('message_you');
  String get notification_newAssignment => _get('notification_newAssignment');
  String get notification_scheduleChange => _get('notification_scheduleChange');
  String get notification_newMessage => _get('notification_newMessage');
  String get notification_alert => _get('notification_alert');
  String get dispatcher_overview => _get('dispatcher_overview');
  String get dispatcher_activeJobs => _get('dispatcher_activeJobs');
  String get dispatcher_activeDrivers => _get('dispatcher_activeDrivers');
  String get dispatcher_openAlerts => _get('dispatcher_openAlerts');
  String get dispatcher_liveFleet => _get('dispatcher_liveFleet');
  String get dispatcher_approve => _get('dispatcher_approve');
  String get dispatcher_reject => _get('dispatcher_reject');
  String get dispatcher_reassign => _get('dispatcher_reassign');
  String get dispatcher_quickActions => _get('dispatcher_quickActions');
  String get dispatcher_jobDetails => _get('dispatcher_jobDetails');
  String get dispatcher_markDelivered => _get('dispatcher_markDelivered');
  String get dispatcher_messageDriver => _get('dispatcher_messageDriver');
  String get dispatcher_reassignConfirm => _get('dispatcher_reassignConfirm');
  String get dispatcher_reassignSuccess => _get('dispatcher_reassignSuccess');
  String get dispatcher_noJobs => _get('dispatcher_noJobs');
  String get dispatcher_all => _get('dispatcher_all');
  String get dispatcher_driver => _get('dispatcher_driver');
  String get general_created => _get('general_created');
  String get alert_delay => _get('alert_delay');
  String get alert_maintenance => _get('alert_maintenance');
  String get alert_documentExpiry => _get('alert_documentExpiry');
  String get alert_compliance => _get('alert_compliance');
  String get alert_noAlerts => _get('alert_noAlerts');
  String get analytics_profit => _get('analytics_profit');
  String get analytics_revenue => _get('analytics_revenue');
  String get analytics_costs => _get('analytics_costs');
  String get analytics_openDesktop => _get('analytics_openDesktop');
  String get analytics_financialSummary => _get('analytics_financialSummary');
  String get analytics_fleetUtilization => _get('analytics_fleetUtilization');
  String get analytics_topClients => _get('analytics_topClients');
  String get analytics_driverPerformance => _get('analytics_driverPerformance');
  String get analytics_thisMonth => _get('analytics_thisMonth');
  String get analytics_lastMonth => _get('analytics_lastMonth');
  String get analytics_trucksActive => _get('analytics_trucksActive');
  String get analytics_noData => _get('analytics_noData');
  String get ocr_results => _get('ocr_results');
  String get ocr_processing => _get('ocr_processing');
  String get ocr_confidence => _get('ocr_confidence');
  String get general_cancel => _get('general_cancel');
  String get general_confirm => _get('general_confirm');
  String get general_save => _get('general_save');
  String get general_delete => _get('general_delete');
  String get general_edit => _get('general_edit');
  String get general_retry => _get('general_retry');
  String get general_loading => _get('general_loading');
  String get general_error => _get('general_error');
  String get general_noInternet => _get('general_noInternet');
  String get general_offline => _get('general_offline');
  String get general_lastUpdated => _get('general_lastUpdated');
  String get general_minAgo => _get('general_minAgo');
  String get general_justNow => _get('general_justNow');
  String get general_hourAgo => _get('general_hourAgo');
  String get general_hoursAgo => _get('general_hoursAgo');
  String get general_pendingSync => _get('general_pendingSync');
  String get general_comingSoon => _get('general_comingSoon');
  String get general_comingSoonDescription => _get('general_comingSoonDescription');
  String get general_openDesktop => _get('general_openDesktop');
  String get general_yes => _get('general_yes');
  String get general_no => _get('general_no');
  String get settings_language => _get('settings_language');
  String get settings_languageRo => _get('settings_languageRo');
  String get settings_languageEn => _get('settings_languageEn');
  String get settings_theme => _get('settings_theme');
  String get settings_themeSystem => _get('settings_themeSystem');
  String get settings_themeLight => _get('settings_themeLight');
  String get settings_themeDark => _get('settings_themeDark');
  String get settings_appVersion => _get('settings_appVersion');

  // ── AI Co-Pilot ─────────────────────────────────────────────────
  String get ai_title => _get('ai_title');
  String get ai_emptyStateMessage => _get('ai_emptyStateMessage');
  String get ai_emptyStatePrompt => _get('ai_emptyStatePrompt');
  String get ai_clarifyPlaceholder => _get('ai_clarifyPlaceholder');
  String get ai_newConversation => _get('ai_newConversation');
  String get ai_placeholder => _get('ai_placeholder');
  String get ai_confirmTitle => _get('ai_confirmTitle');
  String get ai_confirmMessage => _get('ai_confirmMessage');
  String get copilot_level3_title => _get('copilot_level3_title');
  String get copilot_level3_warning => _get('copilot_level3_warning');
  String get copilot_level3_hint => _get('copilot_level3_hint');
  String copilot_level3_phrase(String phrase) =>
      _get('copilot_level3_phrase').replaceAll('{phrase}', phrase);

  // ── Profile screen ──────────────────────────────────────────────
  String get profile_personalInfo => _get('profile_personalInfo');
  String get profile_driverInfo => _get('profile_driverInfo');
  String get profile_quickLinks => _get('profile_quickLinks');
  String get profile_licenseNumber => _get('profile_licenseNumber');
  String get profile_licenseCategory => _get('profile_licenseCategory');
  String get profile_licenseExpiry => _get('profile_licenseExpiry');
  String get profile_phone => _get('profile_phone');
  String get profile_displayName => _get('profile_displayName');
  String get profile_noDriverInfo => _get('profile_noDriverInfo');
  String get profile_documentLicense => _get('profile_documentLicense');
  String get profile_documentPassport => _get('profile_documentPassport');
  String get profile_documentAdr => _get('profile_documentAdr');
  String get profile_selectCamera => _get('profile_selectCamera');
  String get profile_selectGallery => _get('profile_selectGallery');
  String get profile_noDocuments => _get('profile_noDocuments');
  String get profile_uploadSuccess => _get('profile_uploadSuccess');
  String get profile_uploadError => _get('profile_uploadError');

  // ── Driver Overview ──────────────────────────────────────────
  String get driverOverview_emptyState => _get('driverOverview_emptyState');
  String get driverOverview_emptyStateSubtitle => _get('driverOverview_emptyStateSubtitle');
  String get driverOverview_etaUnavailable => _get('driverOverview_etaUnavailable');

  // ── Transport ────────────────────────────────────────────────
  String get transport_statusUpdated => _get('transport_statusUpdated');
  String get transport_eta => _get('transport_eta');
  String get transport_elapsedTime => _get('transport_elapsedTime');

  // ── Route Share ──────────────────────────────────────────────
  String get routeShare_noData => _get('routeShare_noData');
  String get routeShare_noDataSubtitle => _get('routeShare_noDataSubtitle');
  String get routeShare_distance => _get('routeShare_distance');
  String get routeShare_estimatedTime => _get('routeShare_estimatedTime');

  // ── Transport Actions ────────────────────────────────────────
  String get transport_action_startLoading => _get('transport_action_startLoading');
  String get transport_action_depart => _get('transport_action_depart');
  String get transport_action_markDelivered => _get('transport_action_markDelivered');
  String get transport_action_reportDelay => _get('transport_action_reportDelay');
  String get transport_action_noActions => _get('transport_action_noActions');

  // ── Document Center ──────────────────────────────────────────
  String get documentCenter_title => _get('documentCenter_title');
  String get documentCenter_documents => _get('documentCenter_documents');
  String get documentCenter_automation => _get('documentCenter_automation');
  String get documentCenter_ocrTitle => _get('documentCenter_ocrTitle');
  String get documentCenter_ocrDescription => _get('documentCenter_ocrDescription');
  String get documentCenter_capturePhoto => _get('documentCenter_capturePhoto');
  String get documentCenter_uploadConfirmed => _get('documentCenter_uploadConfirmed');

  // ── Local Download ───────────────────────────────────────────
  String get localDownload_title => _get('localDownload_title');
  String get localDownload_selectCategory => _get('localDownload_selectCategory');
  String get localDownload_download => _get('localDownload_download');
  String get localDownload_categoryDocuments => _get('localDownload_categoryDocuments');
  String get localDownload_categoryInvoices => _get('localDownload_categoryInvoices');
  String get localDownload_categoryReceipts => _get('localDownload_categoryReceipts');
  String get localDownload_categoryOcrResults => _get('localDownload_categoryOcrResults');
  String get localDownload_categoryTripHistory => _get('localDownload_categoryTripHistory');
  String get localDownload_dateFrom => _get('localDownload_dateFrom');
  String get localDownload_dateTo => _get('localDownload_dateTo');
  String get localDownload_progress => _get('localDownload_progress');
  String get localDownload_complete => _get('localDownload_complete');

  // ── Profit Calculator ────────────────────────────────────────
  String get profitCalculator_title => _get('profitCalculator_title');
  String get profitCalculator_revenue => _get('profitCalculator_revenue');
  String get profitCalculator_fuelCost => _get('profitCalculator_fuelCost');
  String get profitCalculator_tollCost => _get('profitCalculator_tollCost');
  String get profitCalculator_maintenance => _get('profitCalculator_maintenance');
  String get profitCalculator_driverCost => _get('profitCalculator_driverCost');
  String get profitCalculator_calculate => _get('profitCalculator_calculate');
  String get profitCalculator_totalCosts => _get('profitCalculator_totalCosts');
  String get profitCalculator_profit => _get('profitCalculator_profit');
  String get profitCalculator_profitMargin => _get('profitCalculator_profitMargin');
  String get profitCalculator_currencySymbol => _get('profitCalculator_currencySymbol');

  // ── Teams ────────────────────────────────────────────────────
  String get teams_filterAll => _get('teams_filterAll');
  String get teams_filterAvailable => _get('teams_filterAvailable');
  String get teams_filterDriving => _get('teams_filterDriving');
  String get teams_filterOff => _get('teams_filterOff');
  String get teams_placeholder => _get('teams_placeholder');

  static const Map<String, Map<String, String>> _localizedStrings = {
    'ro': {
      'appName': 'Operion', 'appTagline': 'ERP Logistic',
      'auth_login': 'Autentificare', 'auth_email': 'Email', 'auth_password': 'Parolă',
      'auth_loginButton': 'Conectare', 'auth_loggingIn': 'Se conectează...',
      'auth_loginError': 'Email sau parolă incorectă',
      'auth_biometricTitle': 'Deblochează cu date biometrice',
      'auth_biometricHint': 'Autentifică-te folosind amprenta sau recunoașterea facială',
      'auth_sessionExpired': 'Sesiunea a expirat.', 'auth_loggedOut': 'Ai fost deconectat.',
      'auth_logout': 'Deconectare', 'auth_logoutConfirm': 'Ești sigur că vrei să te deconectezi?',
      'auth_forgotPassword': 'Ai uitat parola?',
      'nav_home': 'Acasă', 'nav_transports': 'Transporturi', 'nav_documents': 'Documente',
      'nav_messages': 'Mesaje', 'nav_notifications': 'Notificări', 'nav_profile': 'Profil',
      'nav_settings': 'Setări', 'nav_jobs': 'Comenzi', 'nav_fleet': 'Flotă',
      'nav_drivers': 'Șoferi',       'nav_alerts': 'Alerte', 'nav_analytics': 'Analize',
      'nav_map': 'Hartă', 'nav_overview': 'Prezentare generală',
      'nav_fleetTracker': 'Flotă', 'nav_copilot': 'AI Co-Pilot', 'nav_more': 'Mai mult',
      'nav_teams': 'Echipe', 'nav_profitCalculator': 'Calculator Profit',
      'nav_routePlanner': 'Planificator Rută', 'nav_freightExchange': 'Schimb Marfă',
      'nav_documentCenter': 'Centru Documente', 'nav_localDownload': 'Descărcare Locală',
      'routePlanner_origin': 'Origine', 'routePlanner_originHint': 'Introdu adresa de origine',
      'routePlanner_destination': 'Destinație', 'routePlanner_destinationHint': 'Introdu adresa destinație',
      'routePlanner_stops': 'Opriri', 'routePlanner_addStop': 'Adaugă oprire',
      'routePlanner_noStops': 'Nicio oprire adăugată',
      'routePlanner_noStopsHint': 'Adaugă opriri intermediare pentru a-ți optimiza ruta.',
      'routePlanner_optimize': 'Optimizează ruta', 'routePlanner_stopNumber': 'Oprirea',
      'freightExchange_searchHint': 'Caută după origine, destinație...',
      'freightExchange_empty': 'Schimb mărfuri',
      'freightExchange_emptyHint': 'Datele bursei de mărfuri vor apărea aici când backend-ul este conectat.',
      'driver_myDay': 'Ziua mea', 'driver_assignedTransports': 'Transporturi asignate',
      'driver_noTransports': 'Nu ai transporturi asignate', 'driver_vehicleInfo': 'Informații vehicul',
      'driver_expenses': 'Cheltuieli', 'driver_documents': 'Documentele mele',
      'transport_status_planned': 'Planificat', 'transport_status_loading': 'Se încarcă',
      'transport_status_in_progress': 'În curs', 'transport_status_in_transit': 'În tranzit',
      'transport_status_delivered': 'Livrat', 'transport_status_cancelled': 'Anulat',
      'transport_status_overdue': 'Restant', 'transport_status_invoiced': 'Facturat',
      'transport_status_paid': 'Plătit', 'transport_status_maintenance': 'Mentenanță',
      'transport_updateStatus': 'Actualizează status', 'transport_navigate': 'Navighează',
      'transport_route': 'Rută', 'transport_details': 'Detalii transport',
      'document_upload': 'Încarcă document', 'document_capture': 'Fotografiază',
      'document_selectGallery': 'Alege din galerie', 'document_cmr': 'CMR', 'document_pod': 'POD',
      'document_invoice': 'Factură', 'document_other': 'Alt document',
      'document_uploading': 'Se încarcă...', 'document_uploaded': 'Încărcat',
      'document_pending': 'În așteptare', 'document_failed': 'Eroare la încărcare',
      'document_noDocuments': 'Niciun document',
      'expense_new': 'Cheltuială nouă', 'expense_type': 'Tip', 'expense_fuel': 'Carburant',
      'expense_tolls': 'Taxe drum', 'expense_perDiem': 'Diurnă', 'expense_other': 'Altele',
      'expense_amount': 'Sumă', 'expense_date': 'Data', 'expense_receipt': 'Bon fiscal',
      'expense_submit': 'Trimite',
      'vehicle_assigned': 'Vehicul asignat', 'vehicle_plate': 'Număr', 'vehicle_type': 'Tip',
      'vehicle_documents': 'Documente vehicul', 'vehicle_expiry': 'Expiră',
      'message_noMessages': 'Niciun mesaj', 'message_typeMessage': 'Scrie un mesaj...',
      'message_send': 'Trimite', 'message_sending': 'Se trimite...', 'message_sent': 'Trimis',
      'message_you': 'Tu',
      'notification_newAssignment': 'Transport nou asignat', 'notification_scheduleChange': 'Program modificat',
      'notification_newMessage': 'Mesaj nou', 'notification_alert': 'Alertă',
      'dispatcher_overview': 'Prezentare generală', 'dispatcher_activeJobs': 'Comenzi active',
      'dispatcher_activeDrivers': 'Șoferi activi', 'dispatcher_openAlerts': 'Alerte deschise',
      'dispatcher_liveFleet': 'Flotă live', 'dispatcher_approve': 'Aprobă',
      'dispatcher_reject': 'Respinge', 'dispatcher_reassign': 'Reasignare',
      'dispatcher_quickActions': 'Acțiuni rapide',
      'dispatcher_jobDetails': 'Detalii comandă',
      'dispatcher_markDelivered': 'Marchează livrat',
      'dispatcher_messageDriver': 'Trimite mesaj șoferului',
      'dispatcher_reassignConfirm': 'Reasignează la {driver}?',
      'dispatcher_reassignSuccess': 'Transport reasignat cu succes',
      'dispatcher_noJobs': 'Nicio comandă găsită',
      'dispatcher_all': 'Toate',
      'dispatcher_driver': 'Șofer',
      'general_created': 'Creată',
      'alert_delay': 'Întârziere', 'alert_maintenance': 'Mentenanță',
      'alert_documentExpiry': 'Document expirat', 'alert_compliance': 'Conformitate',
      'alert_noAlerts': 'Nicio alertă',
      'analytics_profit': 'Profit', 'analytics_revenue': 'Venituri', 'analytics_costs': 'Costuri',
      'analytics_openDesktop': 'Deschide pe desktop pentru analize complete',
      'analytics_financialSummary': 'Rezumat financiar',
      'analytics_fleetUtilization': 'Utilizare flotă',
      'analytics_topClients': 'Clienți de top',
      'analytics_driverPerformance': 'Performanță șoferi',
      'analytics_thisMonth': 'Luna aceasta',
      'analytics_lastMonth': 'Luna trecută',
      'analytics_trucksActive': '{active}/{total} camioane active',
      'analytics_noData': 'Nicio dată pentru această perioadă',
      'ocr_results': 'Rezultate OCR',
      'ocr_processing': 'Procesare OCR în fundal. Rezultatele vor apărea mai târziu.',
      'ocr_confidence': '{percent}% încredere',
      'general_cancel': 'Anulează', 'general_confirm': 'Confirmă', 'general_save': 'Salvează',
      'general_delete': 'Șterge', 'general_edit': 'Editează', 'general_retry': 'Reîncearcă',
      'general_loading': 'Se încarcă...', 'general_error': 'A apărut o eroare',
      'general_noInternet': 'Fără conexiune la internet', 'general_offline': 'Ești offline',
      'general_lastUpdated': 'Ultima actualizare', 'general_minAgo': 'acum {count} min',
      'general_justNow': 'chiar acum', 'general_hourAgo': 'acum o oră',
      'general_hoursAgo': 'acum {count} ore', 'general_pendingSync': 'Se așteaptă sincronizarea',
      'general_comingSoon': 'În curând',
      'general_comingSoonDescription': 'Această funcție va fi disponibilă într-o actualizare viitoare',
      'general_openDesktop': 'Deschide pe desktop', 'general_yes': 'Da', 'general_no': 'Nu',
      'settings_language': 'Limbă', 'settings_languageRo': 'Română', 'settings_languageEn': 'English',
      'settings_theme': 'Temă', 'settings_themeSystem': 'Sistem', 'settings_themeLight': 'Luminos',
      'settings_themeDark': 'Întunecat',       'settings_appVersion': 'Versiune aplicație',
      'ai_title': 'AI Co-Pilot', 'ai_emptyStateMessage': 'Întreabă-mă orice despre flota ta',
      'ai_emptyStatePrompt': 'Încearcă: "Arată camioanele disponibile"',
      'ai_clarifyPlaceholder': 'Scrie răspunsul...', 'ai_newConversation': 'Conversație nouă',
      'ai_placeholder': 'Scrie o comandă sau întrebare...',
      'ai_confirmTitle': 'Confirmă acțiunea',
      'ai_confirmMessage': 'Operion AI propune următoarea acțiune:',
      'copilot_level3_title': 'Nivelul 3 — Tastează confirmarea pentru a continua',
      'copilot_level3_warning': 'Această acțiune este IREVERSIBILĂ. Tastează fraza de confirmare pentru a continua.',
      'copilot_level3_hint': 'Tastează fraza de confirmare...',
      'copilot_level3_phrase': 'Tastează: "{phrase}"',
      'profile_personalInfo': 'Informații personale',
      'profile_driverInfo': 'Informații șofer',
      'profile_quickLinks': 'Linkuri rapide',
      'profile_licenseNumber': 'Număr permis',
      'profile_licenseCategory': 'Categorie permis',
      'profile_licenseExpiry': 'Expirare permis',
      'profile_phone': 'Telefon',
      'profile_displayName': 'Nume afișat',
      'profile_noDriverInfo': 'Nu există informații despre șofer',
      'profile_documentLicense': 'Permis de conducere',
      'profile_documentPassport': 'Pașaport',
      'profile_documentAdr': 'Certificat ADR',
      'profile_selectCamera': 'Cameră',
      'profile_selectGallery': 'Galerie',
      'profile_noDocuments': 'Niciun document încărcat',
      'profile_uploadSuccess': 'Document încărcat cu succes',
      'profile_uploadError': 'Încărcare eșuată',
      'driverOverview_emptyState': 'Nicio cursă activă',
      'driverOverview_emptyStateSubtitle': 'Nu ai niciun transport asignat momentan.',
      'driverOverview_etaUnavailable': 'ETA indisponibilă',
      'transport_statusUpdated': 'Status actualizat',
      'transport_eta': 'ETA',
      'transport_elapsedTime': 'Timp scurs',
      'routeShare_noData': 'Nicio rută',
      'routeShare_noDataSubtitle': 'Informațiile de rută nu sunt disponibile încă pentru acest transport.',
      'routeShare_distance': 'Distanță',
      'routeShare_estimatedTime': 'Timp estimat',
      'transport_action_startLoading': 'Începe încărcarea',
      'transport_action_depart': 'Pleacă',
      'transport_action_markDelivered': 'Marchează ca livrat',
      'transport_action_reportDelay': 'Raportează întârzierea',
      'transport_action_noActions': 'Nicio acțiune disponibilă',
      'profitCalculator_title': 'Calculator profit',
      'profitCalculator_revenue': 'Venituri',
      'profitCalculator_fuelCost': 'Cost carburant',
      'profitCalculator_tollCost': 'Cost taxe drum',
      'profitCalculator_maintenance': 'Amortizare mentenanță',
      'profitCalculator_driverCost': 'Cost șofer',
      'profitCalculator_calculate': 'Calculează',
      'profitCalculator_totalCosts': 'Costuri totale',
      'profitCalculator_profit': 'Profit',
      'profitCalculator_profitMargin': 'Marjă profit',
      'profitCalculator_currencySymbol': 'RON',
      'teams_filterAll': 'Toți',
      'teams_filterAvailable': 'Disponibil',
      'teams_filterDriving': 'Conduce',
      'teams_filterOff': 'Oprit',
      'teams_placeholder': 'Lista șoferilor va apărea aici când este conectată la server.',

      // ── Document Center ──
      'documentCenter_title': 'Centru documente',
      'documentCenter_documents': 'Documente',
      'documentCenter_automation': 'Automatizare',
      'documentCenter_ocrTitle': 'Captură documente OCR',
      'documentCenter_ocrDescription': 'Fotografiază un document pentru a extrage automat câmpurile.',
      'documentCenter_capturePhoto': 'Fotografiază',
      'documentCenter_uploadConfirmed': 'Încărcare confirmată, se procesează...',

      // ── Local Download ──
      'localDownload_title': 'Descărcare locală',
      'localDownload_selectCategory': 'Selectează categoria',
      'localDownload_download': 'Descarcă',
      'localDownload_categoryDocuments': 'Documente',
      'localDownload_categoryInvoices': 'Facturi',
      'localDownload_categoryReceipts': 'Chitanțe',
      'localDownload_categoryOcrResults': 'Rezultate OCR',
      'localDownload_categoryTripHistory': 'Istoric curse',
      'localDownload_dateFrom': 'De la',
      'localDownload_dateTo': 'Până la',
      'localDownload_progress': 'Se descarcă...',
      'localDownload_complete': 'Descărcare completă',
    },
    'en': {
      'appName': 'Operion', 'appTagline': 'Logistics ERP',
      'auth_login': 'Sign In', 'auth_email': 'Email', 'auth_password': 'Password',
      'auth_loginButton': 'Sign In', 'auth_loggingIn': 'Signing in...',
      'auth_loginError': 'Incorrect email or password',
      'auth_biometricTitle': 'Unlock with Biometrics',
      'auth_biometricHint': 'Authenticate using fingerprint or face recognition',
      'auth_sessionExpired': 'Your session has expired.', 'auth_loggedOut': 'You have been signed out.',
      'auth_logout': 'Sign Out', 'auth_logoutConfirm': 'Are you sure you want to sign out?',
      'auth_forgotPassword': 'Forgot password?',
      'nav_home': 'Home', 'nav_transports': 'Transports', 'nav_documents': 'Documents',
      'nav_messages': 'Messages', 'nav_notifications': 'Notifications', 'nav_profile': 'Profile',
      'nav_settings': 'Settings', 'nav_jobs': 'Jobs', 'nav_fleet': 'Fleet',       'nav_drivers': 'Drivers',
      'nav_alerts': 'Alerts', 'nav_analytics': 'Analytics',
      'nav_map': 'Map', 'nav_overview': 'Overview',
      'nav_fleetTracker': 'Fleet Tracker', 'nav_copilot': 'AI Copilot', 'nav_more': 'More',
      'nav_teams': 'Teams', 'nav_profitCalculator': 'Profit Calculator',
      'nav_routePlanner': 'Route Planner', 'nav_freightExchange': 'Freight Exchange',
      'nav_documentCenter': 'Document Center', 'nav_localDownload': 'Local Download',
      'routePlanner_origin': 'Origin', 'routePlanner_originHint': 'Enter origin address',
      'routePlanner_destination': 'Destination', 'routePlanner_destinationHint': 'Enter destination address',
      'routePlanner_stops': 'Stops', 'routePlanner_addStop': 'Add Stop',
      'routePlanner_noStops': 'No stops added',
      'routePlanner_noStopsHint': 'Add intermediate stops to optimize your route.',
      'routePlanner_optimize': 'Optimize Route', 'routePlanner_stopNumber': 'Stop',
      'freightExchange_searchHint': 'Search by origin, destination...',
      'freightExchange_empty': 'Freight Exchange',
      'freightExchange_emptyHint': 'Load board data will appear here when the backend is connected.',
      'driver_myDay': 'My Day', 'driver_assignedTransports': 'Assigned Transports',
      'driver_noTransports': 'No transports assigned', 'driver_vehicleInfo': 'Vehicle Info',
      'driver_expenses': 'Expenses', 'driver_documents': 'My Documents',
      'transport_status_planned': 'Planned', 'transport_status_loading': 'Loading',
      'transport_status_in_progress': 'In Progress', 'transport_status_in_transit': 'In Transit',
      'transport_status_delivered': 'Delivered', 'transport_status_cancelled': 'Cancelled',
      'transport_status_overdue': 'Overdue', 'transport_status_invoiced': 'Invoiced',
      'transport_status_paid': 'Paid', 'transport_status_maintenance': 'Maintenance',
      'transport_updateStatus': 'Update Status', 'transport_navigate': 'Navigate',
      'transport_route': 'Route', 'transport_details': 'Transport Details',
      'document_upload': 'Upload Document', 'document_capture': 'Take Photo',
      'document_selectGallery': 'Choose from Gallery', 'document_cmr': 'CMR', 'document_pod': 'POD',
      'document_invoice': 'Invoice', 'document_other': 'Other Document',
      'document_uploading': 'Uploading...', 'document_uploaded': 'Uploaded',
      'document_pending': 'Pending', 'document_failed': 'Upload Failed', 'document_noDocuments': 'No documents',
      'expense_new': 'New Expense', 'expense_type': 'Type', 'expense_fuel': 'Fuel',
      'expense_tolls': 'Tolls', 'expense_perDiem': 'Per Diem', 'expense_other': 'Other',
      'expense_amount': 'Amount', 'expense_date': 'Date', 'expense_receipt': 'Receipt',
      'expense_submit': 'Submit',
      'vehicle_assigned': 'Assigned Vehicle', 'vehicle_plate': 'Plate', 'vehicle_type': 'Type',
      'vehicle_documents': 'Vehicle Documents', 'vehicle_expiry': 'Expires',
      'message_noMessages': 'No messages', 'message_typeMessage': 'Type a message...',
      'message_send': 'Send', 'message_sending': 'Sending...', 'message_sent': 'Sent', 'message_you': 'You',
      'notification_newAssignment': 'New Transport Assigned', 'notification_scheduleChange': 'Schedule Changed',
      'notification_newMessage': 'New Message', 'notification_alert': 'Alert',
      'dispatcher_overview': 'Overview', 'dispatcher_activeJobs': 'Active Jobs',
      'dispatcher_activeDrivers': 'Active Drivers', 'dispatcher_openAlerts': 'Open Alerts',
      'dispatcher_liveFleet': 'Live Fleet', 'dispatcher_approve': 'Approve',
      'dispatcher_reject': 'Reject', 'dispatcher_reassign': 'Reassign',       'dispatcher_quickActions': 'Quick Actions',
      'dispatcher_jobDetails': 'Job Details',
      'dispatcher_markDelivered': 'Mark Delivered',
      'dispatcher_messageDriver': 'Message Driver',
      'dispatcher_reassignConfirm': 'Reassign to {driver}?',
      'dispatcher_reassignSuccess': 'Transport reassigned successfully',
      'dispatcher_noJobs': 'No jobs found',
      'dispatcher_all': 'All',
      'dispatcher_driver': 'Driver',
      'general_created': 'Created',
      'alert_delay': 'Delay', 'alert_maintenance': 'Maintenance',
      'alert_documentExpiry': 'Document Expired', 'alert_compliance': 'Compliance',
      'alert_noAlerts': 'No alerts',
      'analytics_profit': 'Profit', 'analytics_revenue': 'Revenue', 'analytics_costs': 'Costs',
      'analytics_openDesktop': 'Open on desktop for full analytics',
      'analytics_financialSummary': 'Financial Summary',
      'analytics_fleetUtilization': 'Fleet Utilization',
      'analytics_topClients': 'Top Clients',
      'analytics_driverPerformance': 'Driver Performance',
      'analytics_thisMonth': 'This Month',
      'analytics_lastMonth': 'Last Month',
      'analytics_trucksActive': '{active}/{total} trucks active',
      'analytics_noData': 'No data for this period',
      'ocr_results': 'OCR Results',
      'ocr_processing': 'OCR processing in background. Results will appear later.',
      'ocr_confidence': '{percent}% confident',
      'general_cancel': 'Cancel', 'general_confirm': 'Confirm', 'general_save': 'Save',
      'general_delete': 'Delete', 'general_edit': 'Edit', 'general_retry': 'Retry',
      'general_loading': 'Loading...', 'general_error': 'An error occurred',
      'general_noInternet': 'No internet connection', 'general_offline': 'You are offline',
      'general_lastUpdated': 'Last updated', 'general_minAgo': '{count} min ago',
      'general_justNow': 'just now', 'general_hourAgo': 'an hour ago',
      'general_hoursAgo': '{count} hours ago', 'general_pendingSync': 'Pending sync',
      'general_comingSoon': 'Coming Soon',
      'general_comingSoonDescription': 'This feature will be available in a future update',
      'general_openDesktop': 'Open on desktop', 'general_yes': 'Yes', 'general_no': 'No',
      'settings_language': 'Language', 'settings_languageRo': 'Română', 'settings_languageEn': 'English',
      'settings_theme': 'Theme', 'settings_themeSystem': 'System', 'settings_themeLight': 'Light',
      'settings_themeDark': 'Dark',       'settings_appVersion': 'App Version',
      'ai_title': 'AI Co-Pilot', 'ai_emptyStateMessage': 'Ask me anything about your fleet',
      'ai_emptyStatePrompt': 'Try: "Show my available trucks"',
      'ai_clarifyPlaceholder': 'Type your answer...', 'ai_newConversation': 'New conversation',
      'ai_placeholder': 'Type a command or question...',
      'ai_confirmTitle': 'Confirm Action',
      'ai_confirmMessage': 'Operion AI suggests the following action:',
      'copilot_level3_title': 'Level 3 — Type confirmation to proceed',
      'copilot_level3_warning': 'This action is IRREVERSIBLE. Type the confirmation phrase to continue.',
      'copilot_level3_hint': 'Type the confirmation phrase...',
      'copilot_level3_phrase': 'Type: "{phrase}"',
      'profile_personalInfo': 'Personal Information',
      'profile_driverInfo': 'Driver Information',
      'profile_quickLinks': 'Quick Links',
      'profile_licenseNumber': 'License Number',
      'profile_licenseCategory': 'License Category',
      'profile_licenseExpiry': 'License Expiry',
      'profile_phone': 'Phone',
      'profile_displayName': 'Display Name',
      'profile_noDriverInfo': 'No driver information available',
      'profile_documentLicense': 'Driver License',
      'profile_documentPassport': 'Passport',
      'profile_documentAdr': 'ADR Certificate',
      'profile_selectCamera': 'Camera',
      'profile_selectGallery': 'Gallery',
      'profile_noDocuments': 'No documents uploaded',
      'profile_uploadSuccess': 'Document uploaded successfully',
      'profile_uploadError': 'Upload failed',
      'driverOverview_emptyState': 'No active trip',
      'driverOverview_emptyStateSubtitle': 'You have no transport assigned at this time.',
      'driverOverview_etaUnavailable': 'ETA unavailable',
      'transport_statusUpdated': 'Status updated',
      'transport_eta': 'ETA',
      'transport_elapsedTime': 'Elapsed Time',
      'routeShare_noData': 'No route data',
      'routeShare_noDataSubtitle': 'Route information is not yet available for this transport.',
      'routeShare_distance': 'Distance',
      'routeShare_estimatedTime': 'Est. Time',
      'transport_action_startLoading': 'Start Loading',
      'transport_action_depart': 'Depart',
      'transport_action_markDelivered': 'Mark Delivered',
      'transport_action_reportDelay': 'Report Delay',
      'transport_action_noActions': 'No actions available',
      'profitCalculator_title': 'Profit Calculator',
      'profitCalculator_revenue': 'Revenue',
      'profitCalculator_fuelCost': 'Fuel Cost',
      'profitCalculator_tollCost': 'Toll Cost',
      'profitCalculator_maintenance': 'Maintenance Amort.',
      'profitCalculator_driverCost': 'Driver Cost',
      'profitCalculator_calculate': 'Calculate',
      'profitCalculator_totalCosts': 'Total Costs',
      'profitCalculator_profit': 'Profit',
      'profitCalculator_profitMargin': 'Profit Margin',
      'profitCalculator_currencySymbol': '\$',
      'teams_filterAll': 'All',
      'teams_filterAvailable': 'Available',
      'teams_filterDriving': 'Driving',
      'teams_filterOff': 'Off',
      'teams_placeholder': 'Driver list will appear here when connected to the server.',

      // ── Document Center ──
      'documentCenter_title': 'Document Center',
      'documentCenter_documents': 'Documents',
      'documentCenter_automation': 'Automation',
      'documentCenter_ocrTitle': 'OCR Document Capture',
      'documentCenter_ocrDescription': 'Capture a document photo to automatically extract fields.',
      'documentCenter_capturePhoto': 'Capture Photo',
      'documentCenter_uploadConfirmed': 'Upload confirmed, processing...',

      // ── Local Download ──
      'localDownload_title': 'Local Download',
      'localDownload_selectCategory': 'Select Category',
      'localDownload_download': 'Download',
      'localDownload_categoryDocuments': 'Documents',
      'localDownload_categoryInvoices': 'Invoices',
      'localDownload_categoryReceipts': 'Receipts',
      'localDownload_categoryOcrResults': 'OCR Results',
      'localDownload_categoryTripHistory': 'Trip History',
      'localDownload_dateFrom': 'From',
      'localDownload_dateTo': 'To',
      'localDownload_progress': 'Downloading...',
      'localDownload_complete': 'Download complete',
    },
  };
}

class _AppLocalizationsDelegate extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  bool isSupported(Locale locale) =>
      AppLocalizations.supportedLocales.any((l) => l.languageCode == locale.languageCode);

  @override
  Future<AppLocalizations> load(Locale locale) async => AppLocalizations(locale);

  @override
  bool shouldReload(covariant _AppLocalizationsDelegate old) => false;
}
