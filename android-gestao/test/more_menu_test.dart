import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/more_menu.dart';

void main() {
  testWidgets('Mais scrolls to its last destination on a short screen', (tester) async {
    tester.view.physicalSize = const Size(320, 480);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    int? destination;

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: Builder(builder: (context) => TextButton(
          onPressed: () => showModalBottomSheet<void>(
            context: context,
            showDragHandle: true,
            builder: (_) => MoreMenu(
              entries: [
                for (var index = 0; index < 9; index++)
                  (index, Icons.apps, 'Área $index'),
                (9, Icons.policy_outlined, 'Auditoria'),
              ],
              open: (index) => destination = index,
            ),
          ),
          child: const Text('Mais'),
        )),
      ),
    ));

    await tester.tap(find.text('Mais'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    final lastEntry = find.text('Auditoria').hitTestable();
    for (var attempt = 0; attempt < 6 && lastEntry.evaluate().isEmpty; attempt++) {
      await tester.drag(find.byType(ListView), const Offset(0, -145));
      await tester.pumpAndSettle();
    }
    expect(lastEntry, findsOneWidget);
    await tester.tap(lastEntry);
    expect(destination, 9);
    expect(tester.takeException(), isNull);
  });
}
