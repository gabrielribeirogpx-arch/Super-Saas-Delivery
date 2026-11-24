import 'package:flutter/material.dart';

class MoreMenu extends StatelessWidget {
  const MoreMenu({super.key, required this.entries, required this.open});

  final List<(int, IconData, String)> entries;
  final ValueChanged<int> open;

  @override
  Widget build(BuildContext context) => SafeArea(
    top: false,
    child: ListView(
      shrinkWrap: true,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
      children: [
        Text('Gestão', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 10),
        Card(
          child: Column(
            children: [
              for (final (index, icon, label) in entries)
                ListTile(
                  leading: Icon(icon, color: const Color(0xffb91c1c)),
                  title: Text(label),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => open(index),
                ),
            ],
          ),
        ),
      ],
    ),
  );
}
