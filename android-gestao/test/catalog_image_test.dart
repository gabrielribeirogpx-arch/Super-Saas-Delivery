import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/operations_views.dart';

void main() {
  final origin = Uri.parse('https://api.fomizero.com.br');

  test('loads public HTTPS and relative product photos', () {
    const publicUrl = 'https://cdn.example.com/loja/produto.webp?v=2';
    expect(resolveCatalogImage(origin, publicUrl), Uri.parse(publicUrl));
    expect(resolveCatalogImage(origin, '/uploads/produto.webp'),
        origin.resolve('/uploads/produto.webp'));
  });

  test('resolves legacy internal uploads to the configured API', () {
    expect(
      resolveCatalogImage(origin, 'http://localhost:8000/uploads/produto.webp?v=2'),
      origin.resolve('/uploads/produto.webp?v=2'),
    );
    expect(
      resolveCatalogImage(origin, 'http://api.fomizero.com.br/uploads/produto.webp'),
      origin.resolve('/uploads/produto.webp'),
    );
  });

  test('ignores missing images and unsupported URLs', () {
    expect(resolveCatalogImage(origin, null), isNull);
    expect(resolveCatalogImage(origin, ' '), isNull);
    expect(resolveCatalogImage(origin, 'file:///tmp/produto.png'), isNull);
    expect(resolveCatalogImage(origin, 'http://cdn.example.com/produto.png'), isNull);
  });
}
