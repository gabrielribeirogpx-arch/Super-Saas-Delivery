import 'package:flutter/material.dart';

import '../services/management_api.dart';

class ManagementScreen extends StatefulWidget {
  const ManagementScreen({super.key, required this.api});

  final ManagementApi api;

  @override
  State<ManagementScreen> createState() => _ManagementScreenState();
}

class _ManagementScreenState extends State<ManagementScreen> {
  final _form = GlobalKey<FormState>();
  final _store = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  int? _tenant;
  bool _busy = false;
  String? _error;
  List<Map<String, dynamic>> _orders = [];

  @override
  void dispose() {
    _store.dispose();
    _email.dispose();
    _password.dispose();
    widget.api.close();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() operation) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await operation();
    } on ManagementApiError catch (error) {
      if (mounted) {
        final wasSignedIn = _tenant != null;
        if (error.status == 401) {
          _tenant = null;
          _orders = [];
        }
        _error = switch (error.status) {
          400 => 'Confira o identificador da loja.',
          401 when wasSignedIn => 'Sua sessão expirou. Entre novamente.',
          401 => 'Não foi possível entrar. Confira a loja, o e-mail e a senha.',
          403 => 'Seu usuário não tem acesso a esta operação.',
          412 => 'Confirme seu e-mail pelo painel web antes de entrar no app.',
          429 => 'Muitas tentativas. Aguarde alguns minutos.',
          _ => 'O Fomizero não conseguiu concluir a operação.',
        };
      }
    } catch (_) {
      if (mounted) _error = 'Não foi possível concluir a operação. Tente novamente.';
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _login() async {
    if (!_form.currentState!.validate()) return;

    await _run(() async {
      final password = _password.text;
      _password.clear();
      final tenant = await widget.api.login(_store.text.trim(), _email.text.trim(), password);
      if (!mounted) return;
      setState(() => _tenant = tenant);
      final orders = await widget.api.orders(tenant);
      if (mounted) setState(() => _orders = orders);
    });
  }

  Future<void> _refresh() async {
    final tenant = _tenant;
    if (tenant == null) return;
    await _run(() async {
      final orders = await widget.api.orders(tenant);
      if (mounted) setState(() => _orders = orders);
    });
  }

  Future<void> _logout() async {
    await _run(() async {
      try {
        await widget.api.logout();
      } finally {
        if (mounted) {
          setState(() {
            _tenant = null;
            _orders = [];
          });
        }
      }
    });
  }

  String? _required(String? value) => value == null || value.trim().isEmpty
      ? 'Preencha este campo.'
      : null;

  @override
  Widget build(BuildContext context) {
    final isSignedIn = _tenant != null;
    return Scaffold(
      appBar: AppBar(
        title: Text(isSignedIn ? 'Pedidos' : 'Fomizero Gestão'),
        actions: isSignedIn
            ? [
                IconButton(onPressed: _busy ? null : _refresh, icon: const Icon(Icons.refresh), tooltip: 'Atualizar pedidos'),
                TextButton(onPressed: _busy ? null : _logout, child: const Text('Sair')),
              ]
            : null,
      ),
      body: SafeArea(
        child: Column(
          children: [
            if (_busy) const LinearProgressIndicator(),
            if (_error case final error?)
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(error, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            Expanded(child: isSignedIn ? _ordersView() : _loginView()),
          ],
        ),
      ),
    );
  }

  Widget _loginView() => ListView(
    padding: const EdgeInsets.all(24),
    children: [
      Form(
        key: _form,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(controller: _store, enabled: !_busy, validator: _required, autocorrect: false,
              decoration: const InputDecoration(labelText: 'Identificador da loja', helperText: 'O nome da loja no endereço do Fomizero')),
            TextFormField(controller: _email, enabled: !_busy, validator: _required,
              keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'E-mail')),
            TextFormField(controller: _password, enabled: !_busy, validator: _required,
              obscureText: true, autocorrect: false, enableSuggestions: false,
              onFieldSubmitted: (_) => _login(), decoration: const InputDecoration(labelText: 'Senha')),
            const SizedBox(height: 24),
            FilledButton(onPressed: _busy ? null : _login, child: const Text('Entrar')),
          ],
        ),
      ),
    ],
  );

  Widget _ordersView() => RefreshIndicator(
    onRefresh: _refresh,
    child: ListView.builder(
      physics: const AlwaysScrollableScrollPhysics(),
      itemCount: _orders.isEmpty ? 1 : _orders.length,
      itemBuilder: (context, index) {
        if (_orders.isEmpty) {
          return ListTile(title: Text(_busy ? 'Carregando pedidos…' : 'Nenhum pedido para exibir.'));
        }
        final order = _orders[index];
        final number = order['daily_order_number'] ?? order['id'];
        return ListTile(
          title: Text('Pedido #$number'),
          subtitle: Text(order['customer_name']?.toString() ?? 'Cliente'),
          trailing: Text(order['status']?.toString() ?? ''),
        );
      },
    ),
  );
}
