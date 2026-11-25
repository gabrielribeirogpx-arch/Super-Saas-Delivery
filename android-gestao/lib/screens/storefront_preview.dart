import 'package:flutter/material.dart';

import 'operations_views.dart' show resolveCatalogImage;

Color storefrontColor(Object? value, Color fallback) {
  final text = value is String ? value.trim() : '';
  if (!RegExp(r'^#[a-fA-F0-9]{6}$').hasMatch(text)) return fallback;
  return Color(0xff000000 | int.parse(text.substring(1), radix: 16));
}

List<Map<String, dynamic>> _rows(Object? value) =>
    value is List ? value.whereType<Map<String, dynamic>>().toList() : [];

String _price(Object? cents) => cents is num
    ? 'R\$ ${(cents / 100).toStringAsFixed(2).replaceAll('.', ',')}'
    : '—';

class StorefrontPreview extends StatefulWidget {
  const StorefrontPreview({
    super.key,
    required this.data,
    required this.origin,
    required this.busy,
    required this.refresh,
    required this.edit,
  });

  final Map<String, dynamic>? data;
  final Uri origin;
  final bool busy;
  final Future<void> Function() refresh;
  final VoidCallback? edit;

  @override
  State<StorefrontPreview> createState() => _StorefrontPreviewState();
}

class _StorefrontPreviewState extends State<StorefrontPreview> {
  Object? _category;
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final data = widget.data;
    final store = data?['tenant'] as Map?;
    final settings = data?['public_settings'] as Map?;
    final primary = storefrontColor(
      settings?['primary_color'],
      const Color(0xffdc2626),
    );
    final secondary = storefrontColor(
      settings?['secondary_color'],
      const Color(0xff111827),
    );
    final dark = settings?['theme'] == 'dark';
    final surface = dark ? const Color(0xff172033) : Colors.white;
    final ink = dark ? Colors.white : const Color(0xff0f172a);
    final muted = dark ? const Color(0xffcbd5e1) : const Color(0xff64748b);
    final variant = settings?['layout_variant'];
    final radius = variant == 'commercial'
        ? 24.0
        : variant == 'modern'
        ? 18.0
        : 14.0;
    final photoSize = variant == 'commercial'
        ? 100.0
        : variant == 'modern'
        ? 88.0
        : 78.0;
    final buttonRadius = ((settings?['button_radius'] as num?) ?? 12)
        .clamp(0, 32)
        .toDouble();
    final sections = _rows(data?['categories']);
    final other = _rows(data?['items_without_category']);
    if (other.isNotEmpty)
      sections.add({'id': -1, 'name': 'Nosso cardápio', 'items': other});
    final categories = [
      for (final section in sections)
        (
          id: section['id'],
          name: '${section['name']}',
          items: _rows(section['items'])
              .where(
                (item) =>
                    item['is_active'] != false && item['isAvailable'] != false,
              )
              .toList(),
        ),
    ];
    final visible = [
      for (final category in categories)
        if (_category == null || _category == category.id)
          (
            name: category.name,
            items: category.items
                .where(
                  (item) => '${item['name']} ${item['description'] ?? ''}'
                      .toLowerCase()
                      .contains(_query),
                )
                .toList(),
          ),
    ];
    final highlights = categories.expand((category) => category.items).toList()
      ..sort((a, b) {
        int score(Map<String, dynamic> item) => item['featured'] == true
            ? 100000
            : (item['orderCount'] as num?)?.toInt() ?? 0;
        return score(b).compareTo(score(a));
      });
    final storeName = '${store?['name'] ?? data?['slug'] ?? 'Loja'}';

    final header = <Widget>[
      Wrap(
        crossAxisAlignment: WrapCrossAlignment.center,
        alignment: WrapAlignment.spaceBetween,
        spacing: 8,
        children: [
          Text(
            'Prévia do Cardápio',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: ink,
            ),
          ),
          OutlinedButton.icon(
            onPressed: widget.busy ? null : widget.edit,
            icon: const Icon(Icons.palette_outlined, size: 17),
            label: const Text('Editar aparência'),
            style: OutlinedButton.styleFrom(foregroundColor: ink),
          ),
        ],
      ),
      if (data != null) ...[
        const SizedBox(height: 12),
        ClipRRect(
          borderRadius: BorderRadius.circular(radius),
          child: SizedBox(
            height: 172,
            child: Stack(
              fit: StackFit.expand,
              children: [
                ColoredBox(color: secondary),
                _StorefrontImage(
                  origin: widget.origin,
                  url: settings?['cover_image_url'],
                ),
                const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Colors.transparent, Color(0xdd000000)],
                    ),
                  ),
                ),
                Positioned(
                  left: 12,
                  right: 12,
                  bottom: 12,
                  child: Row(
                    children: [
                      ClipRRect(
                        borderRadius: BorderRadius.circular(12),
                        child: SizedBox(
                          width: 52,
                          height: 52,
                          child: ColoredBox(
                            color: surface,
                            child: _StorefrontImage(
                              origin: widget.origin,
                              url: settings?['logo_url'],
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              storeName,
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 22,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            Text(
                              '${(store?['is_open'] ?? store?['manual_open_status'] ?? true) == true ? 'Aberto agora' : 'Fechado'}'
                              ' · ${store?['estimated_prep_time'] ?? '25–40 min'}',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 12,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            _info(
              'Entrega',
              '${store?['estimated_prep_time'] ?? '25–40 min'}',
              surface,
              ink,
              muted,
            ),
            _info(
              'Taxa',
              _price(((store?['delivery_fee'] as num?) ?? 0) * 100),
              surface,
              ink,
              muted,
            ),
            _info('Pagamento', 'Pix, Cartão', surface, ink, muted),
          ],
        ),
        const SizedBox(height: 10),
        TextField(
          style: TextStyle(color: ink),
          onChanged: (value) => setState(() {
            _query = value.trim().toLowerCase();
            _category = null;
          }),
          decoration: InputDecoration(
            hintText: 'O que você quer pedir hoje?',
            hintStyle: TextStyle(color: muted),
            prefixIcon: Icon(Icons.search, color: muted),
            filled: true,
            fillColor: surface,
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
          ),
        ),
        if (_category == null && _query.isEmpty && highlights.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text(
            'Destaques',
            style: TextStyle(
              color: ink,
              fontWeight: FontWeight.w800,
              fontSize: 18,
            ),
          ),
          const SizedBox(height: 8),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final item in highlights.take(5))
                  Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: SizedBox(
                      width: 118,
                      child: Card(
                        color: surface,
                        clipBehavior: Clip.antiAlias,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            SizedBox(
                              height: 76,
                              child: _StorefrontImage(
                                origin: widget.origin,
                                url: item['image_url'],
                              ),
                            ),
                            Padding(
                              padding: const EdgeInsets.all(8),
                              child: Text(
                                '${item['name']}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  color: ink,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ],
        if (categories.isNotEmpty)
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _chip('Todos', null, primary, surface, ink),
                for (final category in categories)
                  _chip(category.name, category.id, primary, surface, ink),
              ],
            ),
          ),
      ],
    ];

    final rows = <({String? title, Map<String, dynamic>? item})>[
      for (final group in visible)
        if (group.items.isNotEmpty) ...[
          (title: group.name, item: null),
          for (final item in group.items) (title: null, item: item),
        ],
    ];

    return ColoredBox(
      color: dark ? secondary : const Color(0xfff8fafc),
      child: RefreshIndicator(
        onRefresh: widget.refresh,
        child: ListView.builder(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          itemCount:
              header.length +
              rows.length +
              (data != null && rows.isEmpty ? 1 : 0),
          itemBuilder: (context, index) {
            if (index < header.length) return header[index];
            if (rows.isEmpty) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  'Nenhum produto para exibir.',
                  style: TextStyle(color: muted),
                ),
              );
            }
            final row = rows[index - header.length];
            final item = row.item;
            if (item == null) {
              return Padding(
                padding: const EdgeInsets.only(top: 12, bottom: 8),
                child: Text(
                  row.title!,
                  style: TextStyle(
                    color: ink,
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              );
            }
            return Card(
              color: surface,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(radius),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${item['name']}',
                            style: TextStyle(
                              color: ink,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          if (item['description'] case final String text
                              when text.isNotEmpty)
                            Text(
                              text,
                              style: TextStyle(color: muted, fontSize: 12),
                            ),
                          const SizedBox(height: 6),
                          Text(
                            _price(item['price_cents']),
                            style: TextStyle(
                              color: primary,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 10),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: SizedBox(
                        width: photoSize,
                        height: photoSize,
                        child: Stack(
                          fit: StackFit.expand,
                          children: [
                            ColoredBox(
                              color: dark ? secondary : const Color(0xfff1f5f9),
                            ),
                            _StorefrontImage(
                              origin: widget.origin,
                              url: item['image_url'],
                            ),
                            Positioned(
                              right: 4,
                              bottom: 4,
                              child: DecoratedBox(
                                decoration: BoxDecoration(
                                  color: primary,
                                  borderRadius: BorderRadius.circular(
                                    buttonRadius,
                                  ),
                                ),
                                child: const Padding(
                                  padding: EdgeInsets.all(4),
                                  child: Icon(
                                    Icons.add,
                                    size: 16,
                                    color: Colors.white,
                                  ),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _chip(
    String label,
    Object? id,
    Color primary,
    Color surface,
    Color ink,
  ) {
    final selected = _category == id;
    return Padding(
      padding: const EdgeInsets.only(right: 6),
      child: ChoiceChip(
        label: Text(
          label,
          style: TextStyle(color: selected ? Colors.white : ink),
        ),
        backgroundColor: surface,
        selectedColor: primary,
        showCheckmark: false,
        selected: selected,
        onSelected: (_) => setState(() => _category = id),
      ),
    );
  }

  Widget _info(
    String label,
    String value,
    Color surface,
    Color ink,
    Color muted,
  ) => DecoratedBox(
    decoration: BoxDecoration(
      color: surface,
      borderRadius: BorderRadius.circular(12),
    ),
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: TextStyle(color: muted, fontSize: 11)),
          Text(
            value,
            style: TextStyle(
              color: ink,
              fontSize: 12,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    ),
  );
}

class _StorefrontImage extends StatelessWidget {
  const _StorefrontImage({required this.origin, required this.url});

  final Uri origin;
  final Object? url;

  @override
  Widget build(BuildContext context) {
    const fallback = Center(
      child: Icon(Icons.restaurant_menu, color: Color(0xff94a3b8)),
    );
    final image = resolveCatalogImage(origin, url);
    if (image == null) return fallback;
    return LayoutBuilder(
      builder: (context, constraints) {
        final width =
            constraints.maxWidth * MediaQuery.devicePixelRatioOf(context);
        return Image.network(
          image.toString(),
          fit: BoxFit.cover,
          cacheWidth: width.isFinite && width >= 1 ? width.ceil() : null,
          errorBuilder: (_, _, _) => fallback,
        );
      },
    );
  }
}
