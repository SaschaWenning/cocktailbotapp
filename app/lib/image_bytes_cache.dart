import 'dart:collection';
import 'dart:convert';
import 'dart:typed_data';

class ImageBytesCache {
  ImageBytesCache({this.maxBytes = 16 * 1024 * 1024, this.maxEntries = 32});
  final int maxBytes;
  final int maxEntries;
  final _items = LinkedHashMap<String, Uint8List>();
  int _bytes = 0;

  Uint8List decode(String dataUrl) {
    final hit = _items.remove(dataUrl);
    if (hit != null) {
      _items[dataUrl] = hit;
      return hit;
    }
    final comma = dataUrl.indexOf(',');
    if (!dataUrl.startsWith('data:image/') || comma < 0) {
      throw const FormatException('Ungültiges eingebettetes Bild');
    }
    final bytes = base64Decode(dataUrl.substring(comma + 1));
    if (bytes.length > maxBytes || maxEntries <= 0) return bytes;
    while (_items.isNotEmpty &&
        (_bytes + bytes.length > maxBytes || _items.length >= maxEntries)) {
      _bytes -= _items.remove(_items.keys.first)!.length;
    }
    _items[dataUrl] = bytes;
    _bytes += bytes.length;
    return bytes;
  }
}
