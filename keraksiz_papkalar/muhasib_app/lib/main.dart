import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'views/main_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MuhasibAntigravityApp());
}

class MuhasibAntigravityApp extends StatelessWidget {
  const MuhasibAntigravityApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MUHASIB Antigravity AI Studio',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      home: const MainScreen(),
    );
  }
}
