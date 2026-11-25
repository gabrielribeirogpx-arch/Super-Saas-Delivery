import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fomizero_gestao/screens/store_signup_view.dart';
import 'package:fomizero_gestao/services/management_api.dart';

class _SignupApi extends ManagementApi {
  _SignupApi() : super(Uri.https('api.example.com'));

  final configuration = Completer<Map<String, dynamic>>();
  String? recipient;
  Map<String, Object?>? submitted;
  String? proof;

  @override
  Future<Map<String, dynamic>> signupConfig() => configuration.future;

  @override
  Future<void> sendSignupCode(String email) async {
    recipient = email;
  }

  @override
  Future<Map<String, dynamic>> createStore(
    Map<String, Object?> details,
    String code,
  ) async {
    submitted = details;
    proof = code;
    return {'slug': 'meu-restaurante', 'admin_email': recipient};
  }
}

void main() {
  testWidgets(
    'shows the Fomizero brand and completes registration in Flutter',
    (tester) async {
      final api = _SignupApi();
      addTearDown(api.close);
      SignupAccount? account;

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) {
              return Scaffold(
                body: TextButton(
                  onPressed: () async =>
                      account = await Navigator.of(context).push<SignupAccount>(
                        MaterialPageRoute(
                          builder: (_) => StoreSignupView(api: api),
                        ),
                      ),
                  child: const Text('Abrir cadastro'),
                ),
              );
            },
          ),
        ),
      );
      await tester.tap(find.text('Abrir cadastro'));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pump(const Duration(milliseconds: 350));
      expect(find.bySemanticsLabel('Fomizero'), findsOneWidget);
      expect(find.byType(LinearProgressIndicator), findsOneWidget);
      api.configuration.complete({'native_ready': true, 'terms_version': 'v1'});
      await tester.pumpAndSettle();

      Future<void> enter(String label, String value) async {
        final field = find.widgetWithText(TextFormField, label);
        await tester.ensureVisible(field);
        await tester.enterText(field, value);
      }

      Future<void> tap(String label) async {
        final button = find.text(label);
        await tester.ensureVisible(button);
        await tester.tap(button);
        await tester.pumpAndSettle();
      }

      await enter('Nome da loja', 'Meu Restaurante');
      await enter('Seu nome', 'Responsável da Loja');
      await enter('E-mail', 'dono@example.com');
      await enter('Sua senha', 'exemplo-123');
      await tap('Li e aceito os termos de uso e li a política de privacidade.');
      await tap('Enviar código');
      expect(api.recipient, 'dono@example.com');
      await enter('Código do e-mail', 'abcdefghijklmnop');
      await tap('Criar minha loja');
      expect(api.proof, 'ABCDEFGHIJKLMNOP');
      expect(api.submitted?['terms_version'], 'v1');
      expect(find.text('Sua loja foi criada!'), findsOneWidget);
      await tap('Ir para o login');
      expect(account, (store: 'meu-restaurante', email: 'dono@example.com'));
    },
  );
}
