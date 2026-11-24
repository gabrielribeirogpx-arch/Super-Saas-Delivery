import 'package:flutter/material.dart';

const _muted = Color(0xff64748b);
const _brand = Color(0xffb91c1c);
const _brandSurface = Color(0xfffff1f2);

String _money(Object? value) {
  final cents = value is num ? value : num.tryParse('$value');
  if (cents == null || !cents.isFinite) return '—';
  final parts = (cents.abs() / 100).toStringAsFixed(2).split('.');
  final whole = parts[0].replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'), (_) => '.',
  );
  return '${cents < 0 ? '-' : ''}R\$ $whole,${parts[1]}';
}

String _date(Object? value) {
  final date = value is DateTime ? value : DateTime.tryParse('$value')?.toLocal();
  if (date == null) return '—';
  return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year}';
}

class _Tag extends StatelessWidget {
  const _Tag(this.label, {this.danger = false});

  final String label;
  final bool danger;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(
      color: danger ? _brandSurface : const Color(0xffecfdf5),
      borderRadius: BorderRadius.circular(20),
    ),
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      child: Text(label, style: TextStyle(
        fontSize: 11, fontWeight: FontWeight.w600,
        color: danger ? _brand : const Color(0xff047857),
      )),
    ),
  );
}

class InventoryView extends StatelessWidget {
  const InventoryView({
    super.key, required this.items, required this.movements, required this.period,
    required this.busy, required this.refresh, required this.onPeriod,
  });

  final List<Map<String, dynamic>>? items;
  final List<Map<String, dynamic>>? movements;
  final DateTimeRange period;
  final bool busy;
  final Future<void> Function() refresh;
  final ValueChanged<DateTimeRange> onPeriod;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('Estoque atual', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 12),
        if (items?.isEmpty == true) const Text('Nenhum item no estoque.'),
        for (final item in items ?? const <Map<String, dynamic>>[])
          Card(
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
              title: Text('${item['name']}', style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text('Atual: ${item['current_stock']} ${item['unit']}  ·  Mínimo: ${item['min_stock_level']}'),
              trailing: _stockTag(item),
            ),
          ),
        const SizedBox(height: 14),
        Text('Movimentações', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        _PeriodButton(period: period, busy: busy, onPeriod: onPeriod),
        const SizedBox(height: 8),
        if (movements?.isEmpty == true) const Text('Nenhuma movimentação no período.'),
        for (final movement in movements ?? const <Map<String, dynamic>>[])
          Card(
            child: ListTile(
              title: Text('${movement['item_name']}'),
              subtitle: Text([
                _date(movement['created_at']),
                if (movement['reason'] case final String reason when reason.isNotEmpty) reason,
              ].join(' · ')),
              trailing: Text('${movement['type']} · ${movement['quantity']}'),
            ),
          ),
      ],
    ),
  );

  Widget? _stockTag(Map<String, dynamic> item) {
    final current = item['current_stock'];
    final minimum = item['min_stock_level'];
    if (current is! num || minimum is! num) return null;
    final low = current <= minimum;
    return _Tag(low ? 'Baixo' : 'OK', danger: low);
  }
}

enum _CustomerFilter {
  all('Todos'), vip('VIP'), frequent('Frequentes'), inactive('Inativos');
  const _CustomerFilter(this.label);
  final String label;
}

class CustomersView extends StatefulWidget {
  const CustomersView({
    super.key, required this.customers, required this.total, required this.page,
    required this.search, required this.busy, required this.onSearch,
    required this.onPage, required this.onCustomer, required this.refresh,
  });

  final List<Map<String, dynamic>>? customers;
  final int total;
  final int page;
  final String search;
  final bool busy;
  final ValueChanged<String> onSearch;
  final ValueChanged<int> onPage;
  final ValueChanged<int> onCustomer;
  final Future<void> Function() refresh;

  @override
  State<CustomersView> createState() => _CustomersViewState();
}

class _CustomersViewState extends State<CustomersView> {
  late final _search = TextEditingController(text: widget.search);
  _CustomerFilter _filter = _CustomerFilter.all;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  bool _inactive(Map<String, dynamic> customer) {
    final last = DateTime.tryParse('${customer['last_order_date']}');
    return last == null || DateTime.now().difference(last) > const Duration(days: 60);
  }

  bool _matches(Map<String, dynamic> customer) {
    final segment = customer['recurrence_segment']?.toString().toLowerCase();
    return switch (_filter) {
      _CustomerFilter.all => true,
      _CustomerFilter.vip => customer['is_vip'] == true,
      _CustomerFilter.frequent => const {'frequent', 'frequente', 'regular', 'recorrente'}.contains(segment) ||
          ((customer['total_orders'] as num?) ?? 0) >= 5,
      _CustomerFilter.inactive => _inactive(customer),
    };
  }

  @override
  Widget build(BuildContext context) {
    final all = widget.customers;
    final rows = all?.where(_matches) ?? const <Map<String, dynamic>>[];
    final pages = (widget.total / 20).ceil();
    return RefreshIndicator(
      onRefresh: widget.refresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Text('Clientes', style: Theme.of(context).textTheme.headlineSmall),
          const Text('Conheça quem compra na sua loja.', style: TextStyle(color: _muted)),
          const SizedBox(height: 14),
          TextField(
            controller: _search,
            enabled: !widget.busy,
            textInputAction: TextInputAction.search,
            onSubmitted: widget.onSearch,
            decoration: InputDecoration(
              hintText: 'Nome ou telefone',
              border: const OutlineInputBorder(),
              suffixIcon: IconButton(
                onPressed: widget.busy ? null : () => widget.onSearch(_search.text),
                icon: const Icon(Icons.search),
                tooltip: 'Buscar clientes',
              ),
            ),
          ),
          const SizedBox(height: 12),
          if (all != null) ...[
            Row(
              children: [
                Expanded(child: _summaryMetric('Clientes encontrados', '${widget.total}')),
                const SizedBox(width: 8),
                Expanded(child: _summaryMetric('VIP nesta página', '${all.where((c) => c['is_vip'] == true).length}')),
              ],
            ),
            Row(
              children: [
                Expanded(child: _summaryMetric('Inativos nesta página', '${all.where(_inactive).length}')),
                const SizedBox(width: 8),
                Expanded(child: _summaryMetric('Ticket médio da página', _averageTicket(all))),
              ],
            ),
            Wrap(
              spacing: 8,
              children: [
                for (final filter in _CustomerFilter.values)
                  ChoiceChip(
                    label: Text(filter.label),
                    selected: _filter == filter,
                    onSelected: (_) => setState(() => _filter = filter),
                  ),
              ],
            ),
            const Padding(
              padding: EdgeInsets.only(bottom: 12),
              child: Text('Filtros rápidos consideram os clientes desta página.',
                style: TextStyle(fontSize: 11, color: _muted)),
            ),
            if (rows.isEmpty) const Text('Nenhum cliente encontrado.'),
            for (final customer in rows)
              _CustomerCard(customer: customer, onCustomer: widget.busy ? null : widget.onCustomer),
            if (pages > 1)
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  IconButton(onPressed: widget.busy || widget.page <= 1 ? null : () => widget.onPage(widget.page - 1),
                    tooltip: 'Página anterior', icon: const Icon(Icons.chevron_left)),
                  Text('Página ${widget.page} de $pages'),
                  IconButton(onPressed: widget.busy || widget.page >= pages ? null : () => widget.onPage(widget.page + 1),
                    tooltip: 'Próxima página', icon: const Icon(Icons.chevron_right)),
                ],
              ),
          ],
        ],
      ),
    );
  }
}

String _averageTicket(List<Map<String, dynamic>> customers) {
  final orders = customers.fold<num>(0, (sum, customer) => sum + ((customer['total_orders'] as num?) ?? 0));
  final spent = customers.fold<num>(0, (sum, customer) => sum + ((customer['total_spent'] as num?) ?? 0));
  return _money(orders == 0 ? 0 : spent / orders);
}

Widget _summaryMetric(String label, String value) => Card(
  child: Padding(
    padding: const EdgeInsets.all(12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: _muted)),
        const SizedBox(height: 5),
        Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
      ],
    ),
  ),
);

class _CustomerCard extends StatelessWidget {
  const _CustomerCard({required this.customer, required this.onCustomer});
  final Map<String, dynamic> customer;
  final ValueChanged<int>? onCustomer;

  @override
  Widget build(BuildContext context) {
    final rawName = customer['name']?.toString().trim() ?? '';
    final name = rawName.isEmpty ? 'Cliente' : rawName;
    final id = customer['id'];
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: CircleAvatar(backgroundColor: _brandSurface, foregroundColor: _brand, child: Text(String.fromCharCode(name.runes.first).toUpperCase())),
              title: Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text('${customer['phone'] ?? 'Telefone não informado'}'),
              trailing: customer['is_vip'] == true ? const _Tag('VIP', danger: true) : null,
            ),
            DecoratedBox(
              decoration: BoxDecoration(color: const Color(0xfff8fafc), borderRadius: BorderRadius.circular(12)),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text('${customer['total_orders']} pedidos  ·  ${_money(customer['total_spent'])}',
                  style: const TextStyle(fontWeight: FontWeight.w600)),
              ),
            ),
            if (onCustomer != null)
              Row(
              children: [
                  Expanded(child: Text('Último pedido: ${_date(customer['last_order_date'])}',
                    style: const TextStyle(fontSize: 11, color: _muted))),
                if (id is int)
                  TextButton(
                    onPressed: () => onCustomer!(id),
                    child: const Text('Ver histórico'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class CustomerHistoryView extends StatelessWidget {
  const CustomerHistoryView({super.key, required this.customer, required this.orderStatus});

  final Map<String, dynamic> customer;
  final String Function(Map<String, dynamic>) orderStatus;

  @override
  Widget build(BuildContext context) {
    final orders = (customer['orders'] as List?)?.whereType<Map<String, dynamic>>() ?? const <Map<String, dynamic>>[];
    return Scaffold(
      appBar: AppBar(title: const Text('Histórico do cliente')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _CustomerCard(customer: customer, onCustomer: null),
            if (customer['address'] case final String address when address.isNotEmpty)
              Card(child: ListTile(title: const Text('Endereço'), subtitle: Text(address))),
            const SizedBox(height: 12),
            Text('Timeline de pedidos', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            if (orders.isEmpty) const Text('Cliente sem pedidos.'),
            for (final order in orders)
              Card(
                child: ListTile(
                  title: Text('Pedido #${order['daily_order_number'] ?? order['id']}'),
                  subtitle: Text('${orderStatus(order)} · ${_date(order['created_at'])}'),
                  trailing: Text(_money(order['total_cents'])),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _PeriodButton extends StatelessWidget {
  const _PeriodButton({required this.period, required this.busy, required this.onPeriod});

  final DateTimeRange period;
  final bool busy;
  final ValueChanged<DateTimeRange> onPeriod;

  Future<void> _pick(BuildContext context) async {
    final result = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: DateTime.now(),
      initialDateRange: period,
      helpText: 'Selecione o período',
      saveText: 'Aplicar',
    );
    if (context.mounted && result != null) onPeriod(result);
  }

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    onPressed: busy ? null : () => _pick(context),
    icon: const Icon(Icons.date_range_outlined, size: 17),
    label: Text('${_date(period.start)} – ${_date(period.end)}'),
  );
}

class FinanceView extends StatelessWidget {
  const FinanceView({
    super.key, required this.summary, required this.movements, required this.period,
    required this.busy, required this.refresh, required this.onPeriod,
  });

  final Map<String, dynamic>? summary;
  final List<Map<String, dynamic>>? movements;
  final DateTimeRange period;
  final bool busy;
  final Future<void> Function() refresh;
  final ValueChanged<DateTimeRange> onPeriod;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        const Text('Gestão financeira', style: TextStyle(color: _brand, fontWeight: FontWeight.w700)),
        Text('Financeiro', style: Theme.of(context).textTheme.headlineSmall),
        const Text('Acompanhe o caixa e confira as movimentações da loja.', style: TextStyle(color: _muted)),
        const SizedBox(height: 12),
        _PeriodButton(period: period, busy: busy, onPeriod: onPeriod),
        const SizedBox(height: 12),
        Text('Resumo do caixa', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        for (final (label, key, icon, color, surface) in const [
          ('Entradas', 'total_in_cents', Icons.south_west, Color(0xff047857), Color(0xffecfdf5)),
          ('Saídas', 'total_out_cents', Icons.north_east, Color(0xffbe123c), Color(0xfffff1f2)),
          ('Saldo líquido', 'net_cents', Icons.account_balance_wallet_outlined, _brand, _brandSurface),
        ])
          Card(
            color: surface,
            child: ListTile(
              leading: CircleAvatar(backgroundColor: Colors.white, foregroundColor: color, child: Icon(icon, size: 18)),
              title: Text(label, style: TextStyle(color: color, fontWeight: FontWeight.w600)),
              subtitle: Text(_money(summary?[key]), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: Color(0xff0f172a))),
            ),
          ),
        const SizedBox(height: 12),
        Text('Movimentações do caixa', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        if (movements?.isEmpty == true) const Text('Nenhuma movimentação no período.'),
        for (final movement in movements ?? const <Map<String, dynamic>>[])
          Card(child: ListTile(
            title: Text(switch (movement['type']) {'in' => 'Entrada', 'out' => 'Saída', _ => '${movement['type']}' }),
            subtitle: Text([
              switch (movement['category']) {
                'sale' => 'Venda', 'fee' => 'Taxa', 'refund' => 'Devolução',
                'adjustment' => 'Ajuste', _ => '${movement['category']}',
              },
              if (movement['description'] case final String description when description.isNotEmpty) description,
              _date(movement['occurred_at']),
            ].join(' · ')),
            trailing: Text(_money(movement['amount_cents']), style: const TextStyle(fontWeight: FontWeight.w700)),
          )),
      ],
    ),
  );
}

class ReportsView extends StatelessWidget {
  const ReportsView({
    super.key, required this.summary, required this.items, required this.lowStock,
    required this.period, required this.busy, required this.refresh, required this.onPeriod,
  });

  final Map<String, dynamic>? summary;
  final List<Map<String, dynamic>>? items;
  final List<Map<String, dynamic>>? lowStock;
  final DateTimeRange period;
  final bool busy;
  final Future<void> Function() refresh;
  final ValueChanged<DateTimeRange> onPeriod;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('Relatórios financeiros', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 12),
        _PeriodButton(period: period, busy: busy, onPeriod: onPeriod),
        const SizedBox(height: 12),
        if (summary != null) ...[
          Row(children: [
            Expanded(child: _summaryMetric('Pedidos', '${summary?['orders_count'] ?? '—'}')),
            const SizedBox(width: 8),
            Expanded(child: _summaryMetric('Receita bruta', _money(summary?['gross_revenue_cents']))),
          ]),
          Row(children: [
            Expanded(child: _summaryMetric('Receita líquida', _money(summary?['net_revenue_cents']))),
            const SizedBox(width: 8),
            Expanded(child: _summaryMetric('Ticket médio', _money(summary?['avg_ticket_cents'] ?? summary?['average_ticket_cents']))),
          ]),
        ],
        const SizedBox(height: 8),
        Text('Top itens', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        if (items?.isEmpty == true) const Text('Nenhum item vendido no período.'),
        for (final item in items ?? const <Map<String, dynamic>>[])
          Card(child: ListTile(
            leading: const Icon(Icons.restaurant_menu, color: _brand),
            title: Text('${item['item_name'] ?? item['name'] ?? 'Item'}'),
            subtitle: Text('${item['qty'] ?? item['quantity'] ?? 0} vendidos'),
            trailing: Text(_money(item['revenue_cents'] ?? item['gross_revenue_cents'] ?? item['net_revenue_cents'])),
          )),
        const SizedBox(height: 12),
        Text('Baixo estoque', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        if (lowStock?.isEmpty == true) const Text('Nenhum item com estoque baixo.'),
        for (final item in lowStock ?? const <Map<String, dynamic>>[])
          Card(child: ListTile(
            title: Text('${item['name']}'),
            subtitle: Text('Atual: ${item['current_stock']} · Mínimo: ${item['min_stock_level']}'),
            trailing: const _Tag('Baixo', danger: true),
          )),
      ],
    ),
  );
}

class AdminUsersView extends StatelessWidget {
  const AdminUsersView({super.key, required this.users, required this.refresh});

  final List<Map<String, dynamic>>? users;
  final Future<void> Function() refresh;

  String _role(Object? value) => switch (value?.toString().toLowerCase()) {
    'admin' => 'Administrador',
    'owner' => 'Proprietário',
    'operator' => 'Operador',
    'cashier' => 'Caixa',
    'delivery' => 'Entregador',
    _ => value?.toString() ?? '—',
  };

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('Usuários', style: Theme.of(context).textTheme.headlineSmall),
        const Text('Confira os perfis de acesso da sua loja.', style: TextStyle(color: _muted)),
        const SizedBox(height: 12),
        if (users?.isEmpty == true) const Text('Nenhum usuário cadastrado.'),
        for (final user in users ?? const <Map<String, dynamic>>[])
          Card(
            child: ListTile(
              leading: const CircleAvatar(backgroundColor: _brandSurface, foregroundColor: _brand,
                child: Icon(Icons.person_outline)),
              title: Text('${user['name'] ?? 'Usuário'}', style: const TextStyle(fontWeight: FontWeight.w600)),
              subtitle: Text([user['email'], _role(user['role'])].whereType<String>().join(' · ')),
              trailing: _Tag(user['active'] == true ? 'Ativo' : 'Inativo', danger: user['active'] != true),
            ),
          ),
      ],
    ),
  );
}

class AuditView extends StatelessWidget {
  const AuditView({
    super.key, required this.events, required this.period, required this.busy,
    required this.refresh, required this.onPeriod,
  });

  final List<Map<String, dynamic>>? events;
  final DateTimeRange? period;
  final bool busy;
  final Future<void> Function() refresh;
  final ValueChanged<DateTimeRange?> onPeriod;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('Auditoria', style: Theme.of(context).textTheme.headlineSmall),
        const Text('Confira as atividades registradas na loja.', style: TextStyle(color: _muted)),
        const SizedBox(height: 12),
        if (period case final range?) ...[
          _PeriodButton(period: range, busy: busy, onPeriod: onPeriod),
          TextButton(onPressed: busy ? null : () => onPeriod(null), child: const Text('Limpar período')),
        ] else
          OutlinedButton.icon(
            icon: const Icon(Icons.date_range_outlined),
            label: const Text('Filtrar por período'),
            onPressed: busy ? null : () async {
              final now = DateTime.now();
              final selected = await showDateRangePicker(
                context: context, firstDate: DateTime(2000), lastDate: now,
                helpText: 'Período da auditoria', saveText: 'Aplicar',
              );
              if (context.mounted && selected != null) onPeriod(selected);
            },
          ),
        const SizedBox(height: 10),
        if (events?.isEmpty == true) const Text('Nenhum evento encontrado.'),
        for (final event in events ?? const <Map<String, dynamic>>[])
          Card(child: ListTile(
            leading: const Icon(Icons.history, color: _brand),
            title: Text('${event['action'] ?? 'Evento'}', style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text([
              event['user_name'] ?? event['user_email'] ?? 'Sistema',
              if (event['entity_type'] != null) '${event['entity_type']}${event['entity_id'] == null ? '' : ' #${event['entity_id']}'}',
              _timestamp(event['created_at']),
            ].join(' · ')),
            trailing: Text('#${event['id']}'),
          )),
      ],
    ),
  );

  String _timestamp(Object? value) {
    final date = DateTime.tryParse('$value')?.toLocal();
    if (date == null) return '—';
    final hour = date.hour.toString().padLeft(2, '0');
    final minute = date.minute.toString().padLeft(2, '0');
    return '${_date(date)} $hour:$minute';
  }
}
