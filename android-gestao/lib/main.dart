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
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xffdc2626)).copyWith(
        primary: const Color(0xffdc2626),
        surface: Colors.white,
        onSurface: const Color(0xff0f172a),
        secondaryContainer: const Color(0xfffff1f2),
        onSecondaryContainer: const Color(0xffb91c1c),
      ),
      scaffoldBackgroundColor: const Color(0xfff8fafc),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: const EdgeInsets.only(bottom: 10),
        shape: RoundedRectangleBorder(
          side: const BorderSide(color: Color(0xffe2e8f0)),
          borderRadius: BorderRadius.circular(16),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
        ),
      ),
    ),
    home: ManagementScreen(api: ManagementApi(Uri.parse(apiUrl))),
  ));
}
