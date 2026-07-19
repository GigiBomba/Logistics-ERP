/// Centralised conflict resolution for offline-queued actions that are
/// rejected by the server.
///
/// Operion follows a **server-wins** strategy: when a queued PATCH/POST
/// targets a resource whose state has diverged (e.g. a transport was already
/// reassigned by another dispatcher), the server response takes precedence
/// and the local action is discarded.
///
/// Each method returns a user-facing message (in Romanian, the app's primary
/// locale) explaining what happened so the UI can show a non-intrusive toast
/// or snackbar.
class ConflictHandler {
  ConflictHandler._();

  /// Called when an attempt to change a transport's status is rejected
  /// because the current server-side status differs.
  ///
  /// Example: a driver taps "Delivered" while the transport was already
  /// marked "Cancelled" server-side.
  static String resolveStatusConflict(
    String transportId,
    String attemptedStatus,
    String currentStatus,
  ) {
    return 'Transportul $transportId are deja statusul "$currentStatus". '
        'Actualizarea la "$attemptedStatus" nu a fost posibilă. '
        'Datele au fost reîmprospătate.';
  }

  /// Called when a reassign action is rejected because the transport had
  /// already been reassigned to a different driver.
  static String resolveReassignConflict(
    String transportId,
    String attemptedDriver,
  ) {
    return 'Transportul $transportId a fost deja realocat altui șofer. '
        'Acțiunea ta a fost anulată.';
  }

  /// Generic message for an expired or invalid action.
  ///
  /// [actionDescription] is a short label like "Schimbare status" or
  /// "Atribuire șofer".
  static String resolveExpiredAction(String actionDescription) {
    return 'Acțiunea "$actionDescription" nu mai este valabilă. '
        'Datele s-au modificat între timp.';
  }
}
