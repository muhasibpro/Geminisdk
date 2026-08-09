import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../widgets/custom_painter_wave.dart';

class VoiceStudioView extends StatefulWidget {
  const VoiceStudioView({super.key});

  @override
  State<VoiceStudioView> createState() => _VoiceStudioViewState();
}

class _VoiceStudioViewState extends State<VoiceStudioView> with SingleTickerProviderStateMixin {
  late AnimationController _animController;
  bool _isPlaying = false;
  String _selectedVoice = 'uz-UZ-SardorNeural';
  final TextEditingController _textController = TextEditingController(
    text: "MUHASIB POS kassa dasturi bilan savdo va hisob-kitoblarni 10 barobar tezlashtiring!",
  );

  final List<Map<String, String>> _voices = [
    {
      'id': 'uz-UZ-SardorNeural',
      'name': 'Sardor (Erkak suxondon)',
      'desc': 'Rasmiy, aniq va professional o\'zbek erkak ovozi',
      'gender': 'Male',
    },
    {
      'id': 'uz-UZ-MadinaNeural',
      'name': 'Madina (Ayol suxondon)',
      'desc': 'Yumshoq, samimiy va reklamabop o\'zbek ayol ovozi',
      'gender': 'Female',
    },
  ];

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );
  }

  void _toggleSpeech() {
    setState(() {
      _isPlaying = !_isPlaying;
    });

    if (_isPlaying) {
      _animController.repeat();
      // Auto stop after 5 seconds simulation
      Timer(const Duration(seconds: 5), () {
        if (mounted) {
          setState(() {
            _isPlaying = false;
            _animController.stop();
          });
        }
      });
    } else {
      _animController.stop();
    }
  }

  @override
  void dispose() {
    _animController.dispose();
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          const Text(
            "Edge-TTS Uzbek Neural Voices Studio",
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          const SizedBox(height: 4),
          const Text(
            "O'zbek milliy suxondon ovozlarida reklama va kassa xabarlarini avtomatik talaffuz qilish",
            style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
          ),

          const SizedBox(height: 20),

          // Voice Selection Cards
          Row(
            children: _voices.map((voice) {
              bool isSelected = _selectedVoice == voice['id'];
              Color accentColor = voice['gender'] == 'Male' ? AppTheme.accentCyan : AppTheme.accentPink;

              return Expanded(
                child: Padding(
                  padding: const EdgeInsets.only(right: 12.0),
                  child: GlassCard(
                    onTap: () => setState(() => _selectedVoice = voice['id']!),
                    backgroundColor: isSelected ? accentColor.withOpacity(0.15) : AppTheme.cardBg,
                    borderColor: isSelected ? accentColor : AppTheme.glassBorder,
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: accentColor.withOpacity(0.2),
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            voice['gender'] == 'Male' ? Icons.record_voice_over : Icons.record_voice_over_outlined,
                            color: accentColor,
                            size: 28,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(voice['name']!, style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 15)),
                              const SizedBox(height: 4),
                              Text(voice['desc']!, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                            ],
                          ),
                        ),
                        if (isSelected)
                          Icon(Icons.check_circle, color: accentColor, size: 22),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),

          const SizedBox(height: 24),

          // Speech Generator Box
          GlassCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text("Talaffuz etiladigan matn (Uzbek Speech Prompt):", style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 14)),
                const SizedBox(height: 10),
                TextField(
                  controller: _textController,
                  maxLines: 3,
                  style: const TextStyle(color: Colors.white, fontSize: 15),
                  decoration: InputDecoration(
                    filled: true,
                    fillColor: Colors.black.withOpacity(0.3),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                    enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                    focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.accentCyan)),
                  ),
                ),
                const SizedBox(height: 20),

                // Audio Wave Visualizer
                AnimatedBuilder(
                  animation: _animController,
                  builder: (context, child) {
                    return Container(
                      height: 90,
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(horizontal: 16),
                      decoration: BoxDecoration(
                        color: Colors.black26,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppTheme.glassBorder),
                      ),
                      child: CustomPaint(
                        painter: AudioWavePainter(
                          animationValue: _animController.value,
                          isPlaying: _isPlaying,
                          waveColor: _selectedVoice.contains('Sardor') ? AppTheme.accentCyan : AppTheme.accentPink,
                        ),
                      ),
                    );
                  },
                ),

                const SizedBox(height: 20),

                // Action Buttons
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      _isPlaying ? "Ovoza berilmoqda: ${_selectedVoice}..." : "Audio tayyor",
                      style: TextStyle(
                        color: _isPlaying ? AppTheme.accentGreen : AppTheme.textSecondary,
                        fontWeight: FontWeight.bold,
                      ),
                    ),

                    ElevatedButton.icon(
                      onPressed: _toggleSpeech,
                      icon: Icon(_isPlaying ? Icons.stop : Icons.volume_up, color: Colors.black),
                      label: Text(_isPlaying ? "TO'XTATISH" : "OVOZDA TALAFFUZ QILISH", style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _selectedVoice.contains('Sardor') ? AppTheme.accentCyan : AppTheme.accentPink,
                        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
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
}
