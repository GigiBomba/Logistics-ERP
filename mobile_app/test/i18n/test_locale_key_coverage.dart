import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('all locale keys exist in both ro.arb and en.arb', () {
    final roPath = 'lib/l10n/app_ro.arb';
    final enPath = 'lib/l10n/app_en.arb';

    final roJson =
        jsonDecode(File(roPath).readAsStringSync()) as Map<String, dynamic>;
    final enJson =
        jsonDecode(File(enPath).readAsStringSync()) as Map<String, dynamic>;

    final roKeys = roJson.keys.where((k) => !k.startsWith('@')).toSet();
    final enKeys = enJson.keys.where((k) => !k.startsWith('@')).toSet();

    final missingInEn = roKeys.difference(enKeys);
    final missingInRo = enKeys.difference(roKeys);

    expect(missingInEn, isEmpty,
        reason: 'Keys in ro but missing in en: $missingInEn');
    expect(missingInRo, isEmpty,
        reason: 'Keys in en but missing in ro: $missingInRo');
    expect(roKeys.length, equals(enKeys.length), reason: 'Key count mismatch');
  });
}
