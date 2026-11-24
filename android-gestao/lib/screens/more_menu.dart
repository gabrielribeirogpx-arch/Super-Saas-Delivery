import 'package:flutter/material.dart';

class MoreMenu extends StatelessWidget {
  const MoreMenu({super.key, required this.entries, required this.open});

  final List<(int, IconData, String)> entries;
  final ValueChanged<int> open;

  static Future<int?> show(BuildContext context, List<(int, IconData, String)> entries) =>
      showModalBottomSheet<int>(
        context: context,
        backgroundColor: Colors.white,
        showDragHandle: true,
        useSafeArea: true,
        scrollControlDisabledMaxHeightRatio: .82,
        builder: (sheetContext) => MoreMenu(
          entries: entries,
          open: (index) => Navigator.pop(sheetContext, index),
        ),
      );

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    child: ListView.builder(
      primary: false,
      shrinkWrap: true,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
      itemCount: entries.length + 1,
      itemBuilder: (context, position) {
        if (position == 0) {
          return Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Text('Gestão', style: Theme.of(context).textTheme.titleLarge),
          );
        }
        final (index, icon, label) = entries[position - 1];
        const border = BorderSide(color: Color(0xffe2e8f0));
        final first = position == 1;
        final last = position == entries.length;
        return DecoratedBox(
          decoration: ShapeDecoration(
            shape: RoundedRectangleBorder(
              side: border,
              borderRadius: BorderRadius.vertical(
                top: first ? const Radius.circular(16) : Radius.zero,
                bottom: last ? const Radius.circular(16) : Radius.zero,
              ),
            ),
          ),
          child: ListTile(
            leading: Icon(icon, color: const Color(0xffb91c1c)),
            title: Text(label),
            trailing: const Icon(Icons.chevron_right),
            onTap: () => open(index),
          ),
        );
      },
    ),
  );
}
