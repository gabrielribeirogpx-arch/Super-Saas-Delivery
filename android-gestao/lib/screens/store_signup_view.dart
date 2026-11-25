import 'package:flutter/material.dart';
import 'package:html/parser.dart' as html;
import 'package:http/http.dart' as http;

import '../services/management_api.dart';

typedef SignupAccount = ({String store, String email});

class StoreSignupView extends StatefulWidget {
  const StoreSignupView({super.key, required this.api});

  final ManagementApi api;

  @override
  State<StoreSignupView> createState() => _StoreSignupViewState();
}

class _StoreSignupViewState extends State<StoreSignupView> {
  final _form = GlobalKey<FormState>();
  final _business = TextEditingController();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _code = TextEditingController();
  Map<String, dynamic>? _config;
  Map<String, dynamic>? _created;
  bool _busy = false;
  bool _accepted = false;
  bool _showPassword = false;
  bool _confirming = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    for (final controller in [_business, _name, _email, _password, _code]) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _perform(Future<void> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await action();
    } on ManagementApiError catch (error) {
      if (mounted) {
        _error = switch (error.status) {
          401 => 'Código inválido ou expirado. Solicite um novo código.',
          409 =>
            'Já existe um cadastro pendente com esses dados. Confira seu e-mail ou vá para o login.',
          429 => 'Muitas tentativas. Aguarde alguns minutos.',
          400 || 422 => 'Confira os dados e os termos do cadastro.',
          404 || 503 => 'Cadastro pelo aplicativo indisponível neste ambiente.',
          _ => 'Não foi possível concluir. Tente novamente.',
        };
      }
    } catch (_) {
      if (mounted) _error = 'Não foi possível concluir. Tente novamente.';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _load() => _perform(() async {
    final config = await widget.api.signupConfig();
    if (config['native_ready'] != true) throw const ManagementApiError(503);
    if (mounted) _config = config;
  });

  Future<void> _sendCode({bool resend = false}) async {
    if (!resend && !_form.currentState!.validate()) return;
    if (!_accepted) {
      setState(() => _error = 'Aceite os termos para continuar.');
      return;
    }
    FocusScope.of(context).unfocus();
    await _perform(() async {
      await widget.api.sendSignupCode(_email.text.trim());
      if (mounted) {
        _code.clear();
        _confirming = true;
      }
    });
  }

  Future<void> _create() async {
    if (!_form.currentState!.validate()) return;
    FocusScope.of(context).unfocus();
    await _perform(() async {
      final account = await widget.api.createStore({
        'business_name': _business.text.trim(),
        'admin_name': _name.text.trim(),
        'admin_email': _email.text.trim(),
        'admin_password': _password.text,
        'accept_terms': _accepted,
        'terms_version': _config!['terms_version'],
      }, _code.text.trim().toUpperCase());
      if (mounted) {
        _password.clear();
        _code.clear();
        _created = account;
      }
    });
  }

  void _openDocument(String title, String key) {
    final uri = Uri.tryParse(_config?[key]?.toString() ?? '');
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty) {
      setState(() => _error = 'Documento temporariamente indisponível.');
      return;
    }
    Navigator.of(context).push<void>(
      MaterialPageRoute(
        builder: (_) => _SignupDocument(title: title, uri: uri),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label,
    IconData icon, {
    TextInputType? keyboard,
    Iterable<String>? autofill,
    bool obscure = false,
    int? maxLength,
    required String? Function(String?) validate,
  }) => Padding(
    padding: const EdgeInsets.only(bottom: 14),
    child: TextFormField(
      controller: controller,
      enabled: !_busy,
      keyboardType: keyboard,
      autofillHints: autofill,
      obscureText: obscure && !_showPassword,
      autocorrect: keyboard != TextInputType.emailAddress && !obscure,
      maxLength: maxLength,
      validator: validate,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon),
        border: const OutlineInputBorder(),
        counterText: '',
        suffixIcon: obscure
            ? IconButton(
                tooltip: _showPassword ? 'Ocultar senha' : 'Mostrar senha',
                icon: Icon(
                  _showPassword ? Icons.visibility_off : Icons.visibility,
                ),
                onPressed: () => setState(() => _showPassword = !_showPassword),
              )
            : null,
      ),
    ),
  );

  Widget _details() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _field(
        _business,
        'Nome da loja',
        Icons.storefront_outlined,
        autofill: const [AutofillHints.organizationName],
        maxLength: 120,
        validate: (value) =>
            value!.trim().length < 2 ? 'Informe o nome da loja' : null,
      ),
      _field(
        _name,
        'Seu nome',
        Icons.person_outline,
        autofill: const [AutofillHints.name],
        maxLength: 120,
        validate: (value) =>
            value!.trim().length < 2 ? 'Informe seu nome' : null,
      ),
      _field(
        _email,
        'E-mail',
        Icons.alternate_email,
        keyboard: TextInputType.emailAddress,
        autofill: const [AutofillHints.email],
        validate: (value) =>
            RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(value!.trim())
            ? null
            : 'Informe um e-mail válido',
      ),
      _field(
        _password,
        'Sua senha',
        Icons.lock_outline,
        obscure: true,
        autofill: const [AutofillHints.newPassword],
        maxLength: 200,
        validate: (value) =>
            value!.length < 8 ? 'Use pelo menos 8 caracteres' : null,
      ),
      Wrap(
        children: [
          TextButton(
            onPressed: () => _openDocument('Termos de uso', 'terms_url'),
            child: const Text('Termos de uso'),
          ),
          TextButton(
            onPressed: () => _openDocument('Privacidade', 'privacy_url'),
            child: const Text('Privacidade'),
          ),
        ],
      ),
      CheckboxListTile(
        contentPadding: EdgeInsets.zero,
        controlAffinity: ListTileControlAffinity.leading,
        value: _accepted,
        onChanged: _busy
            ? null
            : (value) => setState(() => _accepted = value == true),
        title: const Text(
          'Li e aceito os termos de uso e li a política de privacidade.',
        ),
      ),
      FilledButton(
        onPressed: _busy ? null : _sendCode,
        child: const Text('Enviar código'),
      ),
    ],
  );

  Widget _confirmation() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _field(
        _code,
        'Código do e-mail',
        Icons.verified_user_outlined,
        maxLength: 16,
        validate: (value) =>
            RegExp(r'^[A-Z2-7]{16}$').hasMatch(value!.trim().toUpperCase())
            ? null
            : 'Informe os 16 caracteres do código',
      ),
      FilledButton(
        onPressed: _busy ? null : _create,
        child: const Text('Criar minha loja'),
      ),
      Wrap(
        alignment: WrapAlignment.center,
        children: [
          TextButton(
            onPressed: _busy ? null : () => _sendCode(resend: true),
            child: const Text('Reenviar código'),
          ),
          TextButton(
            onPressed: _busy
                ? null
                : () => setState(() {
                    _confirming = false;
                    _error = null;
                  }),
            child: const Text('Editar dados'),
          ),
        ],
      ),
    ],
  );

  Widget _success(Map<String, dynamic> account) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const Icon(
        Icons.check_circle_outline,
        size: 52,
        color: Color(0xff13795b),
      ),
      const SizedBox(height: 16),
      Text(
        'Identificador da loja',
        style: Theme.of(context).textTheme.labelLarge,
      ),
      SelectableText(account['slug'] as String),
      if (account['subscription_required'] == true) ...[
        const SizedBox(height: 12),
        const Text('A ativação dos recursos pagos depende de uma assinatura.'),
      ],
      const SizedBox(height: 20),
      FilledButton(
        onPressed: () => Navigator.pop<SignupAccount>(context, (
          store: account['slug'] as String,
          email: account['admin_email'] as String,
        )),
        child: const Text('Ir para o login'),
      ),
    ],
  );

  @override
  Widget build(BuildContext context) {
    final account = _created;
    final heading = account != null
        ? 'Sua loja foi criada!'
        : _confirming
        ? 'Confirme seu e-mail'
        : 'Crie sua loja';
    final description = account != null
        ? 'Guarde os dados de acesso para entrar no Gestão.'
        : _confirming
        ? 'Enviamos um código para ${_email.text.trim()}.'
        : 'Cadastre seu restaurante para começar a configurar sua operação.';
    return Scaffold(
      appBar: AppBar(title: const Text('Cadastro')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Card(
                color: Theme.of(context).colorScheme.surface,
                elevation: 0,
                shape: RoundedRectangleBorder(
                  side: BorderSide(
                    color: Theme.of(context).colorScheme.outlineVariant,
                  ),
                  borderRadius: BorderRadius.circular(24),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Center(
                        child: Image.asset(
                          'assets/fomizero-logo.png',
                          width: 148,
                          semanticLabel: 'Fomizero',
                        ),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        heading,
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 8),
                      Text(description, textAlign: TextAlign.center),
                      const SizedBox(height: 20),
                      if (_busy)
                        const LinearProgressIndicator(
                          semanticsLabel: 'Processando cadastro',
                        ),
                      if (_error case final error?) ...[
                        Semantics(
                          liveRegion: true,
                          child: Text(
                            error,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                          ),
                        ),
                        const SizedBox(height: 12),
                      ],
                      if (account != null)
                        _success(account)
                      else if (_config != null)
                        AutofillGroup(
                          child: Form(
                            key: _form,
                            child: KeyedSubtree(
                              key: ValueKey(_confirming),
                              child: _confirming ? _confirmation() : _details(),
                            ),
                          ),
                        )
                      else if (!_busy)
                        OutlinedButton(
                          onPressed: _load,
                          child: const Text('Tentar novamente'),
                        ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SignupDocument extends StatefulWidget {
  const _SignupDocument({required this.title, required this.uri});

  final String title;
  final Uri uri;

  @override
  State<_SignupDocument> createState() => _SignupDocumentState();
}

class _SignupDocumentState extends State<_SignupDocument> {
  late Future<String> _content = _read();

  Future<String> _read() async {
    final client = http.Client();
    try {
      final response = await client
          .get(widget.uri)
          .timeout(const Duration(seconds: 12));
      if (response.statusCode != 200 ||
          response.bodyBytes.length > 512 * 1024) {
        throw const FormatException();
      }
      final document = html.parse(response.bodyBytes);
      final content = document.querySelector('main') ?? document.body;
      if (content == null) throw const FormatException();
      for (final element in content.querySelectorAll(
        'script, style, nav, footer, iframe',
      )) {
        element.remove();
      }
      final blocks = content.querySelectorAll('h1, h2, h3, h4, p, li, tr');
      final text = blocks
          .map((block) => block.text.trim())
          .where((text) => text.isNotEmpty)
          .join('\n\n');
      if (text.isEmpty) throw const FormatException();
      return text;
    } finally {
      client.close();
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: FutureBuilder(
      future: _content,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: OutlinedButton(
              onPressed: () => setState(() => _content = _read()),
              child: const Text('Tentar carregar documento novamente'),
            ),
          );
        }
        if (!snapshot.hasData)
          return const Center(child: CircularProgressIndicator());
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: SelectableText(snapshot.data!),
          ),
        );
      },
    ),
  );
}
