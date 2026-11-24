import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/more_menu.dart';

void main() {
  for (final (size, scale) in const [
    (Size(320, 480), 1.0),
    (Size(320, 480), 2.0),
    (Size(640, 320), 2.0),
  ]) {
    testWidgets('Mais reaches the last destination at $size and scale $scale', (tester) async {
      tester.view.physicalSize = size;
      tester.view.devicePixelRatio = 1;
      tester.view.padding = const FakeViewPadding(top: 24, bottom: 24);
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.view.resetPadding);

      const entries = [
        (15, Icons.chat_outlined, 'Wazza'),
        (16, Icons.chat_bubble_outline, 'WhatsApp'),
        (8, Icons.local_shipping_outlined, 'Entregas'),
        (9, Icons.pedal_bike_outlined, 'Entregadores'),
        (6, Icons.account_balance_wallet_outlined, 'Financeiro'),
        (4, Icons.inventory_2_outlined, 'Estoque'),
        (7, Icons.bar_chart_outlined, 'Relatórios'),
        (12, Icons.stars_outlined, 'Fidelidade'),
        (13, Icons.local_offer_outlined, 'Cupons'),
        (14, Icons.card_giftcard_outlined, 'Recompensas'),
        (5, Icons.people_outline, 'Clientes'),
        (10, Icons.manage_accounts_outlined, 'Usuários'),
        (11, Icons.policy_outlined, 'Auditoria'),
      ];
      int? destination;

      await tester.pumpWidget(MaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(scale)),
          child: child!,
        ),
        home: Scaffold(body: Builder(
          builder: (context) => TextButton(
            onPressed: () async => destination = await MoreMenu.show(context, entries),
            child: const Text('Mais'),
          ),
        )),
      ));

      await tester.tap(find.text('Mais'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);

      final entry = find.text('Auditoria');
      await tester.scrollUntilVisible(
        entry,
        90,
        scrollable: find.byType(Scrollable),
      );
      await tester.pumpAndSettle();
      final last = entry.hitTestable();
      expect(last, findsOneWidget);
      await tester.tap(last);
      await tester.pumpAndSettle();
      expect(destination, 11);
      expect(tester.takeException(), isNull);
    });
  }
}
