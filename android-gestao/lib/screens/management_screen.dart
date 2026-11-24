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
  bool _history = false;
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
      setState(() {
        _tenant = tenant;
        _history = false;
      });
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
      backgroundColor: const Color(0xfff7f6f2),
      appBar: isSignedIn ? AppBar(
        backgroundColor: const Color(0xff202c28),
        foregroundColor: Colors.white,
        title: const Text('Fomizero Gestão'),
        actions: isSignedIn
            ? [
                IconButton(onPressed: _busy ? null : _refresh, icon: const Icon(Icons.refresh), tooltip: 'Atualizar pedidos'),
                TextButton(onPressed: _busy ? null : _logout, child: const Text('Sair', style: TextStyle(color: Colors.white))),
              ]
            : null,
      ) : null,
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
      const SizedBox(height: 36),
      Align(
        alignment: Alignment.centerLeft,
        child: DecoratedBox(
          decoration: BoxDecoration(color: Color(0xff202c28), borderRadius: BorderRadius.all(Radius.circular(16))),
          child: Padding(padding: EdgeInsets.all(14), child: Icon(Icons.storefront_outlined, color: Colors.white, size: 32)),
        ),
      ),
      const SizedBox(height: 24),
      Text('Fomizero Gestão', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      const Text('Entre com a conta do painel do seu restaurante.'),
      const SizedBox(height: 32),
      Form(
        key: _form,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(controller: _store, enabled: !_busy, validator: _required, autocorrect: false,
              decoration: const InputDecoration(labelText: 'Identificador da loja', prefixIcon: Icon(Icons.store_outlined), helperText: 'O nome da loja no endereço do Fomizero', border: OutlineInputBorder())),
            const SizedBox(height: 16),
            TextFormField(controller: _email, enabled: !_busy, validator: _required,
              keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'E-mail', prefixIcon: Icon(Icons.mail_outline), border: OutlineInputBorder())),
            const SizedBox(height: 16),
            TextFormField(controller: _password, enabled: !_busy, validator: _required,
              obscureText: true, autocorrect: false, enableSuggestions: false,
              onFieldSubmitted: (_) => _login(), decoration: const InputDecoration(labelText: 'Senha', prefixIcon: Icon(Icons.lock_outline), border: OutlineInputBorder())),
            const SizedBox(height: 24),
            FilledButton(onPressed: _busy ? null : _login, style: FilledButton.styleFrom(minimumSize: const Size(0, 54)), child: const Text('Entrar')),
          ],
        ),
      ),
    ],
  );

  (String, bool) _status(Map<String, dynamic> order) =>
      switch (order['status']?.toString().toUpperCase()) {
        'RECEBIDO' || 'RECEIVED' || 'PENDING' => ('Recebido', false),
        'EM_PREPARO' || 'PREPARING' => ('Em preparo', false),
        'PRONTO' || 'READY' => ('Pronto', false),
        'OUT_FOR_DELIVERY' || 'SAIU_PARA_ENTREGA' => ('Saiu para entrega', false),
        'ENTREGUE' || 'DELIVERED' => ('Entregue', true),
        'CONCLUIDO' || 'COMPLETED' => ('Concluído', true),
        'CANCELADO' || 'CANCELLED' || 'CANCELED' => ('Cancelado', true),
        _ => ('Status indisponível', false),
      };

  String _number(Map<String, dynamic> order) =>
      '#${order['daily_order_number'] ?? order['id']}';

  String? _total(Map<String, dynamic> order) {
    final cents = order['total_cents'];
    final total = cents is num ? cents / 100 : order['valor_total'];
    return total is num
        ? 'R\$ ${total.toStringAsFixed(2).replaceAll('.', ',')}'
        : null;
  }

  void _showOrder(Map<String, dynamic> order) {
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: FractionallySizedBox(
          heightFactor: .68,
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
            children: [
              Text('Pedido ${_number(order)}', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 8),
              Text(_status(order).$1),
              const Divider(height: 32),
              ListTile(contentPadding: EdgeInsets.zero, title: const Text('Cliente'),
                subtitle: Text(order['customer_name']?.toString() ?? 'Cliente')),
              if (_total(order) case final total?)
                ListTile(contentPadding: EdgeInsets.zero, title: const Text('Total'), subtitle: Text(total)),
              if (order['itens'] case final List items)
                for (final item in items.whereType<Map>())
                  ListTile(contentPadding: EdgeInsets.zero, leading: const Icon(Icons.restaurant_menu),
                    title: Text('${item['qtd'] ?? item['quantity'] ?? 1} × ${item['nome'] ?? item['name'] ?? 'Item'}')),
            ],
          ),
        ),
      ),
    );
  }

  Widget _ordersView() {
    final active = _orders.where((order) => !_status(order).$2).toList();
    final done = _orders.where((order) => _status(order).$2).toList();
    final visible = _history ? done : active;
    return RefreshIndicator(
      onRefresh: _refresh,
      child: CustomScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        slivers: [
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(18, 24, 18, 12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Pedidos', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
                  const SizedBox(height: 6),
                  Text('Loja ${_store.text.trim()}'),
                  const SizedBox(height: 16),
                  Wrap(
                    spacing: 8,
                    children: [
                      ChoiceChip(label: Text('Em andamento (${active.length})'), selected: !_history,
                        onSelected: (_) => setState(() => _history = false)),
                      ChoiceChip(label: Text('Histórico (${done.length})'), selected: _history,
                        onSelected: (_) => setState(() => _history = true)),
                    ],
                  ),
                ],
              ),
            ),
          ),
          if (visible.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: Center(child: Text(_busy ? 'Carregando pedidos…' : 'Nenhum pedido nesta lista.')),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 20),
              sliver: SliverList.builder(
                itemCount: visible.length,
                itemBuilder: (context, index) {
                  final order = visible[index];
                  return Card(
                    color: Colors.white,
                    elevation: 0,
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      onTap: () => _showOrder(order),
                      contentPadding: const EdgeInsets.symmetric(vertical: 6, horizontal: 16),
                      title: Text('Pedido ${_number(order)}', style: const TextStyle(fontWeight: FontWeight.w700)),
                      subtitle: Text([
                        order['customer_name']?.toString() ?? 'Cliente',
                        _status(order).$1,
                        if (_total(order) case final total?) total,
                      ].join(' · ')),
                      trailing: const Icon(Icons.chevron_right),
                    ),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }
}
