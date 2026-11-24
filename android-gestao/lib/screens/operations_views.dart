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
              Text('Cozinha', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              Card(
                margin: EdgeInsets.zero,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 9, 12, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('Área de produção', style: TextStyle(
                        color: Color(0xff64748b), fontSize: 11, fontWeight: FontWeight.w600,
                      )),
                      const SizedBox(height: 3),
                      DropdownButtonFormField<String>(
                        key: ValueKey(area),
                        initialValue: area,
                        isExpanded: true,
                        borderRadius: BorderRadius.circular(12),
                        dropdownColor: Colors.white,
                        icon: const Icon(Icons.expand_more, color: Color(0xff64748b)),
                        style: const TextStyle(color: Color(0xff0f172a), fontSize: 14, fontWeight: FontWeight.w600),
                        decoration: InputDecoration(
                          prefixIcon: const Icon(Icons.local_fire_department_outlined, color: Color(0xffb91c1c), size: 20),
                          filled: true,
                          fillColor: const Color(0xfff8fafc),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 11),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(color: Color(0xffe2e8f0)),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(color: Color(0xffe2e8f0)),
                          ),
                        ),
                        items: [
                          for (final (value, label) in const [
                            ('COZINHA', 'Cozinha'), ('BAR', 'Bar'),
                            ('FRITURA', 'Fritura'), ('DOCES', 'Doces'),
                          ])
                            DropdownMenuItem(value: value, child: Text(label)),
                        ],
                        onChanged: busy ? null : (value) {
                          if (value != null) onArea(value);
                        },
                      ),
                    ],
                  ),
                ),
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
    required this.mediaOrigin,
    required this.items,
    required this.refresh,
    required this.busy,
    this.onAddCategory,
    this.onAddProduct,
  });

  final List<Map<String, dynamic>> categories;
  final Uri mediaOrigin;
  final List<Map<String, dynamic>> items;
  final Future<void> Function() refresh;
  final bool busy;
  final VoidCallback? onAddCategory;
  final VoidCallback? onAddProduct;

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
          if (onAddCategory != null || onAddProduct != null) ...[
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 4, children: [
              if (onAddCategory != null)
                OutlinedButton.icon(onPressed: busy ? null : onAddCategory,
                  icon: const Icon(Icons.create_new_folder_outlined), label: const Text('Nova categoria')),
              if (onAddProduct != null)
                FilledButton.icon(onPressed: busy ? null : onAddProduct,
                  icon: const Icon(Icons.add), label: const Text('Novo produto')),
            ]),
          ],
          const SizedBox(height: 12),
          if (!busy && items.isEmpty)
            const Text('Nenhum produto para exibir.'),
          for (final category in categories)
              if (!items.any((item) => item['category_id'] == category['id']))
                Card(child: ListTile(title: Text('${category['name']}'), subtitle: const Text('Sem produtos'))),
          for (final group in grouped.entries) ...[
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(group.key, style: Theme.of(context).textTheme.titleMedium),
            ),
            for (final item in group.value)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _ProductPhoto(url: resolveCatalogImage(mediaOrigin, item['image_url'])),
                      const SizedBox(width: 12),
                      Expanded(child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${item['name']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                          if (item['description'] case final String description when description.trim().isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 4),
                              child: Text(description, style: const TextStyle(fontSize: 12, color: Color(0xff64748b))),
                            ),
                          const SizedBox(height: 6),
                          Text(_price(item['price_cents']), style: const TextStyle(fontWeight: FontWeight.w700)),
                        ],
                      )),
                    ],
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }
}

Uri? resolveCatalogImage(Uri origin, Object? value) {
  if (value is! String || value.trim().isEmpty) return null;
  final url = Uri.tryParse(value.trim());
  if (url == null || url.userInfo.isNotEmpty) return null;
  final resolved = origin.resolveUri(url);
  if (const {'localhost', '127.0.0.1', '0.0.0.0'}.contains(resolved.host) &&
      resolved.path.startsWith('/uploads/')) {
    return origin.replace(path: resolved.path, query: resolved.hasQuery ? resolved.query : null);
  }
  if (resolved.scheme == 'http' && resolved.host == origin.host && !resolved.hasPort) {
    return resolved.replace(scheme: 'https');
  }
  return resolved.scheme == 'https' && resolved.host.isNotEmpty ? resolved : null;
}

class _ProductPhoto extends StatelessWidget {
  const _ProductPhoto({required this.url});

  final Uri? url;

  @override
  Widget build(BuildContext context) {
    const fallback = Center(child: Icon(Icons.restaurant_menu, color: Color(0xff94a3b8)));
    final source = url;
    return ClipRRect(
      borderRadius: BorderRadius.circular(12),
      child: ColoredBox(
        color: const Color(0xfff1f5f9),
        child: SizedBox(
          width: 64,
          height: 64,
          child: source == null ? fallback : Image.network(
            source.toString(),
            fit: BoxFit.cover,
            cacheWidth: (64 * MediaQuery.devicePixelRatioOf(context)).ceil(),
            errorBuilder: (_, _, _) => fallback,
          ),
        ),
      ),
    );
  }
}
