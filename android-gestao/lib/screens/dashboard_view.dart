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

class DashboardView extends StatelessWidget {
  const DashboardView({
    super.key,
    required this.metrics,
    required this.refresh,
    required this.busy,
  });

  final Map<String, dynamic> metrics;
  final Future<void> Function() refresh;
  final bool busy;

  String _money(String field) {
    final cents = metrics[field];
    return cents is num
        ? 'R\$ ${(cents / 100).toStringAsFixed(2).replaceAll('.', ',')}'
        : '—';
  }

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('Dashboard', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 4),
        const Text('Últimos 7 dias'),
        const SizedBox(height: 16),
        if (metrics.isNotEmpty) ...[
          ManagementMetric('Pedidos', '${metrics['orders_count']}', Icons.shopping_bag_outlined),
          ManagementMetric('Faturamento', _money('gross_sales_cents'), Icons.payments_outlined),
          ManagementMetric('Ticket médio', _money('avg_ticket_cents'), Icons.receipt_long_outlined),
          ManagementMetric('Clientes ativos', '${metrics['active_customers']}', Icons.people_outline),
        ] else if (!busy)
          OutlinedButton(onPressed: refresh, child: const Text('Carregar indicadores')),
      ],
    ),
  );
}
