const defaultHomeTabs = <String>['cocktails', 'mocktails', 'shots', 'settings'];
const optionalHomeTabs = <String>['cocktails', 'mocktails', 'shots', 'fill'];

/// Persist stable IDs rather than translated labels or navigation indices.
List<String> normalizeHomeTabs(Object? value) {
  if (value is! List) return List.of(defaultHomeTabs);
  final result = <String>[];
  for (final item in value) {
    if (item is String &&
        optionalHomeTabs.contains(item) &&
        !result.contains(item)) {
      result.add(item);
    }
  }
  // Keep an escape route even when every optional tab has been hidden.
  return [...result, 'settings'];
}
