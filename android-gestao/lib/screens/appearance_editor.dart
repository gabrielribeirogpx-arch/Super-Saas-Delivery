import 'package:flutter/material.dart';

import 'storefront_preview.dart' show storefrontColor;

class AppearanceEditor extends StatefulWidget {
  const AppearanceEditor({super.key, required this.current, required this.save});

  final Map<String, dynamic> current;
  final Future<bool> Function(Map<String, Object?>) save;

  @override
  State<AppearanceEditor> createState() => _AppearanceEditorState();
}

class _AppearanceEditorState extends State<AppearanceEditor> {
  final _form = GlobalKey<FormState>();
  late final _primary = TextEditingController(text: '${widget.current['primary_color'] ?? '#dc2626'}');
  late final _secondary = TextEditingController(text: '${widget.current['secondary_color'] ?? '#111827'}');
  late final _font = TextEditingController(text: '${widget.current['font_family'] ?? 'Inter'}');
  late double _radius = ((widget.current['button_radius'] as num?) ?? 12).clamp(0, 32).toDouble();
  late String _layout = switch (widget.current['layout_variant']) {
    'modern' => 'modern',
    'commercial' => 'commercial',
    _ => 'clean',
  };
  bool _busy = false;
  bool _failed = false;

  @override
  void dispose() {
    _primary.dispose();
    _secondary.dispose();
    _font.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (_busy || !_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _failed = false;
    });
    try {
      final saved = await widget.save({
        'primary_color': _primary.text.trim(),
        'secondary_color': _secondary.text.trim(),
        'font_family': _font.text.trim(),
        'layout_variant': _layout,
        'button_radius': _radius.round(),
        if (widget.current['hero_image_url'] case final String url) 'hero_image_url': url,
      });
      if (!mounted) return;
      if (saved) {
        Navigator.pop(context);
      } else {
        setState(() => _failed = true);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _color(TextEditingController controller, String label, Color fallback) => TextFormField(
    enabled: !_busy,
    controller: controller,
    textCapitalization: TextCapitalization.characters,
    autocorrect: false,
    onChanged: (_) => setState(() {}),
    decoration: InputDecoration(
      labelText: label, hintText: '#RRGGBB',
      border: const OutlineInputBorder(),
      prefixIcon: Padding(
        padding: const EdgeInsets.all(12),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: storefrontColor(controller.text, fallback),
            borderRadius: BorderRadius.circular(6),
          ),
        ),
      ),
    ),
    validator: (value) => RegExp(r'^#[a-fA-F0-9]{6}$').hasMatch(value?.trim() ?? '')
        ? null : 'Use o formato #RRGGBB.',
  );

  @override
  Widget build(BuildContext context) {
    final primary = storefrontColor(_primary.text, const Color(0xffdc2626));
    final secondary = storefrontColor(_secondary.text, const Color(0xff111827));
    return SafeArea(
      top: false,
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(16, 0, 16, 20 + MediaQuery.viewInsetsOf(context).bottom),
        child: Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(children: [
                Expanded(child: Text('Aparência do cardápio', style: Theme.of(context).textTheme.titleLarge)),
                IconButton(onPressed: _busy ? null : () => Navigator.pop(context),
                  icon: const Icon(Icons.close), tooltip: 'Fechar'),
              ]),
              const Text('As alterações aparecem no cardápio público ao publicar.'),
              const SizedBox(height: 14),
              DecoratedBox(
                decoration: BoxDecoration(color: secondary, borderRadius: BorderRadius.circular(16)),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: DecoratedBox(
                      decoration: BoxDecoration(color: primary, borderRadius: BorderRadius.circular(_radius)),
                      child: const Padding(padding: EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                        child: Text('Botão de exemplo', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700))),
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              _color(_primary, 'Cor primária', const Color(0xffdc2626)),
              const SizedBox(height: 6),
              Wrap(
                spacing: 8,
                children: [
                  for (final (name, hex) in const [
                    ('Vermelho', '#DC2626'), ('Verde', '#15803D'),
                    ('Azul', '#2563EB'), ('Âmbar', '#B45309'),
                    ('Roxo', '#7E22CE'),
                  ])
                    IconButton(
                      tooltip: name,
                      onPressed: _busy ? null : () => setState(() => _primary.text = hex),
                      icon: CircleAvatar(
                        radius: 12,
                        backgroundColor: storefrontColor(hex, primary),
                        foregroundColor: Colors.white,
                        child: _primary.text.toUpperCase() == hex ? const Icon(Icons.check, size: 15) : null,
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 12),
              _color(_secondary, 'Cor secundária', const Color(0xff111827)),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                initialValue: _layout,
                decoration: const InputDecoration(labelText: 'Layout', border: OutlineInputBorder()),
                items: const [
                  DropdownMenuItem(value: 'clean', child: Text('Clean')),
                  DropdownMenuItem(value: 'modern', child: Text('Modern')),
                  DropdownMenuItem(value: 'commercial', child: Text('Commercial')),
                ],
                onChanged: _busy ? null : (value) {
                  if (value != null) setState(() => _layout = value);
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                enabled: !_busy, controller: _font, maxLength: 80,
                decoration: const InputDecoration(labelText: 'Fonte', hintText: 'Ex.: Inter', border: OutlineInputBorder()),
                validator: (value) => (value?.trim().isEmpty ?? true) ? 'Informe o nome da fonte.' : null,
              ),
              Text('Cantos dos botões · ${_radius.round()} px'),
              Slider(
                value: _radius, min: 0, max: 32, divisions: 32,
                onChanged: _busy ? null : (value) => setState(() => _radius = value),
              ),
              if (_failed)
                Text('Não foi possível publicar. Confira a sessão e tente novamente.',
                  style: TextStyle(color: Theme.of(context).colorScheme.error)),
              FilledButton(onPressed: _busy ? null : _save,
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                child: Text(_busy ? 'Publicando…' : 'Publicar aparência')),
            ],
          ),
        ),
      ),
    );
  }
}
