import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class AgentOverviewView extends StatefulWidget {
  final Function(int) onNavigate;

  const AgentOverviewView({super.key, required this.onNavigate});

  @override
  State<AgentOverviewView> createState() => _AgentOverviewViewState();
}

class _AgentOverviewViewState extends State<AgentOverviewView> {
  final TextEditingController _promptController = TextEditingController();
  final List<Map<String, String>> _chatHistory = [
    {
      'sender': 'Antigravity AI',
      'text': 'Assalomu alaykum! Men Antigravity AI agentiman. Mening sevimli mashg\'ulotim (hobbi) — murakkab kassa tizimlarini yaratish, fotorealistik rasmlarni harakatlanuvchi reklama roliklariga aylantirish va Flutter macOS ilovalarini build qilishdir! Bugun sizga qanday yordam bera olaman?'
    }
  ];

  void _sendMessage() {
    if (_promptController.text.trim().isEmpty) return;
    String userText = _promptController.text;
    setState(() {
      _chatHistory.add({'sender': 'Foydalanuvchi', 'text': userText});
      _promptController.clear();
      
      // Simulated AI response based on hobby skills
      Future.delayed(const Duration(milliseconds: 600), () {
        if (mounted) {
          setState(() {
            _chatHistory.add({
              'sender': 'Antigravity AI',
              'text': 'Tushundim! "${userText}" bo\'yicha vazifa qabul qilindi. Antigravity AI dvigateli orqali kassa tahlili va render quvurlari ishga tushirildi!'
            });
          });
        }
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Banner / Hero Card
          GlassCard(
            backgroundColor: AppTheme.primaryNeon.withOpacity(0.15),
            borderColor: AppTheme.primaryNeon.withOpacity(0.5),
            child: Row(
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: AppTheme.primaryNeon.withOpacity(0.2),
                    shape: BoxShape.circle,
                    border: Border.all(color: AppTheme.primaryNeon, width: 2),
                  ),
                  child: const Icon(
                    Icons.auto_awesome,
                    size: 40,
                    color: AppTheme.accentCyan,
                  ),
                ),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Text(
                            "ANTIGRAVITY AI",
                            style: TextStyle(
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1.2,
                              color: Colors.white,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: AppTheme.accentGreen.withOpacity(0.2),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: AppTheme.accentGreen),
                            ),
                            child: const Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.fiber_manual_record, size: 10, color: AppTheme.accentGreen),
                                SizedBox(width: 6),
                                Text(
                                  "ACTIVE & READY",
                                  style: TextStyle(
                                    fontSize: 11,
                                    fontWeight: FontWeight.bold,
                                    color: AppTheme.accentGreen,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        "Google DeepMind | macOS Native Agent Architecture | POS & Motion Engine",
                        style: TextStyle(
                          fontSize: 13,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Hobby & Core Capabilities Grid
          const Text(
            "Mening Hobbi va Sevimli Ishlarim (Core Capabilities)",
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),

          GridView.count(
            crossAxisCount: 3,
            crossAxisSpacing: 16,
            mainAxisSpacing: 16,
            shrinkWrap: true,
            childAspectRatio: 1.4,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              _buildSkillCard(
                title: "POS Kassa Avtomatizatsiyasi",
                description: "Shtrix-kod skaneri, Excel tovarlar bazasi parsing, kassa cheklari va oylik daromad tahlili.",
                icon: Icons.point_of_sale,
                color: AppTheme.accentCyan,
                onTap: () => widget.onNavigate(1),
              ),
              _buildSkillCard(
                title: "Vector Cartoon Video Engine",
                description: "Headless Chrome render va SEEK(t) orqali personaj harakatlarini render qilish (make_multik.py).",
                icon: Icons.movie_creation,
                color: AppTheme.accentPink,
                onTap: () => widget.onNavigate(2),
              ),
              _buildSkillCard(
                title: "Real Motion AI Segmentation",
                description: "macOS Vision layer cutout va AI rasmlaridan fotorealistik reklama roliklari yaratish.",
                icon: Icons.video_library,
                color: AppTheme.accentOrange,
                onTap: () => widget.onNavigate(2),
              ),
              _buildSkillCard(
                title: "O'zbek Neural Ovoz (Edge-TTS)",
                description: "uz-UZ-SardorNeural (erkak) va uz-UZ-MadinaNeural (ayol) milliy suxondon ovozlarida gapirish.",
                icon: Icons.record_voice_over,
                color: AppTheme.accentYellow,
                onTap: () => widget.onNavigate(3),
              ),
              _buildSkillCard(
                title: "Multi-Agent Collaboration",
                description: "Research, Self-Code, Video Render va Sound subagentlarini parallel boshqarish.",
                icon: Icons.hub,
                color: AppTheme.primaryNeon,
                onTap: () => widget.onNavigate(4),
              ),
              _buildSkillCard(
                title: "macOS Flutter Build Engine",
                description: "Yuqori unumdorlikdagi macOS Native va Metal grafik rezimida build qilish va CLI loglarini kuzatish.",
                icon: Icons.terminal,
                color: AppTheme.accentGreen,
                onTap: () => widget.onNavigate(5),
              ),
            ],
          ),

          const SizedBox(height: 24),

          // Interactive AI Prompt Box
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.chat_bubble_outline, color: AppTheme.accentCyan),
                    SizedBox(width: 10),
                    Text(
                      "Antigravity AI Agent bilan Muloqot va Topshiriqlar",
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Container(
                  height: 180,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.black.withOpacity(0.3),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.glassBorder),
                  ),
                  child: ListView.builder(
                    itemCount: _chatHistory.length,
                    itemBuilder: (context, index) {
                      final item = _chatHistory[index];
                      final isAI = item['sender'] == 'Antigravity AI';
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4.0),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              "${item['sender']}: ",
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                color: isAI ? AppTheme.accentCyan : AppTheme.accentPink,
                              ),
                            ),
                            Expanded(
                              child: Text(
                                item['text']!,
                                style: const TextStyle(color: AppTheme.textPrimary),
                              ),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: _promptController,
                        style: const TextStyle(color: Colors.white),
                        decoration: InputDecoration(
                          hintText: "Masalan: Muhasib kassa uchun yangi reklama videosi yarat va Sardor ovozida ayt...",
                          hintStyle: const TextStyle(color: AppTheme.textMuted),
                          filled: true,
                          fillColor: Colors.black.withOpacity(0.2),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(color: AppTheme.glassBorder),
                          ),
                          enabledBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(color: AppTheme.glassBorder),
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(12),
                            borderSide: const BorderSide(color: AppTheme.accentCyan),
                          ),
                        ),
                        onSubmitted: (_) => _sendMessage(),
                      ),
                    ),
                    const SizedBox(width: 12),
                    ElevatedButton.icon(
                      onPressed: _sendMessage,
                      icon: const Icon(Icons.send, color: Colors.black),
                      label: const Text("Yuborish", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.accentCyan,
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                      ),
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

  Widget _buildSkillCard({
    required String title,
    required String description,
    required IconData icon,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GlassCard(
      onTap: onTap,
      backgroundColor: color.withOpacity(0.08),
      borderColor: color.withOpacity(0.3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              Icon(Icons.arrow_forward_ios, size: 14, color: color.withOpacity(0.7)),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                description,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppTheme.textSecondary,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
