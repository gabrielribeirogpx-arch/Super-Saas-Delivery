import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/password_recovery_view.dart';

void main() {
  testWidgets(
    'requests recovery using the login fields and confirms neutrally',
    (tester) async {
      (String, String)? request;
      await tester.pumpWidget(
        MaterialApp(
          home: PasswordRecoveryView(
            store: ' MeuBurger ',
            email: ' operador@example.com ',
            request: (store, email) async => request = (store, email),
          ),
        ),
      );
      await tester.tap(find.text('Enviar link de recuperação'));
      await tester.pumpAndSettle();
      expect(request, ('meuburger', 'operador@example.com'));
      expect(find.textContaining('Se os dados corresponderem'), findsOneWidget);
    },
  );
}
