import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/catalog_editor.dart';

void main() {
  test('converts BRL input to cents without floating-point rounding', () {
    expect(parseCatalogPrice('31,90'), 3190);
    expect(parseCatalogPrice('12.5'), 1250);
    expect(parseCatalogPrice('7'), 700);
    expect(parseCatalogPrice('0'), isNull);
    expect(parseCatalogPrice('12,999'), isNull);
  });

  test('the picker limit accommodates a three-megabyte photo', () {
    final image = Uint8List(3 * 1024 * 1024)..setAll(0, [0xff, 0xd8, 0xff]);
    expect(image.length, lessThanOrEqualTo(catalogPhotoLimit));
    expect(catalogPhotoExtension(image), 'jpg');
    expect(catalogPhotoExtension(Uint8List.fromList([1, 2, 3])), isNull);
  });
}
