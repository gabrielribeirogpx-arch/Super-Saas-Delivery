import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/operations_views.dart';

void main() {
  testWidgets(
    'KDS preserves order details and area actions on a narrow screen',
    (tester) async {
      tester.view.physicalSize = const Size(320, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      (int, bool)? action;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: KitchenView(
              area: 'COZINHA',
              onArea: (_) {},
              refresh: () async {},
              busy: false,
              onAdvance: (id, ready) => action = (id, ready),
              orders: [
                {
                  'id': 42,
                  'daily_order_number': 3,
                  'created_at': DateTime.now()
                      .subtract(const Duration(minutes: 27))
                      .toUtc()
                      .toIso8601String(),
                  'order_type': 'pickup',
                  'payment_method': 'DINHEIRO',
                  'total_cents': 2990,
                  'payment_change_for': 50.0,
                  'status': 'RECEBIDO',
                  'cliente_nome': 'Teste',
                  'observacao': 'Carne bem passada',
                  'itens': [
                    {
                      'name': 'Hambúrguer da Casa',
                      'quantity': 2,
                      'note':
                          'Separar o molho para a embalagem, sem trocar o pão.',
                      'modifiers': [
                        {'option_name': 'Sem cebola'},
                      ],
                    },
                  ],
                },
                {'id': 43, 'status': 'EM_PREPARO'},
              ],
            ),
          ),
        ),
      );

      expect(find.text('#3'), findsOneWidget);
      expect(find.text('27 min'), findsOneWidget);
      expect(find.text('Retirada'), findsOneWidget);
      expect(find.text('Dinheiro'), findsOneWidget);
      expect(find.text(r'Total R$ 29,90'), findsOneWidget);
      expect(find.text(r'Troco para R$ 50,00'), findsOneWidget);
      expect(find.text('2×'), findsOneWidget);
      expect(find.text('+ Sem cebola'), findsOneWidget);
      expect(
        find.text(
          'Obs. do item: Separar o molho para a embalagem, sem trocar o pão.',
        ),
        findsOneWidget,
      );
      expect(find.text('Carne bem passada'), findsOneWidget);
      await tester.ensureVisible(find.text('Iniciar preparo'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Iniciar preparo'));
      expect(action, (42, false));

      await tester.tap(find.text('Em preparo'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Marcar como pronto'));
      expect(action, (43, true));
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
    },
  );
}
