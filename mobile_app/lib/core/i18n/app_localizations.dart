import 'package:flutter/widgets.dart';

import '../../l10n/app_localizations.dart';

export '../../l10n/app_localizations.dart';

/// Helper that wraps [AppLocalizations.of] with a null-safe accessor.
class AppLocalizationsHelper {
  AppLocalizationsHelper._();

  static String t(
    BuildContext context,
    String Function(AppLocalizations) selector,
  ) {
    final loc = AppLocalizations.of(context);
    return selector(loc);
  }
}

/// Shorthand extension so you can write `context.loc.auth_login`.
extension AppLocalizationsX on BuildContext {
  AppLocalizations get loc => AppLocalizations.of(this);
}
