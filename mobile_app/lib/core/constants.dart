/// App-wide constants.
///
/// API keys are injected at build time via ``--dart-define`` so they never
/// appear in version control.
///
/// Build locally with:
/// ```sh
/// flutter run --dart-define=OPERION_API_KEY=<key>
/// flutter build apk --dart-define=OPERION_API_KEY=<key>
/// ```
class AppConstants {
  AppConstants._();

  /// Operion backend API key.
  ///
  /// Pass at build time via ``--dart-define=OPERION_API_KEY=...``.
  /// The app will refuse to start if this is empty.
  static const String apiKey = String.fromEnvironment(
    'OPERION_API_KEY',
    defaultValue: '',
  );

  /// Operion backend base URL.
  static const String baseUrl = 'https://api.operionerp.xyz';
}
