import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../widgets/chat_bubble.dart';

class AntigravityGuiView extends StatefulWidget {
  const AntigravityGuiView({super.key});

  @override
  State<AntigravityGuiView> createState() => _AntigravityGuiViewState();
}

class _AntigravityGuiViewState extends State<AntigravityGuiView> {
  final TextEditingController _promptController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  
  bool _showSidecar = true;
  String _selectedModel = 'Gemini 3.6 Flash (High)';
  bool _isListeningVoice = false;

  final List<ChatMessageModel> _messages = [
    ChatMessageModel(
      id: '1',
      sender: 'antigravity',
      text: "Salom! Men Antigravity AI agentiman (http://localhost:8777). Google DeepMind model platformasi asosida ishlayman. Sening loyihangdagi POS kassa, video render va Uzbek neural ovoz quvurlari bilan integratsiya qilinganman. Menga istalgan vazifani bering!",
      thought: "Loyiha `AGENTS.md` qoidalariga rioya qilinadi. macOS Vision layer cutout hamda vector multik rendering tayyor.",
      toolCalls: [
        {'name': 'view_file', 'args': 'AGENTS.md'},
        {'name': 'list_dir', 'args': '/Users/muhasibpro/Desktop/Geminisdk'},
      ],
      timestamp: DateTime.now().subtract(const Duration(minutes: 10)),
    ),
    ChatMessageModel(
      id: '2',
      sender: 'user',
      text: "Flutter dastur yasa, unda o'zingni yasal ber, hobi va qanday ishlasang xuddi shunday bo'lsin. Birinchi macOS ga yasab build qil!",
      timestamp: DateTime.now().subtract(const Duration(minutes: 8)),
    ),
    ChatMessageModel(
      id: '3',
      sender: 'antigravity',
      text: "Tushundim! `muhasib_app` loyihasi Flutter 3.35.7 frameworkida macOS Apple Silicon uchun yaratildi hamda `flutter build macos` orqali native release binar tayyorlandi! Pastda render qilingan video va binar bormoqda.",
      thought: "macOS Metal grafik tezlashi ishlatildi. 39.2 MB hajmdagi binar yaratildi.",
      toolCalls: [
        {'name': 'run_command', 'args': 'flutter build macos'},
        {'name': 'manage_task', 'args': 'status task-53'},
      ],
      mediaPath: 'build/macos/Build/Products/Release/muhasib_app.app',
      mediaType: 'video',
      timestamp: DateTime.now().subtract(const Duration(minutes: 2)),
    ),
  ];

  final List<String> _mediaFiles = [
    'anim1.mp4',
    'anim2.mp4',
    'muhasib_energetik_multik.mp4',
    'muhasib_cartoon_video.html',
    'tovarlar.xlsx',
    'a1.m4a',
    'make_multik.py',
    'render_anim.py',
  ];

  void _sendMessage() {
    if (_promptController.text.trim().isEmpty) return;
    String userText = _promptController.text.trim();
    
    setState(() {
      _messages.add(
        ChatMessageModel(
          id: DateTime.now().millisecondsSinceEpoch.toString(),
          sender: 'user',
          text: userText,
          timestamp: DateTime.now(),
        ),
      );
      _promptController.clear();

      // Simulated Antigravity AI response stream
      Future.delayed(const Duration(milliseconds: 700), () {
        if (mounted) {
          setState(() {
            _messages.add(
              ChatMessageModel(
                id: (DateTime.now().millisecondsSinceEpoch + 1).toString(),
                sender: 'antigravity',
                text: "Topshiriq qabul qilindi: '$userText'. Antigravity AI PTY va agentic executor ishga tushdi!",
                thought: "zsh shell va subagent orchestrator bilan sinxronizatsiya qilindi.",
                toolCalls: [
                  {'name': 'run_command', 'args': userText},
                ],
                timestamp: DateTime.now(),
              ),
            );
          });
          _scrollToBottom();
        }
      });
    });
    _scrollToBottom();
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

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Top Toolbar (http://localhost:8777 GUI Header)
        Container(
          height: 56,
          decoration: const BoxDecoration(
            color: AppTheme.sidebarBg,
            border: Border(bottom: BorderSide(color: AppTheme.glassBorder)),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.accentGreen.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.accentGreen),
                    ),
                    child: const Row(
                      children: [
                        Icon(Icons.circle, size: 8, color: AppTheme.accentGreen),
                        SizedBox(width: 6),
                        Text("localhost:8777 Connected", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppTheme.accentGreen)),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  const Icon(Icons.account_circle, size: 18, color: AppTheme.textSecondary),
                  const SizedBox(width: 6),
                  const Text("muhasibpro@gmail.com", style: TextStyle(fontSize: 12, color: Colors.white, fontWeight: FontWeight.w500)),
                ],
              ),

              Row(
                children: [
                  // Model Selector
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 2),
                    decoration: BoxDecoration(
                      color: AppTheme.cardBg,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppTheme.glassBorder),
                    ),
                    child: DropdownButton<String>(
                      value: _selectedModel,
                      dropdownColor: AppTheme.cardBg,
                      underline: const SizedBox(),
                      style: const TextStyle(color: AppTheme.accentCyan, fontWeight: FontWeight.bold, fontSize: 12),
                      items: ['Gemini 3.6 Flash (High)', 'Gemini 3.6 Pro', 'Flash-Lite'].map((m) {
                        return DropdownMenuItem(value: m, child: Text(m));
                      }).toList(),
                      onChanged: (val) {
                        if (val != null) setState(() => _selectedModel = val);
                      },
                    ),
                  ),
                  const SizedBox(width: 12),

                  // Toggle Sidecar button
                  IconButton(
                    icon: Icon(Icons.space_dashboard_outlined, color: _showSidecar ? AppTheme.accentCyan : AppTheme.textSecondary),
                    onPressed: () => setState(() => _showSidecar = !_showSidecar),
                    tooltip: "Inspector Sidecar Panel",
                  ),
                ],
              ),
            ],
          ),
        ),

        // Main Body (Left Sidebar + Chat Stream + Right Sidecar Inspector)
        Expanded(
          child: Row(
            children: [
              // Left Workspace Explorer Drawer (220px)
              Container(
                width: 230,
                decoration: const BoxDecoration(
                  color: AppTheme.sidebarBg,
                  border: Border(right: BorderSide(color: AppTheme.glassBorder)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // New Chat Button
                    Padding(
                      padding: const EdgeInsets.all(12.0),
                      child: SizedBox(
                        width: double.infinity,
                        child: ElevatedButton.icon(
                          onPressed: () {},
                          icon: const Icon(Icons.add, color: Colors.black, size: 18),
                          label: const Text("YANGI CHAT", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 12)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: AppTheme.accentCyan,
                            padding: const EdgeInsets.symmetric(vertical: 12),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                    ),

                    const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                      child: Text("LOYIHA FAYLLARI (ARTIFACTS)", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.textMuted, letterSpacing: 1.0)),
                    ),

                    // Media / File List
                    Expanded(
                      child: ListView.builder(
                        padding: const EdgeInsets.symmetric(horizontal: 8),
                        itemCount: _mediaFiles.length,
                        itemBuilder: (context, index) {
                          final f = _mediaFiles[index];
                          IconData fIcon = Icons.insert_drive_file;
                          Color fColor = AppTheme.textSecondary;
                          if (f.endsWith('.mp4')) {
                            fIcon = Icons.video_library;
                            fColor = AppTheme.accentPink;
                          } else if (f.endsWith('.xlsx')) {
                            fIcon = Icons.table_chart;
                            fColor = AppTheme.accentGreen;
                          } else if (f.endsWith('.py')) {
                            fIcon = Icons.code;
                            fColor = AppTheme.accentYellow;
                          }

                          return ListTile(
                            dense: true,
                            horizontalTitleGap: 8,
                            leading: Icon(fIcon, size: 16, color: fColor),
                            title: Text(f, style: const TextStyle(fontSize: 12, color: Colors.white70), overflow: TextOverflow.ellipsis),
                            onTap: () {},
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),

              // Center Chat Messages Stream
              Expanded(
                child: Column(
                  children: [
                    Expanded(
                      child: ListView.builder(
                        controller: _scrollController,
                        padding: const EdgeInsets.symmetric(vertical: 16),
                        itemCount: _messages.length,
                        itemBuilder: (context, index) {
                          return ChatBubbleWidget(message: _messages[index]);
                        },
                      ),
                    ),

                    // Bottom Dock Input Box (localhost:8777 Prompt Dock)
                    Container(
                      padding: const EdgeInsets.all(16),
                      decoration: const BoxDecoration(
                        color: AppTheme.sidebarBg,
                        border: Border(top: BorderSide(color: AppTheme.glassBorder)),
                      ),
                      child: Row(
                        children: [
                          // Voice dictation button
                          IconButton(
                            icon: Icon(_isListeningVoice ? Icons.mic : Icons.mic_none, color: _isListeningVoice ? AppTheme.accentPink : AppTheme.textSecondary),
                            onPressed: () {
                              setState(() => _isListeningVoice = !_isListeningVoice);
                            },
                            tooltip: "O'zbekcha Ovozli Kiritish",
                          ),
                          const SizedBox(width: 4),

                          // File attachment button
                          IconButton(
                            icon: const Icon(Icons.attach_file, color: AppTheme.textSecondary),
                            onPressed: () {},
                            tooltip: "Rasm/Fayl biriktirish",
                          ),

                          const SizedBox(width: 8),

                          // Prompt TextField
                          Expanded(
                            child: TextField(
                              controller: _promptController,
                              style: const TextStyle(color: Colors.white, fontSize: 14),
                              decoration: InputDecoration(
                                hintText: "Antigravity AI agentga topshiriq bering...",
                                hintStyle: const TextStyle(color: AppTheme.textMuted, fontSize: 13),
                                filled: true,
                                fillColor: AppTheme.cardBg,
                                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.accentCyan)),
                              ),
                              onSubmitted: (_) => _sendMessage(),
                            ),
                          ),
                          const SizedBox(width: 10),

                          // Send button
                          ElevatedButton.icon(
                            onPressed: _sendMessage,
                            icon: const Icon(Icons.send, color: Colors.black, size: 18),
                            label: const Text("YUBORISH", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 12)),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.accentCyan,
                              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
                              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

              // Right Inspector Sidecar Panel (Optional 300px)
              if (_showSidecar)
                Container(
                  width: 290,
                  decoration: const BoxDecoration(
                    color: AppTheme.sidebarBg,
                    border: Border(left: BorderSide(color: AppTheme.glassBorder)),
                  ),
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.developer_mode, color: AppTheme.accentCyan, size: 18),
                          SizedBox(width: 8),
                          Text("Agent Sidecar Inspector", style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 14)),
                        ],
                      ),
                      const SizedBox(height: 16),

                      // Status Cards
                      GlassCard(
                        padding: const EdgeInsets.all(12),
                        child: const Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text("ACTIVE SUBAGENTS", style: TextStyle(fontSize: 10, color: AppTheme.textMuted, fontWeight: FontWeight.bold)),
                            SizedBox(height: 6),
                            Row(
                              children: [
                                Icon(Icons.check_circle, size: 14, color: AppTheme.accentGreen),
                                SizedBox(width: 6),
                                Text("Research Subagent: Active", style: TextStyle(fontSize: 12, color: Colors.white)),
                              ],
                            ),
                            SizedBox(height: 4),
                            Row(
                              children: [
                                Icon(Icons.sync, size: 14, color: AppTheme.accentCyan),
                                SizedBox(width: 6),
                                Text("Code Executor: Running", style: TextStyle(fontSize: 12, color: Colors.white)),
                              ],
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 14),

                      // System Stats
                      GlassCard(
                        padding: const EdgeInsets.all(12),
                        child: const Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text("SYSTEM METRICS", style: TextStyle(fontSize: 10, color: AppTheme.textMuted, fontWeight: FontWeight.bold)),
                            SizedBox(height: 8),
                            Text("CPU: 12% (Apple M-Series)", style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                            SizedBox(height: 4),
                            Text("RAM: 14.2 GB / 32 GB", style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                            SizedBox(height: 4),
                            Text("PTY Buffer: 12,000 lines", style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
