import 'package:flutter/material.dart';

const _brand = Color(0xffb91c1c);
const _muted = Color(0xff64748b);

enum WazzaDecision {
  approve('Autorizar alteração'),
  reject('Rejeitar'),
  verify('Verificar nos registros oficiais');

  const WazzaDecision(this.label);
  final String label;
}

String _when(Object? raw) {
  final date = DateTime.tryParse('$raw')?.toLocal();
  if (date == null) return '—';
  String two(int value) => value.toString().padLeft(2, '0');
  return '${two(date.day)}/${two(date.month)}/${date.year} às ${two(date.hour)}:${two(date.minute)}';
}

String _value(Object? cents) => cents is num
    ? 'R\$ ${(cents / 100).toStringAsFixed(2).replaceAll('.', ',')}'
    : '—';

String _state(Object? state) => switch (state) {
  'pending_review' => 'Pendente de análise',
  'rejected' => 'Rejeitada',
  'manual_resolution' => 'Aguardando resolução manual',
  'applied' => 'Aplicada',
  'failed' => 'Falha na aplicação',
  _ => 'Estado indisponível',
};

class WazzaView extends StatelessWidget {
  const WazzaView({
    super.key, required this.connection, required this.requests, required this.busy,
    required this.refresh, required this.previous, required this.next,
    required this.decide,
  });

  final Map<String, dynamic>? connection;
  final List<Map<String, dynamic>>? requests;
  final bool busy;
  final Future<void> Function() refresh;
  final VoidCallback? previous;
  final VoidCallback? next;
  final void Function(int, WazzaDecision, String) decide;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('Wazza', style: Theme.of(context).textTheme.headlineSmall),
        const Text('Acompanhe a integração e as solicitações dos clientes.', style: TextStyle(color: _muted)),
        const SizedBox(height: 14),
        Card(child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('Estado da integração', style: TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 8),
              Text(switch (connection?['state']) {
                'disabled' => 'Integração desativada',
                'setup_required' => 'Configuração pendente no Fomizero',
                'awaiting_contact' => 'Aguardando primeiro contato do Wazza',
                'contact_verified' => 'Comunicação com o Wazza verificada',
                _ => busy ? 'Consultando integração…' : 'Estado indisponível',
              }),
              if (connection?['last_contact'] case final String last)
                Text('Último contato: ${_when(last)}', style: const TextStyle(fontSize: 12, color: _muted)),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: busy ? null : refresh,
                icon: const Icon(Icons.sync, size: 18),
                label: const Text('Verificar conexão'),
              ),
            ],
          ),
        )),
        const SizedBox(height: 12),
        Text('Solicitações do WhatsApp', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 10),
        if (requests?.isEmpty == true)
          const Card(child: ListTile(title: Text('Nenhuma solicitação nesta página.'))),
        for (final request in requests ?? const <Map<String, dynamic>>[])
          _RequestCard(key: ValueKey(request['request_id']), request: request, busy: busy, decide: decide),
        if (previous != null || next != null)
          Wrap(
            spacing: 8,
            children: [
              if (previous != null)
                OutlinedButton(onPressed: busy ? null : previous, child: const Text('Página anterior')),
              if (next != null)
                OutlinedButton(onPressed: busy ? null : next, child: const Text('Próxima página')),
            ],
          ),
      ],
    ),
  );
}

class _RequestCard extends StatelessWidget {
  const _RequestCard({super.key, required this.request, required this.busy, required this.decide});

  final Map<String, dynamic> request;
  final bool busy;
  final void Function(int, WazzaDecision, String) decide;

  Future<void> _confirm(BuildContext context, int id, WazzaDecision decision) async {
    final reason = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      builder: (_) => _DecisionForm(decision: decision),
    );
    if (context.mounted && reason != null) decide(id, decision, reason);
  }

  String _items(Object? data) {
    if (data is! List || data.isEmpty) return 'Sem itens detalhados';
    return data.whereType<Map>().map((line) {
      final modifiers = line['modifiers'];
      final names = modifiers is List
          ? modifiers.whereType<Map>().map((modifier) => modifier['option_name']).whereType<String>().join(', ')
          : '';
      return '${line['quantity']} × ${line['name']}${names.isEmpty ? '' : ' ($names)'}';
    }).join('\n');
  }

  Widget _comparison(String title, Object? amount, String items) => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(color: const Color(0xfff8fafc), borderRadius: BorderRadius.circular(12)),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: const TextStyle(fontSize: 12, color: _muted)),
        Text(_value(amount), style: const TextStyle(fontWeight: FontWeight.w700)),
        Text(items),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final state = request['state'];
    final id = request['request_id'];
    final cancel = request['action'] == 'cancel';
    return Card(child: Padding(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('${cancel ? 'Cancelamento' : 'Edição'} do pedido #${request['order_id']}',
            style: const TextStyle(fontWeight: FontWeight.w700)),
          Align(alignment: Alignment.centerLeft, child: Chip(label: Text(_state(state)))),
          Text(switch (request['reason']) {
            'in_preparation' => 'Pedido em preparo',
            'benefits_or_stock' => 'Há efeitos em benefícios ou estoque',
            'payment_review' => 'Pagamento precisa de análise',
            'other_channel' => 'Pedido de outro canal',
            'customer_confirmed' => 'Alteração confirmada pelo cliente',
            _ => 'Pedido precisa de análise operacional',
          }),
          Text(_when(request['created_at']), style: const TextStyle(fontSize: 12, color: _muted)),
          if (state == 'manual_resolution')
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text('A solicitação foi aprovada, mas ainda não foi aplicada ao pedido.',
                style: TextStyle(color: Color(0xff92400e), fontWeight: FontWeight.w600)),
            ),
          const SizedBox(height: 8),
          _comparison('Pedido no momento da solicitação', request['before_cents'], _items(request['before_items'])),
          const SizedBox(height: 6),
          _comparison('Alteração proposta', request['after_cents'],
            cancel ? 'Cancelamento integral' : _items(request['after_items'])),
          if (request['decision_reason'] case final String reason)
            Padding(padding: const EdgeInsets.only(top: 8),
              child: Text('Decisão do operador #${request['decided_by']} em ${_when(request['decided_at'])}. $reason')),
          if (request['resolution_reason'] case final String reason)
            Padding(padding: const EdgeInsets.only(top: 8),
              child: Text('Verificação do operador #${request['resolved_by']} em ${_when(request['resolved_at'])}. $reason')),
          if (id is int && state == 'pending_review') ...[
            FilledButton(onPressed: busy ? null : () => _confirm(context, id, WazzaDecision.approve), child: const Text('Autorizar alteração')),
            OutlinedButton(onPressed: busy ? null : () => _confirm(context, id, WazzaDecision.reject), child: const Text('Rejeitar')),
          ],
          if (id is int && state == 'manual_resolution')
            FilledButton(onPressed: busy ? null : () => _confirm(context, id, WazzaDecision.verify),
              child: const Text('Verificar nos registros oficiais')),
        ],
      ),
    ));
  }
}

class _DecisionForm extends StatefulWidget {
  const _DecisionForm({required this.decision});
  final WazzaDecision decision;

  @override
  State<_DecisionForm> createState() => _DecisionFormState();
}

class _DecisionFormState extends State<_DecisionForm> {
  final _form = GlobalKey<FormState>();
  final _reason = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    child: SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: Form(
        key: _form,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(widget.decision.label, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            TextFormField(
              controller: _reason,
              minLines: 2,
              maxLines: 4,
              maxLength: 300,
              decoration: const InputDecoration(labelText: 'Motivo', border: OutlineInputBorder()),
              validator: (text) => (text?.trim().length ?? 0) < 5 ? 'Informe pelo menos 5 caracteres.' : null,
            ),
            FilledButton(
              onPressed: () {
                if (_form.currentState!.validate()) Navigator.pop(context, _reason.text.trim());
              },
              child: Text(widget.decision.label),
            ),
          ],
        ),
      ),
    ),
  );
}

class WhatsAppActivityView extends StatelessWidget {
  const WhatsAppActivityView({super.key, required this.logs, required this.refresh});

  final List<Map<String, dynamic>>? logs;
  final Future<void> Function() refresh;

  @override
  Widget build(BuildContext context) => RefreshIndicator(
    onRefresh: refresh,
    child: ListView(
      physics: const AlwaysScrollableScrollPhysics(),
      padding: const EdgeInsets.all(16),
      children: [
        Text('WhatsApp', style: Theme.of(context).textTheme.headlineSmall),
        const Text('Acompanhe o envio e recebimento de mensagens da loja.', style: TextStyle(color: _muted)),
        const SizedBox(height: 14),
        Text('Mensagens recentes', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 10),
        if (logs?.isEmpty == true)
          const Card(child: ListTile(title: Text('Nenhuma mensagem registrada.'))),
        for (final log in logs ?? const <Map<String, dynamic>>[])
          Card(child: ListTile(
            leading: const Icon(Icons.chat_bubble_outline, color: _brand),
            title: Text(switch (log['direction']) {
              'in' || 'inbound' => 'Recebimento', 'out' || 'outbound' => 'Envio', _ => 'Mensagem',
            }),
            subtitle: Text(_when(log['created_at'])),
            trailing: Text(switch (log['status']) {
              'sent' => 'Enviada', 'delivered' => 'Entregue', 'read' => 'Lida',
              'failed' => 'Falhou', 'received' => 'Recebida', 'pending' => 'Pendente',
              _ => '${log['status'] ?? '—'}',
            }),
          )),
      ],
    ),
  );
}
