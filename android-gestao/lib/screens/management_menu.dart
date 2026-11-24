import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

const _webChannel = MethodChannel('br.com.fomizero.gestao/web');

Future<void> openManagementPage(String store, String path) {
  final slug = store.trim().toLowerCase();
  if (!RegExp(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$').hasMatch(slug)) {
    throw ArgumentError('Identificador de loja inválido.');
  }
  final url = Uri.https('$slug.fomizero.com.br', path);
  return _webChannel.invokeMethod<void>('open', url.toString());
}

class ManagementMenu extends StatelessWidget {
  const ManagementMenu({
    super.key,
    required this.tenantId,
    required this.role,
    required this.onOpen,
  });

  final int tenantId;
  final String role;
  final void Function(String route) onOpen;

  @override
  Widget build(BuildContext context) {
    final groups = role == 'delivery'
        ? {
            'Operação': [('Entregas', '/admin/$tenantId/delivery')],
          }
        : {
            'Operação': [
              ('Dashboard', '/dashboard'),
              ('Pedidos', '/orders'),
              ('Wazza', '/wazza'),
              ('Cozinha', '/kds'),
              ('Entregas', '/admin/$tenantId/delivery'),
              ('Entregadores', '/admin/$tenantId/delivery-users'),
            ],
            'Gestão': [
              ('Financeiro', '/finance'),
              ('Estoque', '/inventory'),
              ('Relatórios', '/reports'),
              ('Cardápio', '/menu'),
              ('Prévia do cardápio', '/storefront-preview'),
              ('Clientes', '/customers'),
            ],
            'Crescimento': [
              ('WhatsApp', '/whatsapp'),
              ('IA', '/ai'),
              ('Fidelidade', '/marketing/loyalty'),
              ('Cupons', '/marketing/coupons'),
              ('Recompensas', '/marketing/rewards'),
            ],
            'Minha loja': [
              ('Operação da loja', '/minha-loja'),
              ('Instalar app', '/install-app'),
              ('Usuários', '/users'),
              ('Auditoria', '/audit'),
              if (role == 'admin' || role == 'owner')
                ('Minha assinatura', '/subscriptions'),
            ],
          };

    return SafeArea(
      child: FractionallySizedBox(
        heightFactor: .92,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Image.asset('assets/fomizero-logo.png', width: 132, semanticLabel: 'Fomizero'),
                IconButton(
                  onPressed: () => Navigator.pop(context),
                  tooltip: 'Fechar menu',
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            for (final group in groups.entries) ...[
              Padding(
                padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
                child: Text(group.key, style: Theme.of(context).textTheme.titleSmall),
              ),
              Card(
                child: Column(
                  children: [
                    for (final (label, route) in group.value)
                      ListTile(
                        title: Text(label),
                        subtitle: route == '/dashboard' || route == '/orders'
                            ? null
                            : const Text('Abre no painel web'),
                        trailing: Icon(
                          route == '/dashboard' || route == '/orders'
                              ? Icons.chevron_right
                              : Icons.open_in_new,
                        ),
                        onTap: () {
                          Navigator.pop(context);
                          onOpen(route);
                        },
                      ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
