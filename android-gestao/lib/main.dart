import 'package:flutter/material.dart';

import 'screens/management_screen.dart';
import 'services/management_api.dart';

void main() {
  const apiUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://api.fomizero.com.br',
  );
  runApp(MaterialApp(
    title: 'Fomizero Gestão',
    theme: ThemeData(colorSchemeSeed: const Color(0xffdc2626)),
    home: ManagementScreen(api: ManagementApi(Uri.parse(apiUrl))),
  ));
}
