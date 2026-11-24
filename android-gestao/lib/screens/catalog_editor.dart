import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

typedef CatalogPhoto = ({Uint8List bytes, String filename});
typedef CatalogDraft = ({
  String name,
  int priceCents,
  String description,
  int? categoryId,
  CatalogPhoto? photo,
});

const catalogPhotoLimit = 5 * 1024 * 1024;

int? parseCatalogPrice(String input) {
  final value = input.trim().replaceAll(',', '.');
  if (!RegExp(r'^\d{1,7}(?:\.\d{1,2})?$').hasMatch(value)) return null;
  final parts = value.split('.');
  final cents = int.parse(parts.first) * 100 +
      (parts.length == 2 ? int.parse(parts.last.padRight(2, '0')) : 0);
  return cents > 0 ? cents : null;
}

String? catalogPhotoExtension(Uint8List bytes) {
  if (bytes.length >= 3 && bytes[0] == 0xff && bytes[1] == 0xd8 && bytes[2] == 0xff) {
    return 'jpg';
  }
  if (bytes.length >= 8 && bytes[0] == 0x89 &&
      String.fromCharCodes(bytes.sublist(1, 4)) == 'PNG' &&
      bytes[4] == 13 && bytes[5] == 10 && bytes[6] == 26 && bytes[7] == 10) {
    return 'png';
  }
  if (bytes.length >= 12 && String.fromCharCodes(bytes.sublist(0, 4)) == 'RIFF' &&
      String.fromCharCodes(bytes.sublist(8, 12)) == 'WEBP') {
    return 'webp';
  }
  return null;
}

class CatalogEditor extends StatefulWidget {
  const CatalogEditor({
    super.key, this.categories = const [], this.saveCategory, this.saveProduct,
  }) : assert((saveCategory == null) != (saveProduct == null));

  final List<Map<String, dynamic>> categories;
  final Future<bool> Function(String)? saveCategory;
  final Future<bool> Function(CatalogDraft)? saveProduct;

  @override
  State<CatalogEditor> createState() => _CatalogEditorState();
}

class _CatalogEditorState extends State<CatalogEditor> {
  final _form = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _price = TextEditingController();
  final _description = TextEditingController();
  final _picker = ImagePicker();
  int? _category;
  CatalogPhoto? _photo;
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _price.dispose();
    _description.dispose();
    super.dispose();
  }

  Future<void> _pick(ImageSource source) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final file = await _picker.pickImage(
        source: source,
        maxWidth: source == ImageSource.camera ? 2400 : null,
        imageQuality: source == ImageSource.camera ? 92 : null,
        requestFullMetadata: false,
      );
      if (file == null || !mounted) return;
      if (await file.length() > catalogPhotoLimit) {
        if (mounted) setState(() => _error = 'Escolha uma foto de até 5 MB.');
        return;
      }
      final bytes = await file.readAsBytes();
      if (!mounted) return;
      final extension = catalogPhotoExtension(bytes);
      if (extension == null) {
        setState(() => _error = 'Use uma imagem JPEG, PNG ou WebP.');
        return;
      }
      setState(() => _photo = (bytes: bytes, filename: 'produto.$extension'));
    } catch (_) {
      if (mounted) setState(() => _error = 'Não foi possível abrir a foto. Tente novamente.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    if (_busy || !_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final saveCategory = widget.saveCategory;
    try {
      final saved = saveCategory != null
          ? await saveCategory(_name.text.trim())
          : await widget.saveProduct!((
              name: _name.text.trim(),
              priceCents: parseCatalogPrice(_price.text)!,
              description: _description.text.trim(),
              categoryId: _category,
              photo: _photo,
            ));
      if (!mounted) return;
      if (saved) {
        Navigator.pop(context);
      } else {
        setState(() => _error = 'Não foi possível salvar. Confira a sessão e tente novamente.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final product = widget.saveProduct != null;
    final photo = _photo;
    final outline = OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: const BorderSide(color: Color(0xffe2e8f0)),
    );
    InputDecoration input(String label, {String? hint, String? prefix}) => InputDecoration(
      labelText: label,
      hintText: hint,
      prefixText: prefix,
      filled: true,
      fillColor: const Color(0xfff8fafc),
      enabledBorder: outline,
      border: outline,
    );
    return SafeArea(
      top: false,
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: Form(
          key: _form,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(children: [
                Expanded(child: Text(product ? 'Novo produto' : 'Nova categoria',
                  style: Theme.of(context).textTheme.titleLarge)),
                IconButton(onPressed: _busy ? null : () => Navigator.pop(context),
                  icon: const Icon(Icons.close), tooltip: 'Fechar'),
              ]),
              Text(
                product ? 'Cadastre um item para vender no cardápio.' : 'Agrupe produtos que fazem parte da mesma seção.',
                style: const TextStyle(color: Color(0xff64748b), fontSize: 13),
              ),
              const SizedBox(height: 16),
              if (product) ...[
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xfffff1f2),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text('Foto do produto', style: TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      if (photo != null)
                        ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: Image.memory(
                            photo.bytes, height: 140, fit: BoxFit.cover, cacheWidth: 480,
                            errorBuilder: (_, _, _) => const Text('Prévia da foto indisponível.'),
                          ),
                        ),
                      const Text('Opcional · até 5 MB', style: TextStyle(fontSize: 12, color: Color(0xff64748b))),
                      Wrap(spacing: 8, runSpacing: 4, children: [
                        OutlinedButton.icon(
                          onPressed: _busy ? null : () => _pick(ImageSource.camera),
                          icon: const Icon(Icons.photo_camera_outlined),
                          label: const Text('Tirar foto'),
                        ),
                        OutlinedButton.icon(
                          onPressed: _busy ? null : () => _pick(ImageSource.gallery),
                          icon: const Icon(Icons.photo_library_outlined),
                          label: const Text('Galeria'),
                        ),
                        if (photo != null)
                          TextButton(onPressed: _busy ? null : () => setState(() => _photo = null), child: const Text('Remover foto')),
                      ]),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
              ],
              TextFormField(
                controller: _name,
                enabled: !_busy,
                decoration: input(product ? 'Nome do produto' : 'Nome da categoria', hint: product ? 'Ex.: Burger da casa' : 'Ex.: Hambúrgueres'),
                validator: (value) => (value?.trim().isEmpty ?? true) ? 'Informe o nome.' : null,
              ),
              if (product) ...[
                const SizedBox(height: 12),
                TextFormField(
                  controller: _price,
                  enabled: !_busy,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: input('Preço de venda', hint: '0,00', prefix: 'R\$ '),
                  validator: (value) => parseCatalogPrice(value ?? '') == null ? 'Informe um preço válido.' : null,
                ),
                const SizedBox(height: 12),
                DropdownButtonFormField<int?>(
                  initialValue: null,
                  isExpanded: true,
                  decoration: input('Categoria'),
                  items: [
                    const DropdownMenuItem(value: null, child: Text('Sem categoria')),
                    for (final row in widget.categories)
                      if (row['id'] case final int id)
                        DropdownMenuItem(value: id, child: Text('${row['name']}', overflow: TextOverflow.ellipsis)),
                  ],
                  onChanged: _busy ? null : (value) => setState(() => _category = value),
                ),
                const SizedBox(height: 12),
                TextFormField(
                  controller: _description,
                  enabled: !_busy,
                  maxLines: 3,
                  decoration: input('Descrição (opcional)', hint: 'Conte o que vem no produto'),
                ),
              ],
              if (_error case final message?)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(message, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _busy ? null : _save,
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(50)),
                child: Text(_busy ? 'Aguarde…' : product ? 'Cadastrar produto' : 'Criar categoria'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
