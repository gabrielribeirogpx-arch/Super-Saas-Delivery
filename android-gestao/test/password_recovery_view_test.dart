import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/password_recovery_view.dart';
import 'package:fomizero_gestao/services/management_api.dart';

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

  test('onboarding belongs to the selected API environment', () {
    final production = ManagementApi(Uri.parse('https://api.fomizero.com.br'));
    final staging = ManagementApi(
      Uri.parse('https://super-saas-delivery-production.up.railway.app'),
    );
    final unknown = ManagementApi(Uri.parse('https://api.example.com'));
    addTearDown(production.close);
    addTearDown(staging.close);
    addTearDown(unknown.close);
    expect(
      production.onboardingUrl?.toString(),
      'https://www.fomizero.com.br/onboarding?source=gestao_android',
    );
    expect(staging.onboardingUrl?.host, 'meuburger.staging.fomizero.com.br');
    expect(unknown.onboardingUrl, isNull);
  });
}
