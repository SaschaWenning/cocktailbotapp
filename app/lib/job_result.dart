/// Only an explicit success for the submitted job permits consumption booking.
bool jobCompletedSuccessfully(Map<String, dynamic> status, String expectedId) {
  if (status['jobId'] != expectedId) {
    throw Exception(
      'Der Pumpenauftrag konnte nicht eindeutig bestätigt werden.',
    );
  }
  switch (status['jobState']) {
    case 'succeeded':
      return true;
    case 'running':
      return false;
    case 'failed':
      throw Exception(
        'Pumpenlauf fehlgeschlagen: ${status['jobError'] ?? 'Unbekannter Fehler'}. '
        'Eine bereits ausgegebene Teilmenge bitte prüfen.',
      );
    case 'cancelled':
      throw Exception(
        'Pumpenlauf abgebrochen: ${status['jobError'] ?? 'Abbruch'}.',
      );
    default:
      throw Exception('Der Abschluss des Pumpenauftrags ist unbekannt.');
  }
}
