import 'package:flutter/material.dart';

const _ink = Color(0xff0f172a);
const _muted = Color(0xff64748b);
const _brand = Color(0xffb91c1c);
const _rose = Color(0xfffff1f2);
const _amber = Color(0xff92400e);
const _amberLight = Color(0xfffffbeb);

class DeliveriesView extends StatelessWidget {
  const DeliveriesView({
    super.key,
    required this.orders,
    required this.busy,
    required this.refresh,
    required this.onAdvance,
  });

  final List<Map<String, dynamic>>? orders;
  final bool busy;
  final Future<void> Function() refresh;
  final void Function(int, bool) onAdvance;

  @override
  Widget build(BuildContext context) {
    final rows = orders;
    final onRoute = rows?.where(_isOnRoute).length;
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      _IconTile(Icons.local_shipping_outlined, color: _brand, background: _rose),
                      SizedBox(width: 10),
                      Expanded(child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Entregas', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: _ink)),
                          Text('Acompanhe os pedidos prontos e em rota.', style: TextStyle(fontSize: 12, color: _muted)),
                        ],
                      )),
                    ],
                  ),
                  if (rows != null && onRoute != null) ...[
                    const SizedBox(height: 12),
                    Wrap(
                      spacing: 8,
                      runSpacing: 6,
                      children: [
                        _Badge('$onRoute em rota', color: _brand, background: _rose),
                        _Badge('${rows.where(_isReady).length} prontos', color: _amber, background: _amberLight),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (rows?.isEmpty == true)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Column(children: [
                  _IconTile(Icons.pedal_bike_outlined),
                  SizedBox(height: 10),
                  Text('Nenhuma entrega em andamento', textAlign: TextAlign.center,
                    style: TextStyle(fontWeight: FontWeight.w700)),
                  SizedBox(height: 4),
                  Text('Os pedidos prontos e em rota aparecerão aqui.', textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12, color: _muted)),
                ]),
              ),
            ),
          for (final order in rows ?? const <Map<String, dynamic>>[])
            _DeliveryCard(order: order, busy: busy, onAdvance: onAdvance),
        ],
      ),
    );
  }
}

bool _isOnRoute(Map<String, dynamic> order) =>
    const {'OUT_FOR_DELIVERY', 'SAIU', 'SAIU_PARA_ENTREGA'}.contains(_status(order));

bool _isReady(Map<String, dynamic> order) =>
    const {'READY', 'PRONTO'}.contains(_status(order));

String? _status(Map<String, dynamic> order) => order['status']?.toString().trim().toUpperCase();

String? _text(Object? value) {
  final text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

String _address(Map<String, dynamic> order) {
  final address = order['delivery_address'];
  if (address is Map) {
    final street = [_text(address['street']), _text(address['number'])].nonNulls.join(', ');
    final result = [_text(street), _text(address['neighborhood']), _text(address['complement'])]
        .nonNulls.join(' · ');
    if (result.isNotEmpty) return result;
  }
  return _text(order['endereco']) ?? 'Endereço não informado';
}

class _DeliveryCard extends StatelessWidget {
  const _DeliveryCard({required this.order, required this.busy, required this.onAdvance});

  final Map<String, dynamic> order;
  final bool busy;
  final void Function(int, bool) onAdvance;

  @override
  Widget build(BuildContext context) {
    final onRoute = _isOnRoute(order);
    final ready = _isReady(order);
    final number = order['daily_order_number'] ?? order['id'];
    final id = order['id'];
    final reference = DateTime.tryParse('${onRoute
        ? order['out_for_delivery_at'] ?? order['start_delivery_at'] : order['ready_at']}');
    final elapsed = reference == null ? null : DateTime.now().difference(reference).inMinutes;
    final phone = _text(order['cliente_telefone']);
    final driver = _text(order['assigned_delivery_user_name']) ??
        (order['assigned_delivery_user_id'] != null ? '#${order['assigned_delivery_user_id']}' : 'Aguardando atribuição');
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(height: 4, color: onRoute ? const Color(0xffdc2626) : const Color(0xfff59e0b)),
          Padding(
            padding: const EdgeInsets.all(14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Wrap(
                  alignment: WrapAlignment.spaceBetween,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  spacing: 8,
                  runSpacing: 6,
                  children: [
                    Text('Pedido #$number', style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800, color: _ink)),
                    _Badge(
                      onRoute ? 'Saiu para entrega' : ready ? 'Pronto para entrega' : 'Status indisponível',
                      color: onRoute ? _brand : _amber,
                      background: onRoute ? _rose : _amberLight,
                    ),
                  ],
                ),
                if (elapsed != null) ...[
                  const SizedBox(height: 6),
                  Text('${onRoute ? 'Em rota' : 'Pronto'} há ${elapsed < 0 ? 0 : elapsed} min',
                    style: const TextStyle(fontSize: 12, color: _muted)),
                ],
                const SizedBox(height: 14),
                _DeliveryInfo(Icons.person_outline, 'Cliente', [
                  _text(order['cliente_nome']) ?? 'Cliente',
                  if (phone != null) phone,
                ]),
                const SizedBox(height: 10),
                _DeliveryInfo(Icons.location_on_outlined, 'Endereço de entrega', [_address(order)]),
                if (onRoute) ...[
                  const SizedBox(height: 10),
                  _DeliveryInfo(Icons.pedal_bike_outlined, 'Entregador', [driver]),
                ],
                if ((ready || onRoute) && id is int) ...[
                  const SizedBox(height: 14),
                  if (onRoute)
                    OutlinedButton(
                      onPressed: busy ? null : () => onAdvance(id, true),
                      child: const Text('Marcar entregue'),
                    )
                  else
                    FilledButton.icon(
                      onPressed: busy ? null : () => onAdvance(id, false),
                      icon: const Icon(Icons.arrow_forward, size: 18),
                      label: const Text('Iniciar entrega'),
                    ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class DeliveryUsersView extends StatelessWidget {
  const DeliveryUsersView({super.key, required this.users, required this.refresh});

  final List<Map<String, dynamic>>? users;
  final Future<void> Function() refresh;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        const Card(child: ListTile(
          leading: _IconTile(Icons.pedal_bike_outlined, color: _brand, background: _rose),
          title: Text('Gerenciar entregadores', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          subtitle: Text('Confira os entregadores da sua loja.'),
        )),
        const SizedBox(height: 8),
        Text('Entregadores cadastrados', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 10),
        if (users?.isEmpty == true)
          const Card(child: ListTile(title: Text('Nenhum entregador cadastrado.'))),
        for (final user in users ?? const <Map<String, dynamic>>[])
          Card(child: Padding(
            padding: const EdgeInsets.all(14),
            child: _DeliveryInfo(
              Icons.person_outline,
              _text(user['name']) ?? 'Entregador',
              [_text(user['phone']) ?? 'Telefone não informado', if (_text(user['email']) case final email?) email],
              badge: user['active'] == true
                  ? const _Badge('Ativo', color: Color(0xff047857), background: Color(0xffecfdf5))
                  : const _Badge('Inativo', color: _muted, background: Color(0xfff1f5f9)),
            ),
          )),
      ],
    ),
  );
}

class _DeliveryInfo extends StatelessWidget {
  const _DeliveryInfo(this.icon, this.label, this.lines, {this.badge});

  final IconData icon;
  final String label;
  final List<String> lines;
  final Widget? badge;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      _IconTile(icon),
      const SizedBox(width: 10),
      Expanded(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 8,
            runSpacing: 4,
            children: [
              Text(label, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: _ink)),
              if (badge case final status?) status,
            ],
          ),
          for (final line in lines)
            Text(line, style: const TextStyle(fontSize: 12, color: _muted)),
        ],
      )),
    ],
  );
}

class _IconTile extends StatelessWidget {
  const _IconTile(this.icon, {this.color = _muted, this.background = const Color(0xfff1f5f9)});

  final IconData icon;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(10)),
    child: Padding(padding: const EdgeInsets.all(9), child: Icon(icon, size: 19, color: color)),
  );
}

class _Badge extends StatelessWidget {
  const _Badge(this.label, {required this.color, required this.background});

  final String label;
  final Color color;
  final Color background;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(color: background, borderRadius: BorderRadius.circular(20)),
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      child: Text(label, style: TextStyle(fontSize: 11, color: color, fontWeight: FontWeight.w700)),
    ),
  );
}
