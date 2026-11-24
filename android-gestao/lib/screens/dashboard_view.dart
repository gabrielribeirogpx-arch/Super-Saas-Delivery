import 'package:flutter/material.dart';

class ManagementMetric extends StatelessWidget {
  const ManagementMetric(this.label, this.value, this.icon, {super.key});

  final String label;
  final String value;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(
      padding: const EdgeInsets.all(14),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 6),
                Text(value, style: Theme.of(context).textTheme.titleLarge),
              ],
            ),
          ),
          const SizedBox(width: 8),
          DecoratedBox(
            decoration: BoxDecoration(
              color: const Color(0xfffff1f2),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Padding(
              padding: const EdgeInsets.all(9),
              child: Icon(icon, color: const Color(0xffdc2626), size: 19),
            ),
          ),
        ],
      ),
    ),
  );
}

enum DashboardPeriod {
  today('Hoje'),
  yesterday('Ontem'),
  last7('Últimos 7 dias'),
  last30('Últimos 30 dias'),
  custom('Personalizado');

  const DashboardPeriod(this.label);
  final String label;

  DateTimeRange range(DateTimeRange? customRange) {
    if (this == custom && customRange != null) return customRange;
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    DateTime daysAgo(int days) => DateTime(now.year, now.month, now.day - days);
    return switch (this) {
      DashboardPeriod.today => DateTimeRange(start: today, end: today),
      DashboardPeriod.yesterday => DateTimeRange(start: daysAgo(1), end: daysAgo(1)),
      DashboardPeriod.last30 => DateTimeRange(start: daysAgo(29), end: today),
      _ => DateTimeRange(start: daysAgo(6), end: today),
    };
  }
}

class DashboardView extends StatelessWidget {
  const DashboardView({
    super.key,
    required this.data,
    required this.period,
    required this.customRange,
    required this.refresh,
    required this.busy,
    required this.onPeriodChanged,
    required this.onOrders,
    required this.onKitchen,
    required this.onCatalog,
    required this.orderStatus,
  });

  final Map<String, dynamic> data;
  final DashboardPeriod period;
  final DateTimeRange? customRange;
  final Future<void> Function() refresh;
  final bool busy;
  final void Function(DashboardPeriod, DateTimeRange?) onPeriodChanged;
  final VoidCallback onOrders;
  final VoidCallback onKitchen;
  final VoidCallback onCatalog;
  final String Function(Map<String, dynamic>) orderStatus;

  String _money(Object? cents) {
    return cents is num
        ? 'R\$ ${(cents / 100).toStringAsFixed(2).replaceAll('.', ',')}'
        : '—';
  }

  Future<void> _selectPeriod(BuildContext context, DashboardPeriod? selected) async {
    if (selected == null) return;
    if (selected != DashboardPeriod.custom) {
      onPeriodChanged(selected, null);
      return;
    }
    final now = DateTime.now();
    final range = await showDateRangePicker(
      context: context,
      firstDate: DateTime(2000),
      lastDate: now,
      initialDateRange: period.range(customRange),
      helpText: 'Selecione o período',
      saveText: 'Aplicar',
    );
    if (context.mounted && range != null) onPeriodChanged(selected, range);
  }

  String _trend(Object? current, Object? previous) {
    if (current is! num || previous is! num) return 'Comparação indisponível';
    if (previous == 0 && current > 0) return 'Em alta vs. período anterior';
    final delta = previous == 0 ? 0 : (current - previous) / previous.abs() * 100;
    final value = delta.toStringAsFixed(1).replaceAll('.', ',');
    return '${delta > 0 ? '+' : ''}$value% vs. período anterior';
  }

  Widget _panel(BuildContext context, String title, Widget child) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 10),
          child,
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final overview = data['overview'] as Map<String, dynamic>?;
    final previous = data['previous'] as Map<String, dynamic>?;
    final points = (data['timeseries'] as List?)?.cast<Map<String, dynamic>>();
    final items = (data['items'] as List?)?.cast<Map<String, dynamic>>();
    final orders = (data['orders'] as List?)?.cast<Map<String, dynamic>>();
    final range = period.range(customRange);
    final material = MaterialLocalizations.of(context);
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              leading: const Icon(Icons.shopping_bag_outlined, color: Color(0xffb91c1c)),
              title: const Text('Sua operação'),
              trailing: TextButton(onPressed: busy ? null : onOrders, child: const Text('Ver pedidos')),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              for (final (label, icon, action) in [
                ('Pedidos', Icons.shopping_bag_outlined, onOrders),
                ('Cozinha', Icons.local_fire_department_outlined, onKitchen),
                ('Cardápio', Icons.restaurant_menu, onCatalog),
              ])
                Expanded(
                  child: Card(
                    margin: const EdgeInsets.symmetric(horizontal: 3),
                    child: InkWell(
                      onTap: busy ? null : action,
                      borderRadius: BorderRadius.circular(16),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        child: Column(children: [
                          Icon(icon, color: const Color(0xffb91c1c)),
                          const SizedBox(height: 6),
                          Text(label),
                        ]),
                      ),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Text('Visão geral', style: Theme.of(context).textTheme.headlineSmall),
          const Text('Acompanhe os principais indicadores por período.'),
          const SizedBox(height: 12),
          DropdownButtonFormField<DashboardPeriod>(
            key: ValueKey(period),
            initialValue: period,
            decoration: const InputDecoration(
              labelText: 'Período',
              border: OutlineInputBorder(),
              filled: true,
              fillColor: Colors.white,
            ),
            items: [
              for (final option in DashboardPeriod.values)
                DropdownMenuItem(value: option, child: Text(option.label)),
            ],
            onChanged: busy ? null : (selected) => _selectPeriod(context, selected),
          ),
          const SizedBox(height: 6),
          Text('${material.formatCompactDate(range.start)} – ${material.formatCompactDate(range.end)}'),
          const SizedBox(height: 16),
          if (overview != null) ...[
            LayoutBuilder(
              builder: (context, constraints) {
                final width = constraints.maxWidth < 290
                    ? constraints.maxWidth
                    : (constraints.maxWidth - 10) / 2;
                return Wrap(
                  spacing: 10,
                  children: [
                    for (final (label, field, monetary) in const [
                      ('Pedidos', 'orders_count', false),
                      ('Faturamento', 'gross_sales_cents', true),
                      ('Ticket médio', 'avg_ticket_cents', true),
                      ('Clientes ativos', 'active_customers', false),
                    ])
                      SizedBox(
                        width: width,
                        child: _panel(context, label, Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              monetary ? _money(overview[field]) : '${overview[field] ?? '—'}',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            const SizedBox(height: 4),
                            Text(_trend(overview[field], previous?[field]), style: Theme.of(context).textTheme.bodySmall),
                          ],
                        )),
                      ),
                  ],
                );
              },
            ),
            _panel(context, 'Vendas no período', points == null || points.isEmpty
                ? Text(points == null ? 'Gráfico indisponível.' : 'Sem dados para este período.')
                : _PerformanceChart(key: ValueKey(range), points: points)),
            _panel(context, 'Top itens', Column(
              children: [
                if (items == null || items.isEmpty)
                  Text(items == null ? 'Itens indisponíveis.' : 'Nenhum item vendido neste período.'),
                for (final (index, item) in (items ?? <Map<String, dynamic>>[]).indexed)
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: CircleAvatar(child: Text('${index + 1}')),
                    title: Text('${item['name']}'),
                    subtitle: Text('${item['qty']} vendidos'),
                    trailing: Text(_money(item['total_cents'])),
                  ),
              ],
            )),
            _panel(context, 'Pedidos recentes', Column(
              children: [
                if (orders == null || orders.isEmpty)
                  Text(orders == null ? 'Pedidos indisponíveis.' : 'Seus pedidos aparecerão aqui.'),
                for (final order in orders ?? <Map<String, dynamic>>[])
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    onTap: busy ? null : onOrders,
                    title: Text('Pedido #${order['daily_order_number'] ?? order['id']}'),
                    subtitle: Text(orderStatus(order)),
                    trailing: Text(_money(order['total_cents'])),
                  ),
              ],
            )),
          ] else if (!busy)
            OutlinedButton(onPressed: refresh, child: const Text('Tentar novamente')),
        ],
      ),
    );
  }
}

class _PerformanceChart extends StatefulWidget {
  const _PerformanceChart({super.key, required this.points});

  final List<Map<String, dynamic>> points;

  @override
  State<_PerformanceChart> createState() => _PerformanceChartState();
}

class _PerformanceChartState extends State<_PerformanceChart> {
  int? _selected;

  num _revenue(Map<String, dynamic> point) =>
      (point['gross_sales_cents'] as num?) ?? 0;

  String _money(num cents) =>
      'R\$ ${(cents / 100).toStringAsFixed(2).replaceAll('.', ',')}';

  String _date(Map<String, dynamic> point) {
    final date = DateTime.tryParse('${point['date']}');
    if (date == null) return '';
    return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    final points = widget.points;
    final active = (_selected ?? points.length - 1).clamp(0, points.length - 1).toInt();
    final current = points[active];
    final total = points.fold<num>(0, (sum, point) => sum + _revenue(point));
    final orders = points.fold<num>(0, (sum, point) =>
        sum + ((point['orders_count'] as num?) ?? 0));
    final max = points.fold<num>(100, (highest, point) =>
        highest > _revenue(point).abs() ? highest : _revenue(point).abs());
    final hasNegative = points.any((point) => _revenue(point) < 0);
    final baseline = hasNegative ? 72.0 : 144.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(_money(total), style: Theme.of(context).textTheme.headlineSmall),
        Text('$orders pedidos · Por dia'),
        const SizedBox(height: 12),
        LayoutBuilder(
          builder: (context, constraints) {
            final width = (constraints.maxWidth / points.length).clamp(44.0, double.infinity).toDouble();
            return SizedBox(
              height: 185,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: points.length,
                itemBuilder: (context, index) {
                  final point = points[index];
                  final revenue = _revenue(point);
                  final height = (revenue.abs() / max * (baseline - 4)).clamp(2.0, baseline).toDouble();
                  return SizedBox(
                    width: width,
                    child: Semantics(
                      button: true,
                      selected: active == index,
                      label: '${_date(point)}: ${_money(revenue)}',
                      child: InkWell(
                        borderRadius: BorderRadius.circular(8),
                        onTap: () => setState(() => _selected = index),
                        child: Column(
                          children: [
                            SizedBox(
                              height: 148,
                              child: Stack(
                                alignment: Alignment.center,
                                children: [
                                  Positioned(
                                    top: baseline,
                                    left: 0,
                                    right: 0,
                                    child: const Divider(height: 1, color: Color(0xffe2e8f0)),
                                  ),
                                  Positioned(
                                    top: revenue < 0 ? baseline : baseline - height,
                                    width: (width * .66).clamp(2.0, 36.0).toDouble(),
                                    height: height,
                                    child: DecoratedBox(
                                      decoration: BoxDecoration(
                                        color: active == index ? const Color(0xffb91c1c) : const Color(0xfff87171),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(_date(point), style: Theme.of(context).textTheme.labelSmall),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            );
          },
        ),
        DecoratedBox(
          decoration: BoxDecoration(
            color: const Color(0xfff8fafc),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Text('${_date(current)}  ·  ${_money(_revenue(current))}  ·  ${current['orders_count'] ?? 0} pedidos'),
          ),
        ),
      ],
    );
  }
}
