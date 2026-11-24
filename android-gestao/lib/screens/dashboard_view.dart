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
    required this.orderStatus,
  });

  final Map<String, dynamic> data;
  final DashboardPeriod period;
  final DateTimeRange? customRange;
  final Future<void> Function() refresh;
  final bool busy;
  final void Function(DashboardPeriod, DateTimeRange?) onPeriodChanged;
  final VoidCallback onOrders;
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
            _panel(context, 'Performance diária', points == null || points.isEmpty
                ? Text(points == null ? 'Gráfico indisponível.' : 'Sem dados para este período.')
                : _PerformanceChart(points: points)),
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

class _PerformanceChart extends StatelessWidget {
  const _PerformanceChart({required this.points});

  final List<Map<String, dynamic>> points;

  @override
  Widget build(BuildContext context) {
    final values = [
      for (final point in points) (point['gross_sales_cents'] as num?)?.toDouble() ?? 0,
    ];
    String date(Map<String, dynamic> point) {
      final value = DateTime.tryParse('${point['date']}');
      return value == null ? '' : MaterialLocalizations.of(context).formatShortDate(value);
    }

    return Column(
      children: [
        SizedBox(
          height: 140,
          width: double.infinity,
          child: Semantics(
            label: 'Receita diária. ${points.map((point) => '${date(point)}: ${point['gross_sales_cents']} centavos').join('. ')}',
            child: CustomPaint(painter: _RevenueLine(values)),
          ),
        ),
        Row(
          mainAxisAlignment: points.length == 1 ? MainAxisAlignment.center : MainAxisAlignment.spaceBetween,
          children: [
            Text(date(points.first)),
            if (points.length > 1) Text(date(points.last)),
          ],
        ),
      ],
    );
  }
}

class _RevenueLine extends CustomPainter {
  const _RevenueLine(this.values);
  final List<double> values;

  @override
  void paint(Canvas canvas, Size size) {
    const inset = 6.0;
    final width = size.width - 2 * inset;
    final height = size.height - 2 * inset;
    final grid = Paint()..color = const Color(0xffe2e8f0);
    for (var i = 0; i <= 4; i++) {
      final y = inset + height * i / 4;
      canvas.drawLine(Offset(inset, y), Offset(size.width - inset, y), grid);
    }
    final max = values.fold<double>(1, (highest, value) => value > highest ? value : highest);
    final min = values.fold<double>(0, (lowest, value) => value < lowest ? value : lowest);
    final samples = [
      for (final (index, value) in values.indexed)
        Offset(
          inset + width * (values.length == 1 ? .5 : index / (values.length - 1)),
          inset + height * (1 - (value - min) / (max - min)),
        ),
    ];
    final line = Paint()
      ..color = const Color(0xffdc2626)
      ..strokeWidth = 2;
    for (var index = 1; index < samples.length; index++) {
      canvas.drawLine(samples[index - 1], samples[index], line);
    }
    for (final point in samples) {
      canvas.drawCircle(point, 3, line);
    }
  }

  @override
  bool shouldRepaint(_RevenueLine oldDelegate) => oldDelegate.values != values;
}
