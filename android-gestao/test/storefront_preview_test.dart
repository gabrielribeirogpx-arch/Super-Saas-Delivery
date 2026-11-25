import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/storefront_preview.dart';

void main() {
  testWidgets(
    'builds products near the viewport and loads the rest on scroll',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StorefrontPreview(
              data: {
                'tenant': {'name': 'Loja de teste'},
                'categories': [
                  {
                    'id': 1,
                    'name': 'Cardápio completo',
                    'items': [
                      for (var index = 0; index < 30; index++)
                        {'name': 'Produto ${index + 1}', 'price_cents': 1000},
                    ],
                  },
                ],
              },
              origin: Uri.https('example.com'),
              busy: false,
              refresh: () async {},
              edit: null,
            ),
          ),
        ),
      );

      expect(find.text('Loja de teste'), findsWidgets);
      expect(find.text('Produto 30'), findsNothing);
      await tester.scrollUntilVisible(
        find.text('Produto 30'),
        450,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Produto 30'), findsOneWidget);
    },
  );
}
