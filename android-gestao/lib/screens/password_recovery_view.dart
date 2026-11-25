import 'package:flutter/material.dart';

import '../services/management_api.dart';

class PasswordRecoveryView extends StatefulWidget {
  const PasswordRecoveryView({
    super.key,
    required this.store,
    required this.email,
    required this.request,
  });

  final String store;
  final String email;
  final Future<void> Function(String store, String email) request;

  @override
  State<PasswordRecoveryView> createState() => _PasswordRecoveryViewState();
}

class _PasswordRecoveryViewState extends State<PasswordRecoveryView> {
  final _form = GlobalKey<FormState>();
  late final _store = TextEditingController(text: widget.store);
  late final _email = TextEditingController(text: widget.email);
  bool _busy = false;
  bool _sent = false;
  String? _error;

  @override
  void dispose() {
    _store.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || !_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await widget.request(
        _store.text.trim().toLowerCase(),
        _email.text.trim(),
      );
      if (mounted) setState(() => _sent = true);
    } on ManagementApiError catch (error) {
      if (mounted) {
        _error = switch (error.status) {
          422 => 'Confira o identificador e o e-mail informado.',
          429 => 'Muitas tentativas. Aguarde um minuto e tente novamente.',
          _ => 'Não foi possível enviar a solicitação. Tente novamente.',
        };
      }
    } catch (_) {
      if (mounted)
        _error = 'Não foi possível enviar a solicitação. Tente novamente.';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Recuperar senha')),
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 416),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Form(
                  key: _form,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        _sent
                            ? 'Confira sua caixa de entrada'
                            : 'Recupere seu acesso',
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      if (_sent) ...[
                        const Text(
                          'Se os dados corresponderem a uma conta, você receberá por e-mail um link para criar uma nova senha.',
                        ),
                        const SizedBox(height: 20),
                        FilledButton(
                          onPressed: () => Navigator.of(context).pop(),
                          child: const Text('Voltar ao login'),
                        ),
                      ] else ...[
                        const Text(
                          'Informe a loja e o e-mail que você usa no painel.',
                        ),
                        const SizedBox(height: 20),
                        TextFormField(
                          controller: _store,
                          enabled: !_busy,
                          autocorrect: false,
                          textInputAction: TextInputAction.next,
                          validator: (value) =>
                              RegExp(
                                r'^[a-z0-9][a-z0-9-]{0,79}$',
                              ).hasMatch(value?.trim().toLowerCase() ?? '')
                              ? null
                              : 'Informe o identificador da loja.',
                          decoration: const InputDecoration(
                            labelText: 'Identificador da loja',
                            border: OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 14),
                        TextFormField(
                          controller: _email,
                          enabled: !_busy,
                          autocorrect: false,
                          keyboardType: TextInputType.emailAddress,
                          textInputAction: TextInputAction.done,
                          validator: (value) =>
                              value?.trim().contains('@') == true
                              ? null
                              : 'Informe um e-mail válido.',
                          onFieldSubmitted: (_) => _submit(),
                          decoration: const InputDecoration(
                            labelText: 'E-mail',
                            border: OutlineInputBorder(),
                          ),
                        ),
                        if (_error case final error?) ...[
                          const SizedBox(height: 12),
                          Semantics(
                            liveRegion: true,
                            child: Text(
                              error,
                              style: TextStyle(
                                color: Theme.of(context).colorScheme.error,
                              ),
                            ),
                          ),
                        ],
                        const SizedBox(height: 20),
                        FilledButton(
                          onPressed: _busy ? null : _submit,
                          child: Text(
                            _busy ? 'Enviando…' : 'Enviar link de recuperação',
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
