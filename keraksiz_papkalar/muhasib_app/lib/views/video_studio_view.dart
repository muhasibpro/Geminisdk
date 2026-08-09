import 'dart:async';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';
import '../widgets/character_animation_widget.dart';

class VideoStudioView extends StatefulWidget {
  const VideoStudioView({super.key});

  @override
  State<VideoStudioView> createState() => _VideoStudioViewState();
}

class _VideoStudioViewState extends State<VideoStudioView> {
  double _progress = 0.0;
  bool _isPlaying = false;
  String _activeMode = 'cartoon'; // 'cartoon' or 'real'
  Timer? _timer;
  int _fps = 30;
  String _audioTrack = 'uz-UZ-SardorNeural @ 12.2s';

  @override
  void initState() {
    super.initState();
  }

  void _togglePlay() {
    setState(() {
      _isPlaying = !_isPlaying;
    });

    if (_isPlaying) {
      _timer = Timer.periodic(const Duration(milliseconds: 33), (timer) {
        if (mounted) {
          setState(() {
            _progress += 0.005;
            if (_progress >= 1.0) _progress = 0.0;
          });
        }
      });
    } else {
      _timer?.cancel();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header title
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "AI Video & Animation Studio (SEEK Render Pipeline)",
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    "Headless Chrome → Frame-by-Frame SEEK(t) → ffmpeg (make_multik.py & make_real_demo.py)",
                    style: TextStyle(fontSize: 13, color: AppTheme.accentCyan.withOpacity(0.8)),
                  ),
                ],
              ),

              // Mode Toggle
              Container(
                decoration: BoxDecoration(
                  color: AppTheme.cardBg,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppTheme.glassBorder),
                ),
                child: Row(
                  children: [
                    _buildModeButton('cartoon', "Vektor Multik", Icons.animation),
                    _buildModeButton('real', "Real Motion AI", Icons.person_pin),
                  ],
                ),
              ),
            ],
          ),

          const SizedBox(height: 20),

          // Main Animation Preview Canvas
          GlassCard(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                // Render Canvas Container
                ClipRRect(
                  borderRadius: const BorderRadius.vertical(top: Radius.circular(16)),
                  child: Container(
                    height: 380,
                    width: double.infinity,
                    child: CustomPaint(
                      painter: MotionCanvasPainter(progress: _progress, mode: _activeMode),
                    ),
                  ),
                ),

                // Controls & Timeline
                Container(
                  padding: const EdgeInsets.all(16),
                  color: AppTheme.sidebarBg,
                  child: Column(
                    children: [
                      // Timeline Slider
                      Row(
                        children: [
                          Text(
                            "${(_progress * 30.0).toStringAsFixed(1)}s",
                            style: const TextStyle(color: AppTheme.accentCyan, fontWeight: FontWeight.bold, fontFamily: 'monospace'),
                          ),
                          Expanded(
                            child: Slider(
                              value: _progress,
                              onChanged: (val) {
                                setState(() {
                                  _progress = val;
                                });
                              },
                              activeColor: AppTheme.primaryNeon,
                              inactiveColor: AppTheme.glassBorder,
                            ),
                          ),
                          const Text(
                            "30.0s",
                            style: TextStyle(color: AppTheme.textSecondary, fontFamily: 'monospace'),
                          ),
                        ],
                      ),

                      // Control Buttons
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              IconButton(
                                icon: Icon(_isPlaying ? Icons.pause_circle_filled : Icons.play_circle_filled, size: 40, color: AppTheme.accentCyan),
                                onPressed: _togglePlay,
                              ),
                              const SizedBox(width: 8),
                              IconButton(
                                icon: const Icon(Icons.replay_10, color: AppTheme.textSecondary),
                                onPressed: () => setState(() => _progress = (_progress - 0.1).clamp(0.0, 1.0)),
                              ),
                              IconButton(
                                icon: const Icon(Icons.forward_10, color: AppTheme.textSecondary),
                                onPressed: () => setState(() => _progress = (_progress + 0.1).clamp(0.0, 1.0)),
                              ),
                            ],
                          ),

                          Row(
                            children: [
                              const Icon(Icons.audiotrack, size: 16, color: AppTheme.accentYellow),
                              const SizedBox(width: 6),
                              Text(_audioTrack, style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                              const SizedBox(width: 20),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                decoration: BoxDecoration(color: AppTheme.cardBg, borderRadius: BorderRadius.circular(8), border: Border.all(color: AppTheme.glassBorder)),
                                child: Text("$_fps FPS", style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Colors.white)),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),

          const SizedBox(height: 24),

          // Render Architecture Cards
          Row(
            children: [
              Expanded(
                child: GlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.code, color: AppTheme.accentPink),
                          SizedBox(width: 10),
                          Text("SEEK(t) JS Protocol", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Colors.white)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        "window.DURATION = 30;\nwindow.SEEK = function(t) {\n   // Kadrma-kadr render qilish\n}",
                        style: TextStyle(fontFamily: 'monospace', fontSize: 12, color: AppTheme.accentCyan),
                      ),
                      const SizedBox(height: 8),
                      const Text("CSS Animation ishlatilmaydi — barcha harakat SEEK(t) vaqtidan hisoblanib, audio bilan 100% sinxron bo'ladi.", style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: GlassCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.center_focus_strong, color: AppTheme.accentGreen),
                          SizedBox(width: 10),
                          Text("Vision Layer Segmentation", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15, color: Colors.white)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        ".venv/bin/python video/make_real_demo.py image.jpg",
                        style: TextStyle(fontFamily: 'monospace', fontSize: 12, color: AppTheme.accentGreen),
                      ),
                      const SizedBox(height: 8),
                      const Text("macOS Vision ramkasi orqali rasmdagi odam qatlamlarga ajratiladi, fon inpaint qilinadi va oyoq-qo'llar bo'g'inda burchak bo'yicha harakatlanadi.", style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildModeButton(String modeKey, String label, IconData icon) {
    bool isSel = _activeMode == modeKey;
    return InkWell(
      onTap: () => setState(() => _activeMode = modeKey),
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          color: isSel ? AppTheme.primaryNeon : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Row(
          children: [
            Icon(icon, size: 16, color: isSel ? Colors.white : AppTheme.textSecondary),
            const SizedBox(width: 8),
            Text(label, style: TextStyle(fontWeight: isSel ? FontWeight.bold : FontWeight.normal, color: isSel ? Colors.white : AppTheme.textSecondary, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
