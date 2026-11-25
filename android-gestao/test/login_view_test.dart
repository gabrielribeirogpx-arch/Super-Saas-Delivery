import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/login_view.dart';

void main() {
  testWidgets('login is usable on a narrow screen with large text', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 480);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final form = GlobalKey<FormState>();
    final store = TextEditingController();
    final email = TextEditingController();
    final password = TextEditingController();
    addTearDown(store.dispose);
    addTearDown(email.dispose);
    addTearDown(password.dispose);
    var submitted = false;
    await tester.pumpWidget(
      MaterialApp(
        builder: (context, child) => MediaQuery(
          data: MediaQuery.of(
            context,
          ).copyWith(textScaler: const TextScaler.linear(1.6)),
          child: child!,
        ),
        home: Scaffold(
          body: LoginView(
            formKey: form,
            store: store,
            email: email,
            password: password,
            validator: (value) =>
                value?.trim().isNotEmpty == true ? null : 'Campo obrigatório',
            onSubmit: () => submitted = form.currentState!.validate(),
            busy: false,
            error: 'Confira os dados da loja.',
          ),
        ),
      ),
    );

    final fields = find.byType(TextFormField);
    await tester.enterText(fields.at(0), 'meuburger');
    await tester.enterText(fields.at(1), 'operador@example.com');
    await tester.ensureVisible(fields.at(2));
    await tester.enterText(fields.at(2), 'senha-de-teste');
    expect(
      tester.widget<EditableText>(find.byType(EditableText).at(2)).obscureText,
      isTrue,
    );
    await tester.tap(find.byTooltip('Mostrar senha'));
    await tester.pump();
    expect(
      tester.widget<EditableText>(find.byType(EditableText).at(2)).obscureText,
      isFalse,
    );
    await tester.ensureVisible(find.text('Entrar'));
    await tester.tap(find.text('Entrar'));
    expect(submitted, isTrue);
    expect(tester.takeException(), isNull);
  });
}
