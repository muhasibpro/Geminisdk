import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class LiveTerminalView extends StatefulWidget {
  const LiveTerminalView({super.key});

  @override
  State<LiveTerminalView> createState() => _LiveTerminalViewState();
}

class _LiveTerminalViewState extends State<LiveTerminalView> {
  final ScrollController _scrollController = ScrollController();
  final List<String> _logs = [
    "[SYSTEM] Antigravity AI Engine v2.5 initialized on macOS darwin-arm64",
    "[MACOS BUILD] Checking Flutter SDK dependencies... [OK]",
    "[MACOS BUILD] Xcode Developer tools version 26.1.1 selected",
    "[VIDEO PIPELINE] python video/make_multik.py --fps 30 --w 1920 --h 1080",
    "[AUDIO SYNTHESIS] edge-tts --voice uz-UZ-SardorNeural --text 'MUHASIB POS' --write-media test.mp3",
    "[VISION SEGMENTATION] Vision framework layer extraction active for image_1.jpg",
    "[MACOS BUILD] Building macOS application in release mode...",
    "[FLUTTER] Compiling lib/main.dart for macOS darwin-arm64 (Metal GPU)...",
  ];

  final TextEditingController _cmdController = TextEditingController();
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    // Simulate periodic live log updates
    _timer = Timer.periodic(const Duration(seconds: 3), (timer) {
      if (mounted) {
        setState(() {
          _logs.add("[LOG ${DateTime.now().toIso8601String().substring(11, 19)}] Task executed cleanly with exit code 0.");
        });
        _scrollToBottom();
      }
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _executeCommand() {
    if (_cmdController.text.trim().isEmpty) return;
    String cmd = _cmdController.text.trim();
    setState(() {
      _logs.add("\$ $cmd");
      _cmdController.clear();
      
      if (cmd.contains("build")) {
        _logs.add("[BUILD] Executing: flutter build macos --release...");
        _logs.add("[BUILD] Generating App Bundle: build/macos/Build/Products/Release/muhasib_app.app");
      } else {
        _logs.add("[EXEC] Command '$cmd' executed successfully.");
      }
    });
    _scrollToBottom();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _scrollController.dispose();
    _cmdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "Real-Time Antigravity CLI & macOS Build Console",
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  SizedBox(height: 4),
                  Text(
                    "Zsh Terminal Shell execution, background tasks & Flutter compiler logs",
                    style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                  ),
                ],
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: AppTheme.accentGreen.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: AppTheme.accentGreen),
                ),
                child: const Row(
                  children: [
                    Icon(Icons.terminal, color: AppTheme.accentGreen, size: 16),
                    SizedBox(width: 8),
                    Text("SHELL ACTIVE", style: TextStyle(color: AppTheme.accentGreen, fontWeight: FontWeight.bold, fontSize: 12)),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 20),

          // Terminal Window
          GlassCard(
            backgroundColor: const Color(0xFF0A0C14),
            borderColor: AppTheme.glassBorder,
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Terminal Header Bar
                Row(
                  children: [
                    Container(width: 12, height: 12, decoration: const BoxDecoration(color: Color(0xFFFF5F56), shape: BoxShape.circle)),
                    const SizedBox(width: 8),
                    Container(width: 12, height: 12, decoration: const BoxDecoration(color: Color(0xFFFFBD2E), shape: BoxShape.circle)),
                    const SizedBox(width: 8),
                    Container(width: 12, height: 12, decoration: const BoxDecoration(color: Color(0xFF27C93F), shape: BoxShape.circle)),
                    const SizedBox(width: 16),
                    const Text("antigravity-cli — zsh — 120x40", style: TextStyle(color: AppTheme.textMuted, fontSize: 12, fontFamily: 'monospace')),
                  ],
                ),
                const SizedBox(height: 12),
                const Divider(color: AppTheme.glassBorder),
                const SizedBox(height: 10),

                // Terminal Output Area
                Container(
                  height: 340,
                  width: double.infinity,
                  child: ListView.builder(
                    controller: _scrollController,
                    itemCount: _logs.length,
                    itemBuilder: (context, index) {
                      final log = _logs[index];
                      Color logColor = AppTheme.textPrimary;
                      if (log.startsWith("\$")) logColor = AppTheme.accentCyan;
                      if (log.contains("BUILD") || log.contains("SYSTEM")) logColor = AppTheme.accentGreen;
                      if (log.contains("VIDEO") || log.contains("AUDIO")) logColor = AppTheme.accentYellow;

                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3.0),
                        child: Text(
                          log,
                          style: TextStyle(
                            color: logColor,
                            fontFamily: 'monospace',
                            fontSize: 13,
                          ),
                        ),
                      );
                    },
                  ),
                ),

                const SizedBox(height: 12),

                // Command Input Line
                Row(
                  children: [
                    const Text("\$ ", style: TextStyle(color: AppTheme.accentCyan, fontWeight: FontWeight.bold, fontSize: 16, fontFamily: 'monospace')),
                    Expanded(
                      child: TextField(
                        controller: _cmdController,
                        style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 14),
                        decoration: const InputDecoration(
                          hintText: "Buyruq kiriting (masalan: flutter build macos)...",
                          hintStyle: TextStyle(color: AppTheme.textMuted, fontSize: 13),
                          border: InputBorder.none,
                        ),
                        onSubmitted: (_) => _executeCommand(),
                      ),
                    ),
                    IconButton(
                      icon: const Icon(Icons.play_arrow, color: AppTheme.accentGreen),
                      onPressed: _executeCommand,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
