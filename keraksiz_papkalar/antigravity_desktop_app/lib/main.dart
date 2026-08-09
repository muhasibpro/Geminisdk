import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'views/main_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AntigravityRealDesktopApp());
}

class AntigravityRealDesktopApp extends StatelessWidget {
  const AntigravityRealDesktopApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Antigravity Real Localhost Client',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const MainScreen(),
    );
  }
}
