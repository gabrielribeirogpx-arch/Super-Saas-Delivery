import 'package:flutter/material.dart';

enum MarketingSection {
  loyalty('Fidelidade', Icons.stars_outlined),
  coupons('Cupons', Icons.local_offer_outlined),
  rewards('Recompensas', Icons.card_giftcard_outlined);

  const MarketingSection(this.label, this.icon);
  final String label;
  final IconData icon;

  String get heading => switch (this) {
    MarketingSection.loyalty => 'Regras de pontuação',
    MarketingSection.coupons => 'Cupons criados',
    MarketingSection.rewards => 'Recompensas disponíveis',
  };

  String get action => switch (this) {
    MarketingSection.loyalty => 'Editar regras',
    MarketingSection.coupons => 'Criar cupom',
    MarketingSection.rewards => 'Criar recompensa',
  };
}

class MarketingView extends StatelessWidget {
  const MarketingView({
    super.key, required this.section, required this.entries, required this.busy,
    required this.canEdit, required this.refresh, required this.save,
  });

  final MarketingSection section;
  final List<Map<String, dynamic>>? entries;
  final bool busy;
  final bool canEdit;
  final Future<void> Function() refresh;
  final ValueChanged<Map<String, Object?>> save;

  Future<void> _edit(BuildContext context, Map<String, dynamic>? current) async {
    final payload = await showModalBottomSheet<Map<String, Object?>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      showDragHandle: true,
      backgroundColor: Colors.white,
      builder: (context) => _MarketingForm(section: section, current: current),
    );
    if (context.mounted && payload != null) save(payload);
  }

  @override
  Widget build(BuildContext context) {
    final rows = entries;
    final current = rows != null && rows.isNotEmpty ? rows.first : null;
    return RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [
          Text('Marketing', style: Theme.of(context).textTheme.labelLarge?.copyWith(
            color: const Color(0xffb91c1c), fontWeight: FontWeight.w700,
          )),
          Text(section.label, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
          const SizedBox(height: 14),
          Card(
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: const Color(0xfffff1f2),
                foregroundColor: const Color(0xffb91c1c),
                child: Icon(section.icon),
              ),
              title: Text(section.heading, style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: rows == null || section == MarketingSection.loyalty
                  ? null : Text('${rows.length} ${rows.length == 1 ? 'opção' : 'opções'}'),
            ),
          ),
          if (canEdit && rows != null) ...[
            FilledButton.icon(
              onPressed: busy ? null : () => _edit(context, current),
              icon: Icon(section == MarketingSection.loyalty ? Icons.edit_outlined : Icons.add),
              label: Text(section.action),
            ),
            const SizedBox(height: 10),
          ],
          if (rows?.isEmpty == true)
            const Card(child: ListTile(title: Text('Nenhum benefício cadastrado.'))),
          for (final entry in rows ?? const <Map<String, dynamic>>[])
            Card(child: _entry(entry)),
        ],
      ),
    );
  }

  String _currency(Object? amount) {
    final number = amount is num ? amount : num.tryParse('$amount');
    return number == null ? '—' : 'R\$ ${number.toStringAsFixed(2).replaceAll('.', ',')}';
  }

  Widget _entry(Map<String, dynamic> entry) => switch (section) {
    MarketingSection.loyalty => ListTile(
      title: Text(entry['points_enabled'] == true ? 'Pontos ativados' : 'Pontos desativados'),
      subtitle: Text('${_currency(entry['reais_por_ponto'])} por ponto · '
        '${entry['points_expiration_days'] == null ? 'Sem expiração' : "Expira em ${entry['points_expiration_days']} dias"}'),
    ),
    MarketingSection.coupons => ListTile(
      title: Text('${entry['code']}', style: const TextStyle(
        color: Color(0xffb91c1c), fontWeight: FontWeight.w800, letterSpacing: .4,
      )),
      subtitle: Text('${entry['active'] == true ? 'Ativo' : 'Inativo'} · ${entry['uses_count'] ?? 0} usos'),
      trailing: Text(
        entry['discount_type'] == 'percentage'
            ? '${entry['discount_value']}% OFF' : _currency(entry['discount_value']),
        style: const TextStyle(fontWeight: FontWeight.w700),
      ),
    ),
    MarketingSection.rewards => ListTile(
      title: Text('${entry['points_required']} pontos'),
      subtitle: const Text('Desconto'),
      trailing: Text(_currency(entry['discount_value']), style: const TextStyle(fontWeight: FontWeight.w700)),
    ),
  };
}

class _MarketingForm extends StatefulWidget {
  const _MarketingForm({required this.section, required this.current});
  final MarketingSection section;
  final Map<String, dynamic>? current;

  @override
  State<_MarketingForm> createState() => _MarketingFormState();
}

class _MarketingFormState extends State<_MarketingForm> {
  final _key = GlobalKey<FormState>();
  late final _first = TextEditingController(text: switch (widget.section) {
    MarketingSection.loyalty => '${widget.current?['reais_por_ponto'] ?? ''}'.replaceAll('.', ','),
    MarketingSection.rewards => '100',
    MarketingSection.coupons => '',
  });
  late final _second = TextEditingController(text: widget.section == MarketingSection.loyalty
      ? '${widget.current?['points_expiration_days'] ?? ''}' : '10');
  late bool _enabled = widget.current?['points_enabled'] == true;
  String _discount = 'percentage';

  @override
  void dispose() {
    _first.dispose();
    _second.dispose();
    super.dispose();
  }

  double? _decimal(String input) => double.tryParse(input.trim().replaceAll(',', '.'));

  Widget _number(TextEditingController controller, String label, {
    bool integer = false, bool optional = false, double? max,
  }) => TextFormField(
    controller: controller,
    keyboardType: TextInputType.numberWithOptions(decimal: !integer),
    decoration: InputDecoration(labelText: label, border: const OutlineInputBorder()),
    validator: (input) {
      final text = input?.trim() ?? '';
      if (text.isEmpty && optional) return null;
      final value = integer ? int.tryParse(text) : _decimal(text);
      if (value == null || !value.isFinite || value <= 0) return 'Informe um valor maior que zero.';
      if (max != null && value > max) return 'Informe um valor de até ${max.toInt()}.';
      return null;
    },
  );

  void _submit() {
    if (!_key.currentState!.validate()) return;
    final Map<String, Object?> payload = switch (widget.section) {
      MarketingSection.loyalty => {
        'points_enabled': _enabled,
        'reais_por_ponto': _decimal(_first.text),
        'points_expiration_days': int.tryParse(_second.text.trim()),
      },
      MarketingSection.coupons => {
        'code': _first.text.trim().toUpperCase(),
        'discount_type': _discount,
        'discount_value': _decimal(_second.text),
      },
      MarketingSection.rewards => {
        'points_required': int.tryParse(_first.text.trim()),
        'discount_value': _decimal(_second.text),
      },
    };
    Navigator.pop(context, payload);
  }

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    child: SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: Form(
        key: _key,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(widget.section.action, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            if (widget.section == MarketingSection.loyalty) ...[
              SwitchListTile(contentPadding: EdgeInsets.zero, title: const Text('Ativar programa de pontos'),
                value: _enabled, onChanged: (value) => setState(() => _enabled = value)),
              _number(_first, 'Reais por ponto'),
              const SizedBox(height: 12),
              _number(_second, 'Dias para expirar (opcional)', integer: true, optional: true),
            ] else if (widget.section == MarketingSection.coupons) ...[
              TextFormField(
                controller: _first,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(labelText: 'Código do cupom', border: OutlineInputBorder()),
                validator: (value) => value == null || value.trim().isEmpty ? 'Informe o código.' : null,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _discount,
                decoration: const InputDecoration(labelText: 'Tipo de desconto', border: OutlineInputBorder()),
                items: const [
                  DropdownMenuItem(value: 'percentage', child: Text('Porcentagem (%)')),
                  DropdownMenuItem(value: 'fixed', child: Text('Valor fixo (R\$)')),
                ],
                onChanged: (value) => setState(() => _discount = value ?? 'percentage'),
              ),
              const SizedBox(height: 12),
              _number(_second, 'Valor do desconto', max: _discount == 'percentage' ? 100 : null),
            ] else ...[
              _number(_first, 'Pontos necessários', integer: true),
              const SizedBox(height: 12),
              _number(_second, 'Valor do desconto em reais'),
            ],
            const SizedBox(height: 16),
            FilledButton(onPressed: _submit, child: Text(widget.section == MarketingSection.loyalty ? 'Salvar regras' : widget.section.action)),
          ],
        ),
      ),
    ),
  );
}
