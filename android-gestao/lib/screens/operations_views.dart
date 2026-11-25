import 'dart:async';

import 'package:flutter/material.dart';

class KitchenView extends StatefulWidget {
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

  @override
  State<KitchenView> createState() => _KitchenViewState();
}

class _KitchenViewState extends State<KitchenView> {
  late final Timer _clock;

  List<Map<String, dynamic>> get orders => widget.orders;
  String get area => widget.area;
  bool get busy => widget.busy;

  @override
  void initState() {
    super.initState();
    _clock = Timer.periodic(const Duration(minutes: 1), (_) => setState(() {}));
  }

  @override
  void dispose() {
    _clock.cancel();
    super.dispose();
  }

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
              Text(
                'Cozinha',
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              Card(
                margin: EdgeInsets.zero,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 9, 12, 8),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Área de produção',
                        style: TextStyle(
                          color: Color(0xff64748b),
                          fontSize: 11,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      const SizedBox(height: 3),
                      DropdownButtonFormField<String>(
                        key: ValueKey(area),
                        initialValue: area,
                        isExpanded: true,
                        borderRadius: BorderRadius.circular(12),
                        dropdownColor: Colors.white,
                        icon: const Icon(
                          Icons.expand_more,
                          color: Color(0xff64748b),
                        ),
                        style: const TextStyle(
                          color: Color(0xff0f172a),
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                        decoration: InputDecoration(
                          prefixIcon: const Icon(
                            Icons.local_fire_department_outlined,
                            color: Color(0xffb91c1c),
                            size: 20,
                          ),
                          filled: true,
                          fillColor: const Color(0xfff8fafc),
                          contentPadding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 11,
                          ),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(
                              color: Color(0xffe2e8f0),
                            ),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(10),
                            borderSide: const BorderSide(
                              color: Color(0xffe2e8f0),
                            ),
                          ),
                        ),
                        items: [
                          for (final (value, label) in const [
                            ('COZINHA', 'Cozinha'),
                            ('BAR', 'Bar'),
                            ('FRITURA', 'Fritura'),
                            ('DOCES', 'Doces'),
                          ])
                            DropdownMenuItem(value: value, child: Text(label)),
                        ],
                        onChanged: busy
                            ? null
                            : (value) {
                                if (value != null) widget.onArea(value);
                              },
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: const Color(0xffeef2f6),
            borderRadius: BorderRadius.circular(16),
          ),
          child: TabBar(
            dividerHeight: 0,
            indicatorSize: TabBarIndicatorSize.tab,
            indicator: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            labelColor: const Color(0xffb91c1c),
            unselectedLabelColor: const Color(0xff475569),
            labelPadding: EdgeInsets.zero,
            tabs: [
              for (
                var index = 0;
                index < _KitchenOrderCard.stages.length;
                index++
              )
                Tab(
                  height: 18 + 2 * MediaQuery.textScalerOf(context).scale(16),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        _KitchenOrderCard.stages[index],
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          fontSize: 12,
                          height: 1.25,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                      Text(
                        '${orders.where((order) => _stage(order) == index).length}',
                        style: const TextStyle(
                          fontSize: 14,
                          height: 1.25,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            children: [
              for (var stage = 0; stage < 3; stage++)
                RefreshIndicator(
                  onRefresh: widget.refresh,
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.all(16),
                    children: [
                      if (!busy &&
                          !orders.any((order) => _stage(order) == stage))
                        const Center(child: Text('Nenhum pedido nesta etapa.')),
                      for (final order in orders.where(
                        (order) => _stage(order) == stage,
                      ))
                        _KitchenOrderCard(
                          key: ValueKey(order['id']),
                          order: order,
                          stage: stage,
                          onAdvance: !busy && stage < 2 && order['id'] is int
                              ? () => widget.onAdvance(
                                  order['id'] as int,
                                  stage == 1,
                                )
                              : null,
                        ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    ),
  );
}

class _KitchenOrderCard extends StatelessWidget {
  const _KitchenOrderCard({
    super.key,
    required this.order,
    required this.stage,
    required this.onAdvance,
  });

  static const stages = ['Pendente', 'Em preparo', 'Pronto'];
  static const ink = Color(0xff0f172a);
  static const muted = Color(0xff475569);
  static const border = Color(0xffe2e8f0);
  static const surface = Color(0xfff8fafc);

  final Map<String, dynamic> order;
  final int stage;
  final VoidCallback? onAdvance;

  int? get _elapsed {
    final value = DateTime.tryParse(order['created_at']?.toString() ?? '');
    if (value == null) return null;
    final created = value.isUtc
        ? value
        : DateTime.utc(
            value.year,
            value.month,
            value.day,
            value.hour,
            value.minute,
            value.second,
          );
    return DateTime.now().difference(created).inMinutes.clamp(0, 99999).toInt();
  }

  @override
  Widget build(BuildContext context) {
    final elapsed = _elapsed;
    final late = stage != 2 && elapsed != null && elapsed >= 25;
    final accent = late
        ? const Color(0xffdc2626)
        : switch (stage) {
            1 => const Color(0xffdc2626),
            2 => const Color(0xff059669),
            _ => const Color(0xff64748b),
          };
    final fulfillment = switch ((order['order_type'] ?? order['tipo_entrega'])
        ?.toString()
        .toUpperCase()) {
      'PICKUP' || 'RETIRADA' => (Icons.shopping_bag_outlined, 'Retirada'),
      'DELIVERY' || 'ENTREGA' => (Icons.local_shipping_outlined, 'Entrega'),
      'TABLE' || 'MESA' => (Icons.table_restaurant_outlined, 'Mesa'),
      _ => null,
    };
    final method = switch (order['payment_method']
        ?.toString()
        .trim()
        .toLowerCase()) {
      'pix' || 'manual_pix' => 'Pix',
      'native_pix' => 'Pix online',
      'money' || 'cash' || 'dinheiro' => 'Dinheiro',
      'credit' || 'credito' || 'crédito' || 'credit_card' => 'Crédito',
      'debit' || 'debito' || 'débito' || 'debit_card' => 'Débito',
      'native_card' => 'Cartão online',
      'card' || 'cartao' || 'cartão' || 'external_card' => 'Cartão',
      _ => null,
    };
    final cents = order['total_cents'];
    final changeFor = order['payment_change_for'];
    final address = [
      for (final key in ['street', 'number', 'neighborhood'])
        if (order[key]?.toString().trim() case final String part
            when part.isNotEmpty)
          part,
    ].join(', ');
    final name = order['cliente_nome']?.toString().trim() ?? '';
    final reference = order['reference']?.toString().trim() ?? '';
    final note = order['observacao']?.toString().trim() ?? '';
    final items = (order['itens'] as List? ?? const []).whereType<Map>();
    return Card(
      clipBehavior: Clip.antiAlias,
      margin: const EdgeInsets.only(bottom: 12),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border(left: BorderSide(color: accent, width: 5)),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 15, 15, 15),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      '#${order['daily_order_number'] ?? order['id'] ?? '—'}',
                      style: const TextStyle(
                        color: ink,
                        fontSize: 28,
                        fontWeight: FontWeight.w900,
                        height: 1.1,
                      ),
                    ),
                  ),
                  if (elapsed != null)
                    _badge(
                      Icons.schedule,
                      '$elapsed min',
                      late ? const Color(0xffb91c1c) : muted,
                      late ? const Color(0xfffee2e2) : const Color(0xfff1f5f9),
                    ),
                ],
              ),
              if (name.isNotEmpty || fulfillment != null) ...[
                const SizedBox(height: 10),
                Wrap(
                  spacing: 10,
                  runSpacing: 6,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    if (name.isNotEmpty)
                      Text(
                        name,
                        style: const TextStyle(
                          color: ink,
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    if (fulfillment != null)
                      _badge(fulfillment.$1, fulfillment.$2, muted, surface),
                  ],
                ),
              ],
              if (method != null || cents is num) ...[
                const SizedBox(height: 10),
                Wrap(
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    if (method != null)
                      _badge(
                        Icons.payments_outlined,
                        method,
                        const Color(0xff334155),
                        surface,
                      ),
                    if (cents is num)
                      _badge(
                        Icons.receipt_long_outlined,
                        'Total ${_reais(cents / 100)}',
                        ink,
                        surface,
                      ),
                    if (method == 'Dinheiro' &&
                        changeFor is num &&
                        changeFor > 0)
                      _badge(
                        Icons.currency_exchange,
                        'Troco para ${_reais(changeFor)}',
                        muted,
                        surface,
                      ),
                  ],
                ),
              ],
              if (fulfillment?.$2 == 'Entrega' && address.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  address,
                  style: const TextStyle(color: muted, fontSize: 13),
                ),
              ],
              if (fulfillment?.$2 == 'Entrega' && reference.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    'Entrega: $reference',
                    style: const TextStyle(color: muted, fontSize: 13),
                  ),
                ),
              const SizedBox(height: 12),
              if (items.isEmpty)
                const Text(
                  'Pedido sem itens para exibir.',
                  style: TextStyle(color: muted),
                ),
              for (final item in items) _item(item),
              if (note.isNotEmpty &&
                  !const {
                    'sem observações',
                    'sem observacoes',
                  }.contains(note.toLowerCase())) ...[
                const SizedBox(height: 4),
                Container(
                  padding: const EdgeInsets.all(11),
                  decoration: BoxDecoration(
                    color: const Color(0xfffffbeb),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xfffde68a)),
                  ),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.info_outline_rounded,
                        size: 17,
                        color: Color(0xff92400e),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Observação',
                              style: TextStyle(
                                fontWeight: FontWeight.w800,
                                color: Color(0xff78350f),
                              ),
                            ),
                            Text(
                              note,
                              style: const TextStyle(color: Color(0xff78350f)),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
              if (stage < 2 && order['id'] is int) ...[
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: onAdvance,
                  style: FilledButton.styleFrom(minimumSize: const Size(0, 46)),
                  icon: Icon(
                    stage == 0 ? Icons.play_arrow_rounded : Icons.check_rounded,
                  ),
                  label: Text(
                    stage == 0 ? 'Iniciar preparo' : 'Marcar como pronto',
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _reais(num value) =>
      'R\$ ${value.toStringAsFixed(2).replaceAll('.', ',')}';

  Widget _badge(
    IconData icon,
    String caption,
    Color foreground,
    Color background,
  ) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: background,
      borderRadius: BorderRadius.circular(20),
    ),
    child: Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 15, color: foreground),
        const SizedBox(width: 4),
        Flexible(
          child: Text(
            caption,
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w800,
              color: foreground,
            ),
          ),
        ),
      ],
    ),
  );

  Widget _item(Map item) => Container(
    margin: const EdgeInsets.only(bottom: 7),
    padding: const EdgeInsets.all(10),
    decoration: BoxDecoration(
      color: surface,
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: border),
    ),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(7),
          ),
          child: Text(
            '${item['quantity'] ?? 1}×',
            style: const TextStyle(color: ink, fontWeight: FontWeight.w900),
          ),
        ),
        const SizedBox(width: 9),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item['name']?.toString() ?? 'Item',
                style: const TextStyle(
                  color: ink,
                  fontSize: 15,
                  fontWeight: FontWeight.w800,
                ),
              ),
              if (item['modifiers'] case final List modifiers)
                for (final modifier in modifiers.whereType<Map>())
                  if (modifier['name'] ?? modifier['option_name']
                      case final String name when name.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 3),
                      child: Text(
                        '+ $name',
                        style: const TextStyle(color: muted, fontSize: 13),
                      ),
                    ),
              if (item['note']?.toString().trim() case final String note
                  when note.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 5),
                  child: Text(
                    'Obs. do item: $note',
                    style: const TextStyle(
                      color: ink,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
            ],
          ),
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
    this.onEditCategory,
    this.onDeleteCategory,
    this.onEditProduct,
    this.onProductAvailability,
  });

  final List<Map<String, dynamic>> categories;
  final Uri mediaOrigin;
  final List<Map<String, dynamic>> items;
  final Future<void> Function() refresh;
  final bool busy;
  final VoidCallback? onAddCategory;
  final VoidCallback? onAddProduct;
  final ValueChanged<Map<String, dynamic>>? onEditCategory;
  final ValueChanged<Map<String, dynamic>>? onDeleteCategory;
  final ValueChanged<Map<String, dynamic>>? onEditProduct;
  final ValueChanged<Map<String, dynamic>>? onProductAvailability;

  String _price(Object? cents) => cents is num
      ? 'R\$ ${(cents / 100).toStringAsFixed(2).replaceAll('.', ',')}'
      : '—';

  @override
  Widget build(BuildContext context) {
    final groups = <Object?, List<Map<String, dynamic>>>{};
    final categoryIds = categories.map((category) => category['id']).toSet();
    for (final item in items) {
      final id = item['category_id'];
      groups.putIfAbsent(categoryIds.contains(id) ? id : null, () => []).add(item);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Expanded(
          child: RefreshIndicator(
            onRefresh: refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.all(16),
              children: [
                Text('Cardápio', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 12),
                if (!busy && items.isEmpty && categories.isEmpty)
                  const Text('Nenhum produto para exibir.'),
                for (final category in categories) ...[
                  _categoryHeader(context, category),
                  if (groups[category['id']] case final products?)
                    for (final item in products) _product(item)
                  else
                    const Padding(
                      padding: EdgeInsets.only(bottom: 12),
                      child: Text('Sem produtos', style: TextStyle(color: Color(0xff64748b))),
                    ),
                ],
                if (groups[null] case final products?) ...[
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text('Sem categoria', style: Theme.of(context).textTheme.titleMedium),
                  ),
                  for (final item in products) _product(item),
                ],
              ],
            ),
          ),
        ),
        if (onAddCategory != null && onAddProduct != null)
          Material(
            color: Colors.white,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),
              child: Row(
                children: [
                  Expanded(child: OutlinedButton.icon(
                    onPressed: busy ? null : onAddCategory,
                    icon: const Icon(Icons.create_new_folder_outlined, size: 17),
                    label: const Text('Nova categoria', textAlign: TextAlign.center),
                    style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 6)),
                  )),
                  const SizedBox(width: 8),
                  Expanded(child: FilledButton.icon(
                    onPressed: busy ? null : onAddProduct,
                    icon: const Icon(Icons.add, size: 17),
                    label: const Text('Novo produto', textAlign: TextAlign.center),
                    style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: 6)),
                  )),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _categoryHeader(BuildContext context, Map<String, dynamic> category) => Row(
    children: [
      Expanded(child: Text('${category['name']}', style: Theme.of(context).textTheme.titleMedium)),
      if (category['active'] == false)
        const Text('Inativa', style: TextStyle(color: Color(0xff64748b), fontSize: 12)),
      if (onEditCategory != null)
        PopupMenuButton<String>(
          enabled: !busy,
          tooltip: 'Opções da categoria ${category['name']}',
          onSelected: (action) {
            if (action == 'edit') onEditCategory!(category);
            if (action == 'delete') onDeleteCategory?.call(category);
          },
          itemBuilder: (_) => [
            const PopupMenuItem(value: 'edit', child: Text('Editar categoria')),
            if (category['active'] != false && onDeleteCategory != null)
              const PopupMenuItem(value: 'delete', child: Text('Excluir categoria')),
          ],
        ),
    ],
  );

  Widget _product(Map<String, dynamic> item) {
    final active = item['active'] != false;
    return Card(
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
                Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                  Text(_price(item['price_cents']), style: const TextStyle(fontWeight: FontWeight.w700)),
                  Text(active ? 'Ativo' : 'Inativo',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600,
                      color: active ? const Color(0xff047857) : const Color(0xff64748b))),
                ]),
              ],
            )),
            if (onEditProduct != null)
              PopupMenuButton<String>(
                padding: EdgeInsets.zero,
                enabled: !busy,
                tooltip: 'Opções do produto ${item['name']}',
                onSelected: (action) {
                  if (action == 'edit') onEditProduct!(item);
                  if (action == 'availability') onProductAvailability?.call(item);
                },
                itemBuilder: (_) => [
                  const PopupMenuItem(value: 'edit', child: Text('Editar produto')),
                  if (onProductAvailability != null)
                    PopupMenuItem(value: 'availability', child: Text(active ? 'Desativar produto' : 'Ativar produto')),
                ],
              ),
          ],
        ),
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
