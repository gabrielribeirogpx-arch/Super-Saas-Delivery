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

  Widget _trend(Object? current, Object? previous, int days) {
    const muted = Color(0xff64748b);
    if (current is! num || previous is! num) {
      return const Text('Sem comparação', style: TextStyle(fontSize: 10, color: muted));
    }

    final risingFromZero = previous == 0 && current > 0;
    final delta = previous == 0 ? 0 : (current - previous) / previous.abs() * 100;
    final rising = risingFromZero || delta > 0;
    final color = rising ? const Color(0xff059669) : delta < 0 ? const Color(0xffe11d48) : muted;
    final value = delta.toStringAsFixed(1).replaceAll('.', ',');
    final comparison = days == 1 ? 'dia anterior' : '$days dias anteriores';
    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 4,
      children: [
        Icon(rising ? Icons.trending_up : delta < 0 ? Icons.trending_down : Icons.remove, size: 13, color: color),
        if (!risingFromZero)
          Text('${delta > 0 ? '+' : ''}$value%', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600, color: color)),
        Text('vs. $comparison', style: const TextStyle(fontSize: 10, color: muted)),
      ],
    );
  }

  Widget _periodFilter(BuildContext context, DateTimeRange range) {
    String date(DateTime value) =>
        '${value.day.toString().padLeft(2, '0')}/${value.month.toString().padLeft(2, '0')}/${value.year}';

    return Card(
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: Color(0xffe2e8f0)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.calendar_today_outlined, size: 14, color: Color(0xff64748b)),
                const SizedBox(width: 6),
                const Text('Período', style: TextStyle(fontSize: 12, color: Color(0xff475569))),
                const Spacer(),
                Flexible(
                  flex: 3,
                  child: PopupMenuButton<DashboardPeriod>(
                    enabled: !busy,
                    initialValue: period,
                    onSelected: (value) => _selectPeriod(context, value),
                    tooltip: 'Selecionar período',
                    itemBuilder: (context) => [
                      for (final option in DashboardPeriod.values)
                        PopupMenuItem(value: option, child: Text(option.label)),
                    ],
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
                      decoration: BoxDecoration(
                        border: Border.all(color: const Color(0xffe2e8f0)),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Flexible(child: Text(period.label, overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500))),
                          const SizedBox(width: 6),
                          const Icon(Icons.expand_more, size: 16),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            if (period == DashboardPeriod.custom)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text('${date(range.start)} – ${date(range.end)}',
                  style: const TextStyle(fontSize: 11, color: Color(0xff64748b))),
              ),
          ],
        ),
      ),
    );
  }

  Widget _shortcutIcon(IconData icon) => DecoratedBox(
    decoration: BoxDecoration(
      color: const Color(0xfffff1f2),
      borderRadius: BorderRadius.circular(10),
    ),
    child: Padding(
      padding: const EdgeInsets.all(8),
      child: Icon(icon, size: 18, color: const Color(0xffb91c1c)),
    ),
  );

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
    final days = DateTime.utc(range.end.year, range.end.month, range.end.day)
        .difference(DateTime.utc(range.start.year, range.start.month, range.start.day))
        .inDays + 1;
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: ListTile(
              contentPadding: const EdgeInsets.symmetric(horizontal: 12),
              leading: _shortcutIcon(Icons.shopping_bag_outlined),
              title: const Text('Sua operação', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
              subtitle: const Text('Pedidos e cozinha em um toque', style: TextStyle(fontSize: 10, color: Color(0xff64748b))),
              trailing: TextButton(onPressed: busy ? null : onOrders, child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('Ver pedidos', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
                  SizedBox(width: 4),
                  Icon(Icons.north_east, size: 13),
                ],
              )),
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
                          _shortcutIcon(icon),
                          const SizedBox(height: 6),
                          Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                        ]),
                      ),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 16),
          const Text('Visão geral', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: Color(0xff0f172a))),
          const SizedBox(height: 3),
          const Text('Acompanhe os principais indicadores por período.',
            style: TextStyle(fontSize: 12, color: Color(0xff64748b))),
          const SizedBox(height: 10),
          _periodFilter(context, range),
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
                        child: Card(
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(label, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500, color: Color(0xff475569))),
                                const SizedBox(height: 6),
                                Text(
                                  monetary ? _money(overview[field]) : '${overview[field] ?? '—'}',
                                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: Color(0xff0f172a)),
                                ),
                                const SizedBox(height: 6),
                                _trend(overview[field], previous?[field], days),
                              ],
                            ),
                          ),
                        ),
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
        Text(_money(total), style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: Color(0xff0f172a))),
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
