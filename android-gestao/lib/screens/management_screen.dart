import 'package:flutter/material.dart';

import '../services/management_api.dart';
import 'dashboard_view.dart';

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
  bool _showDashboard = false;
  Map<String, dynamic> _dashboard = {};
  DashboardPeriod _period = DashboardPeriod.last7;
  DateTimeRange? _customRange;
  bool _busy = false;
  final _customer = TextEditingController();
  final _numberFilter = TextEditingController();
  String _statusFilter = '';
  ({String customer, String number, String status}) _appliedFilters =
      (customer: '', number: '', status: '');
  int _page = 1;
  int _totalOrders = 0;
  Map<String, dynamic> _summary = {};
  String? _error;
  List<Map<String, dynamic>> _orders = [];

  @override
  void dispose() {
    _store.dispose();
    _email.dispose();
    _password.dispose();
    _customer.dispose();
    _numberFilter.dispose();
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
          _dashboard = {};
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
      final session = await widget.api.login(_store.text.trim(), _email.text.trim(), password);
      if (!mounted) return;
      setState(() {
        _tenant = session.tenantId;
        _period = DashboardPeriod.last7;
        _customRange = null;
        _showDashboard = const {'admin', 'owner', 'operator', 'cashier'}.contains(session.role);
        _dashboard = {};
        _page = 1;
        _totalOrders = 0;
        _summary = {};
        _statusFilter = '';
        _customer.clear();
        _numberFilter.clear();
      });
      if (_showDashboard) {
        await _loadDashboard();
      } else {
        await _loadOrders(session.tenantId, 1, summary: true);
      }
    });
  }

  Future<void> _loadDashboard() async {
    final range = _period.range(_customRange);
    final dashboard = await widget.api.dashboard(range.start, range.end);
    if (mounted) setState(() => _dashboard = dashboard);
  }

  Future<void> _changePeriod(DashboardPeriod period, DateTimeRange? range) async {
    if (_busy) return;
    setState(() {
      _period = period;
      _customRange = range;
      _dashboard = {};
    });
    await _run(_loadDashboard);
  }

  Future<void> _selectSection(int index) async {
    final dashboard = index == 0;
    if (_busy || dashboard == _showDashboard) return;
    setState(() => _showDashboard = dashboard);
    if (dashboard) {
      if (_dashboard.isEmpty) await _run(_loadDashboard);
    } else if (_summary.isEmpty) {
      await _refresh();
    }
  }

  Future<void> _loadOrders(int tenant, int page, {bool summary = false, bool applyFilters = true}) async {
    final filters = applyFilters
        ? (customer: _customer.text.trim(), number: _numberFilter.text.trim(), status: _statusFilter)
        : _appliedFilters;
    final orders = await widget.api.orders(
      tenant,
      page: page,
      customer: filters.customer,
      number: filters.number,
      status: filters.status,
    );
    if (!mounted) return;
    setState(() {
      _orders = orders.items;
      _totalOrders = orders.total;
      _page = page;
      _appliedFilters = filters;
    });
    if (summary) {
      final counts = await widget.api.orderSummary(tenant);
      if (mounted) setState(() => _summary = counts);
    }
  }

  Future<void> _refresh({int? page, bool summary = true}) async {
    final tenant = _tenant;
    if (tenant == null) return;
    await _run(() => _loadOrders(tenant, page ?? 1, summary: summary, applyFilters: page == null));
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
          _dashboard = {};
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
      backgroundColor: const Color(0xfff8fafc),
      appBar: isSignedIn ? AppBar(
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xff0f172a),
        title: Image.asset('assets/fomizero-logo.png', width: 132, semanticLabel: 'Fomizero'),
        actions: isSignedIn
            ? [
                IconButton(onPressed: _busy ? null : _showDashboard ? () => _run(_loadDashboard) : _refresh, icon: const Icon(Icons.refresh), tooltip: 'Atualizar'),
                TextButton(onPressed: _busy ? null : _logout, child: const Text('Sair', style: TextStyle(color: Color(0xff0f172a)))),
              ]
            : null,
      ) : null,
      bottomNavigationBar: isSignedIn
          ? NavigationBar(
              backgroundColor: Colors.white,
              selectedIndex: _showDashboard ? 0 : 1,
              onDestinationSelected: _selectSection,
              destinations: const [
                NavigationDestination(icon: Icon(Icons.grid_view_outlined), label: 'Início'),
                NavigationDestination(icon: Icon(Icons.shopping_bag_outlined), label: 'Pedidos'),
              ],
            )
          : null,
      body: SafeArea(
        child: Column(
          children: [
            if (_busy) const LinearProgressIndicator(),
            if (_error case final error?)
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(error, style: TextStyle(color: Theme.of(context).colorScheme.error)),
              ),
            Expanded(
              child: !isSignedIn
                  ? _loginView()
                  : _showDashboard
                      ? DashboardView(
                          data: _dashboard,
                          period: _period,
                          customRange: _customRange,
                          busy: _busy,
                          refresh: () => _run(_loadDashboard),
                          onPeriodChanged: _changePeriod,
                          onOrders: () => _selectSection(1),
                          orderStatus: _status,
                        )
                      : _ordersView(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _loginView() => DecoratedBox(
    decoration: const BoxDecoration(
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [Color(0xfffff1f2), Colors.white, Color(0xfff1f5f9)],
      ),
    ),
    child: LayoutBuilder(
      builder: (context, constraints) => SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: (constraints.maxHeight - 32).clamp(0.0, double.infinity).toDouble()),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 448),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Form(
                    key: _form,
                    child: AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Center(child: Image.asset('assets/fomizero-logo.png', width: 170, semanticLabel: 'Fomizero')),
                          const SizedBox(height: 12),
                          Text('Bem-vindo ao Fomizero', textAlign: TextAlign.center,
                            style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
                          const SizedBox(height: 4),
                          const Text('Faça login para acessar sua loja.', textAlign: TextAlign.center),
                          const SizedBox(height: 24),
                          TextFormField(
                            controller: _store,
                            enabled: !_busy,
                            validator: _required,
                            autocorrect: false,
                            decoration: const InputDecoration(labelText: 'Identificador da loja', border: OutlineInputBorder()),
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _email,
                            enabled: !_busy,
                            validator: _required,
                            autofillHints: const [AutofillHints.username],
                            keyboardType: TextInputType.emailAddress,
                            decoration: const InputDecoration(labelText: 'Email', hintText: 'admin@empresa.com', border: OutlineInputBorder()),
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            controller: _password,
                            enabled: !_busy,
                            validator: _required,
                            autofillHints: const [AutofillHints.password],
                            obscureText: true,
                            autocorrect: false,
                            enableSuggestions: false,
                            onFieldSubmitted: (_) => _login(),
                            decoration: const InputDecoration(labelText: 'Senha', border: OutlineInputBorder()),
                          ),
                          const SizedBox(height: 20),
                          FilledButton(
                            onPressed: _busy ? null : _login,
                            child: Text(_busy ? 'Entrando…' : 'Entrar'),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );

  String _status(Map<String, dynamic> order) =>
      switch (order['status']?.toString().trim().toUpperCase()) {
        'RECEBIDO' || 'RECEIVED' || 'PENDING' => 'Recebido',
        'CONFIRMADO' || 'CONFIRMED' => 'Confirmado',
        'EM_PREPARO' || 'PREPARANDO' || 'PREPARING' => 'Em preparo',
        'PRONTO' || 'READY' || 'READY_FOR_DELIVERY' => 'Pronto',
        'DRIVER_ASSIGNED' || 'ASSIGNED' => 'Entregador designado',
        'OUT_FOR_DELIVERY' || 'SAIU_PARA_ENTREGA' || 'IN_TRANSIT' => 'Saiu para entrega',
        'ENTREGUE' || 'DELIVERED' => 'Entregue',
        'CONCLUIDO' || 'COMPLETED' => 'Concluído',
        'CANCELADO' || 'CANCELLED' || 'CANCELED' => 'Cancelado',
        'FAILED' => 'Falhou',
        _ => 'Status indisponível',
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
              Text(_status(order)),
              const Divider(height: 32),
              ListTile(contentPadding: EdgeInsets.zero, title: const Text('Cliente'),
                subtitle: Text(order['customer_name']?.toString() ?? 'Cliente')),
              if (order['tipo_entrega'] case final String delivery when delivery.isNotEmpty)
                ListTile(contentPadding: EdgeInsets.zero, title: const Text('Entrega'),
                  subtitle: Text(delivery)),
              if (order['endereco'] case final String address when address.isNotEmpty)
                ListTile(contentPadding: EdgeInsets.zero, title: const Text('Endereço'),
                  subtitle: Text(address)),
              if (order['forma_pagamento'] case final String payment when payment.isNotEmpty)
                ListTile(contentPadding: EdgeInsets.zero, title: const Text('Forma de pagamento'),
                  subtitle: Text(payment)),
              if (order['observacao'] case final String note when note.isNotEmpty)
                ListTile(contentPadding: EdgeInsets.zero, title: const Text('Observação'),
                  subtitle: Text(note)),
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
                  const Text('Acompanhe os pedidos da sua loja.'),
                  const SizedBox(height: 16),
                  if (_summary.isNotEmpty) ...[
                    SizedBox(
                      height: 100,
                      child: ListView(
                        scrollDirection: Axis.horizontal,
                        children: [
                          for (final (key, label, icon) in const [
                            ('today', 'Pedidos hoje', Icons.shopping_bag_outlined),
                            ('pending', 'Pendentes', Icons.schedule),
                            ('preparing', 'Em preparo', Icons.timer_outlined),
                            ('delivering', 'Em entrega', Icons.local_shipping_outlined),
                            ('completed', 'Concluídos', Icons.check_circle_outline),
                          ])
                            Padding(
                              padding: const EdgeInsets.only(right: 8),
                              child: SizedBox(
                                width: 168,
                                child: ManagementMetric(label, '${_summary[key] ?? 0}', icon),
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],
                  TextField(
                    controller: _customer,
                    enabled: !_busy,
                    decoration: const InputDecoration(labelText: 'Cliente', prefixIcon: Icon(Icons.search), border: OutlineInputBorder()),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _refresh(summary: false),
                  ),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _numberFilter,
                    enabled: !_busy,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Número do pedido', border: OutlineInputBorder()),
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _refresh(summary: false),
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    initialValue: _statusFilter,
                    decoration: const InputDecoration(labelText: 'Status', border: OutlineInputBorder()),
                    items: [
                      const DropdownMenuItem(value: '', child: Text('Todos os status')),
                      for (final status in const [
                        'PENDING', 'CONFIRMADO', 'EM_PREPARO', 'PRONTO',
                        'DRIVER_ASSIGNED', 'SAIU_PARA_ENTREGA', 'ENTREGUE',
                        'CANCELADO', 'FAILED',
                      ])
                        DropdownMenuItem(value: status, child: Text(_status({'status': status}))),
                    ],
                    onChanged: _busy ? null : (value) => setState(() => _statusFilter = value ?? ''),
                  ),
                  const SizedBox(height: 8),
                  FilledButton.tonalIcon(
                    onPressed: _busy ? null : () => _refresh(summary: false),
                    icon: const Icon(Icons.filter_list),
                    label: const Text('Filtrar pedidos'),
                  ),
                ],
              ),
            ),
          ),
          if (_orders.isEmpty)
            SliverFillRemaining(
              hasScrollBody: false,
              child: Center(child: Text(_busy ? 'Carregando pedidos…' : 'Nenhum pedido nesta lista.')),
            )
          else
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(14, 0, 14, 20),
              sliver: SliverList.builder(
                itemCount: _orders.length,
                itemBuilder: (context, index) {
                  final order = _orders[index];
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
                        _status(order),
                        if (_total(order) case final total?) total,
                      ].join(' · ')),
                      trailing: const Icon(Icons.chevron_right),
                    ),
                  );
                },
              ),
            ),
          if (_totalOrders > 8 || _page > 1)
            SliverToBoxAdapter(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(
                    tooltip: 'Página anterior',
                    onPressed: _busy || _page <= 1 ? null : () => _refresh(page: _page - 1, summary: false),
                    icon: const Icon(Icons.chevron_left),
                  ),
                  Text('Página $_page de ${(_totalOrders / 8).ceil().clamp(1, 125000)}'),
                  IconButton(
                    tooltip: 'Próxima página',
                    onPressed: _busy || _page * 8 >= _totalOrders ? null : () => _refresh(page: _page + 1, summary: false),
                    icon: const Icon(Icons.chevron_right),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
