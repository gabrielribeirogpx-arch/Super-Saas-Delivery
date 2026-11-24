import 'package:flutter/material.dart';

class KitchenView extends StatelessWidget {
  const KitchenView({
    super.key,
    required this.orders,
    required this.area,
    required this.onArea,
    required this.refresh,
    required this.onAdvance,
    required this.busy,
  });

  static const areas = ['COZINHA', 'BAR', 'FRITURA', 'DOCES'];

  final List<Map<String, dynamic>> orders;
  final String area;
  final ValueChanged<String> onArea;
  final Future<void> Function() refresh;
  final void Function(int, bool) onAdvance;
  final bool busy;

  int _stage(Map<String, dynamic> order) {
    if ((order['ready_areas'] as List?)?.contains(area) == true) return 2;
    return switch (order['status']?.toString().toUpperCase()) {
      'READY' || 'PRONTO' || 'READY_FOR_DELIVERY' => 2,
      'PREPARING' || 'EM_PREPARO' || 'PREPARO' || 'PREPARANDO' => 1,
      _ => 0,
    };
  }

  @override
  Widget build(BuildContext context) => DefaultTabController(
    length: 3,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Cozinha', style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: area,
                decoration: const InputDecoration(labelText: 'Área de produção', border: OutlineInputBorder()),
                items: [for (final option in areas) DropdownMenuItem(value: option, child: Text(option))],
                onChanged: busy ? null : (value) { if (value != null) onArea(value); },
              ),
            ],
          ),
        ),
        const TabBar(tabs: [Tab(text: 'Pendente'), Tab(text: 'Em preparo'), Tab(text: 'Pronto')]),
        Expanded(
          child: TabBarView(children: [
            for (var stage = 0; stage < 3; stage++)
              RefreshIndicator(
                onRefresh: refresh,
                child: ListView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (!busy && !orders.any((order) => _stage(order) == stage))
                      const Center(child: Text('Nenhum pedido nesta etapa.')),
                    for (final order in orders.where((order) => _stage(order) == stage))
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text('Pedido #${order['daily_order_number'] ?? order['id']}',
                                style: Theme.of(context).textTheme.titleMedium),
                              if (order['cliente_nome'] case final String name when name.isNotEmpty) Text(name),
                              const Divider(),
                              if (order['itens'] case final List items)
                                for (final item in items.whereType<Map>()) ...[
                                  Text('${item['quantity']} × ${item['name']}'),
                                  if (item['modifiers'] case final List modifiers)
                                    for (final modifier in modifiers.whereType<Map>())
                                      Text('  + ${modifier['name'] ?? modifier['option_name'] ?? ''}'),
                                ],
                              if (order['observacao'] case final String note when note.isNotEmpty)
                                Text(note),
                              if (stage < 2 && order['id'] is int) ...[
                                const SizedBox(height: 12),
                                FilledButton(
                                  onPressed: busy ? null : () => onAdvance(order['id'] as int, stage == 1),
                                  child: Text(stage == 0 ? 'Iniciar preparo' : 'Marcar como pronto'),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
          ]),
        ),
      ],
    ),
  );
}

class CatalogView extends StatelessWidget {
  const CatalogView({
    super.key,
    required this.categories,
    required this.items,
    required this.refresh,
    required this.busy,
  });

  final List<Map<String, dynamic>> categories;
  final List<Map<String, dynamic>> items;
  final Future<void> Function() refresh;
  final bool busy;

  String _price(Object? cents) => cents is num
      ? 'R\$ ${(cents / 100).toStringAsFixed(2).replaceAll('.', ',')}'
      : '—';

  @override
  Widget build(BuildContext context) {
    final names = {for (final category in categories) category['id']: category['name']?.toString()};
    final grouped = <String, List<Map<String, dynamic>>>{};
    for (final item in items) {
      final category = names[item['category_id']] ?? 'Sem categoria';
      grouped.putIfAbsent(category, () => []).add(item);
    }
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Text('Cardápio', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 12),
          if (!busy && items.isEmpty) const Text('Nenhum produto para exibir.'),
          for (final group in grouped.entries) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(group.key, style: Theme.of(context).textTheme.titleMedium),
            ),
            for (final item in group.value)
              Card(
                child: ListTile(
                  contentPadding: const EdgeInsets.all(12),
                  leading: const Icon(Icons.restaurant_menu, color: Color(0xffb91c1c)),
                  title: Text('${item['name']}'),
                  subtitle: item['description'] is String ? Text(item['description'] as String) : null,
                  trailing: Text(_price(item['price_cents'])),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
