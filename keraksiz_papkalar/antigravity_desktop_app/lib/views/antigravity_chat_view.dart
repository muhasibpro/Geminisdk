import 'dart:async';
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/chat_bubble.dart';

class AntigravityChatView extends StatefulWidget {
  const AntigravityChatView({super.key});

  @override
  State<AntigravityChatView> createState() => _AntigravityChatViewState();
}

class _AntigravityChatViewState extends State<AntigravityChatView> {
  final TextEditingController _promptController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  
  Timer? _pollingTimer;
  bool _isServerOnline = false;
  String _userEmail = '';
  List<dynamic> _jobs = [];
  String? _activeJobId;
  
  List<Map<String, dynamic>> _messages = [];
  bool _isSending = false;

  @override
  void initState() {
    super.initState();
    _checkServerAndFetchData();
    // Poll localhost:8777 every 2 seconds for live real-time sync
    _pollingTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      _checkServerAndFetchData();
    });
  }

  Future<void> _checkServerAndFetchData() async {
    final status = await ApiService.getStatus();
    if (mounted) {
      setState(() {
        _isServerOnline = status != null;
        if (status != null) {
          _userEmail = status['email'] ?? 'muhasibpro@gmail.com';
        }
      });
    }

    if (status != null) {
      final jobsList = await ApiService.getJobs();
      if (mounted) {
        setState(() {
          _jobs = jobsList;
          if (_activeJobId == null && _jobs.isNotEmpty) {
            _activeJobId = _jobs.first['id'];
          }
        });
      }

      if (_activeJobId != null) {
        final jobDetails = await ApiService.getJobDetails(_activeJobId!);
        if (jobDetails != null && mounted) {
          _parseJobDetailsToMessages(jobDetails);
        }
      }
    }
  }

  void _parseJobDetailsToMessages(Map<String, dynamic> details) {
    List<Map<String, dynamic>> parsed = [];
    
    // User prompt message
    String userPrompt = details['prompt'] ?? '';
    if (userPrompt.isNotEmpty) {
      parsed.add({
        'sender': 'user',
        'text': userPrompt,
        'timestamp': DateTime.now(),
      });
    }

    // Acts (AI thought, text, tools)
    final acts = details['acts'];
    if (acts is List) {
      StringBuffer aiTextBuffer = StringBuffer();
      String? thoughtText;
      List<Map<String, String>> toolCalls = [];

      for (var act in acts) {
        if (act is Map) {
          final type = act['type'];
          if (type == 'text') {
            aiTextBuffer.write(act['text'] ?? '');
          } else if (type == 'thought') {
            thoughtText = act['text'];
          } else if (type == 'tool') {
            toolCalls.add({
              'name': act['name'] ?? 'tool',
              'args': act['args'] ?? '',
            });
          }
        }
      }

      if (aiTextBuffer.isNotEmpty || toolCalls.isNotEmpty || thoughtText != null) {
        parsed.add({
          'sender': 'antigravity',
          'text': aiTextBuffer.toString().isEmpty ? "Processing..." : aiTextBuffer.toString(),
          'thought': thoughtText,
          'tool_calls': toolCalls,
          'timestamp': DateTime.now(),
        });
      }
    }

    if (mounted) {
      setState(() {
        if (parsed.isNotEmpty) {
          _messages = parsed;
        }
      });
    }
  }

  Future<void> _sendUserPrompt() async {
    if (_promptController.text.trim().isEmpty || _isSending) return;

    final promptText = _promptController.text.trim();
    setState(() {
      _isSending = true;
      _messages.add({
        'sender': 'user',
        'text': promptText,
        'timestamp': DateTime.now(),
      });
      _promptController.clear();
    });
    _scrollToBottom();

    bool success = await ApiService.sendPrompt(promptText);
    
    if (mounted) {
      setState(() {
        _isSending = false;
      });
      if (!success && !_isServerOnline) {
        // Fallback message if server is offline
        _messages.add({
          'sender': 'antigravity',
          'text': "Local Server (http://localhost:8777) bilan ulanish mavjud emas. Iltimos `./start.sh` yoki `python3 agy_app.py` ni ishga tushiring.",
          'timestamp': DateTime.now(),
        });
      } else {
        // Immediately trigger check to pick up the new job
        _checkServerAndFetchData();
      }
    }
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
  void dispose() {
    _pollingTimer?.cancel();
    _promptController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // Real-time Connection Header Bar
        Container(
          height: 52,
          decoration: const BoxDecoration(
            color: AppTheme.sidebarBg,
            border: Border(bottom: BorderSide(color: AppTheme.glassBorder)),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                    decoration: BoxDecoration(
                      color: (_isServerOnline ? AppTheme.accentGreen : AppTheme.accentPink).withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: _isServerOnline ? AppTheme.accentGreen : AppTheme.accentPink),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.circle, size: 8, color: _isServerOnline ? AppTheme.accentGreen : AppTheme.accentPink),
                        const SizedBox(width: 6),
                        Text(
                          _isServerOnline ? "http://localhost:8777 LIVE API CONNECTED" : "SERVER OFFLINE (localhost:8777)",
                          style: TextStyle(
                            fontSize: 11,
                            fontWeight: FontWeight.bold,
                            color: _isServerOnline ? AppTheme.accentGreen : AppTheme.accentPink,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 16),
                  if (_userEmail.isNotEmpty)
                    Text("Account: $_userEmail", style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                ],
              ),

              ElevatedButton.icon(
                onPressed: () async {
                  await ApiService.startNewChat();
                  _checkServerAndFetchData();
                },
                icon: const Icon(Icons.add, color: Colors.black, size: 16),
                label: const Text("YANGI CHAT", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 11)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.accentCyan,
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ],
          ),
        ),

        // Main Layout (Jobs Drawer + Chat Area)
        Expanded(
          child: Row(
            children: [
              // Left Jobs/Chat History List (220px)
              Container(
                width: 220,
                decoration: const BoxDecoration(
                  color: AppTheme.sidebarBg,
                  border: Border(right: BorderSide(color: AppTheme.glassBorder)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Padding(
                      padding: EdgeInsets.all(12),
                      child: Text("CHAT TARIXI & JOBS", style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.textMuted, letterSpacing: 1.0)),
                    ),
                    Expanded(
                      child: _jobs.isEmpty
                          ? const Center(child: Text("Chatlar mavjud emas", style: TextStyle(fontSize: 11, color: AppTheme.textMuted)))
                          : ListView.builder(
                              itemCount: _jobs.length,
                              itemBuilder: (context, index) {
                                final job = _jobs[index];
                                bool isSelected = _activeJobId == job['id'];
                                String promptText = job['prompt'] ?? 'Suhbat #${index + 1}';

                                return ListTile(
                                  selected: isSelected,
                                  selectedTileColor: AppTheme.primaryNeon.withValues(alpha: 0.15),
                                  dense: true,
                                  leading: Icon(
                                    Icons.chat_bubble_outline,
                                    size: 16,
                                    color: isSelected ? AppTheme.accentCyan : AppTheme.textSecondary,
                                  ),
                                  title: Text(
                                    promptText,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: isSelected ? Colors.white : AppTheme.textSecondary,
                                      fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                                    ),
                                  ),
                                  onTap: () {
                                    setState(() {
                                      _activeJobId = job['id'];
                                    });
                                    _checkServerAndFetchData();
                                  },
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
                      child: _messages.isEmpty
                          ? const Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(Icons.auto_awesome, size: 48, color: AppTheme.accentCyan),
                                  SizedBox(height: 12),
                                  Text(
                                    "Antigravity Real Localhost Engine",
                                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white),
                                  ),
                                  SizedBox(height: 6),
                                  Text(
                                    "http://localhost:8777 serveriga real so'rov yuborish uchun prompt kiriting",
                                    style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                                  ),
                                ],
                              ),
                            )
                          : ListView.builder(
                              controller: _scrollController,
                              padding: const EdgeInsets.symmetric(vertical: 16),
                              itemCount: _messages.length,
                              itemBuilder: (context, index) {
                                return ChatBubbleWidget(messageData: _messages[index]);
                              },
                            ),
                    ),

                    // Bottom Dock Input Box
                    Container(
                      padding: const EdgeInsets.all(14),
                      decoration: const BoxDecoration(
                        color: AppTheme.sidebarBg,
                        border: Border(top: BorderSide(color: AppTheme.glassBorder)),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _promptController,
                              style: const TextStyle(color: Colors.white, fontSize: 14),
                              decoration: InputDecoration(
                                hintText: "http://localhost:8777 backendiga topshiriq bering...",
                                hintStyle: const TextStyle(color: AppTheme.textMuted, fontSize: 13),
                                filled: true,
                                fillColor: AppTheme.cardBg,
                                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                                border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                                enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                                focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.accentCyan)),
                              ),
                              onSubmitted: (_) => _sendUserPrompt(),
                            ),
                          ),
                          const SizedBox(width: 10),

                          ElevatedButton.icon(
                            onPressed: _isSending ? null : _sendUserPrompt,
                            icon: _isSending
                                ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                                : const Icon(Icons.send, color: Colors.black, size: 18),
                            label: Text(
                              _isSending ? "YUBORILMOQDA..." : "YUBORISH",
                              style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 12),
                            ),
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
            ],
          ),
        ),
      ],
    );
  }
}
