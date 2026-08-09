import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'antigravity_gui_view.dart';
import 'agent_overview_view.dart';
import 'pos_kassa_view.dart';
import 'video_studio_view.dart';
import 'voice_studio_view.dart';
import 'multi_agent_view.dart';
import 'live_terminal_view.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _selectedIndex = 0;

  final List<String> _titles = [
    "Antigravity AI Agent Studio (localhost:8777)",
    "Agent Hobbi & Dynamic Capabilities",
    "MUHASIB Smart POS Kassa",
    "Vector & Real Motion Video Studio",
    "Uzbek Neural Voice TTS Studio",
    "Multi-Agent Subagent Hub",
    "Live CLI & Build Console",
  ];

  @override
  Widget build(BuildContext context) {
    Widget activeBody;
    switch (_selectedIndex) {
      case 0:
        activeBody = const AntigravityGuiView();
        break;
      case 1:
        activeBody = AgentOverviewView(onNavigate: (index) => setState(() => _selectedIndex = index + 1));
        break;
      case 2:
        activeBody = const PosKassaView();
        break;
      case 3:
        activeBody = const VideoStudioView();
        break;
      case 4:
        activeBody = const VoiceStudioView();
        break;
      case 5:
        activeBody = const MultiAgentView();
        break;
      case 6:
        activeBody = const LiveTerminalView();
        break;
      default:
        activeBody = const AntigravityGuiView();
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Row(
        children: [
          // Left Navigation Sidebar (macOS Style)
          Container(
            width: 250,
            color: AppTheme.sidebarBg,
            child: Column(
              children: [
                const SizedBox(height: 36),
                // App Logo / Title
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 18.0),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryNeon.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.primaryNeon),
                        ),
                        child: const Icon(Icons.rocket_launch, color: AppTheme.accentCyan, size: 24),
                      ),
                      const SizedBox(width: 12),
                      const Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            "ANTIGRAVITY",
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 1.2,
                              color: Colors.white,
                            ),
                          ),
                          Text(
                            "localhost:8777 Native macOS",
                            style: TextStyle(
                              fontSize: 9,
                              color: AppTheme.textSecondary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 24),
                const Divider(indent: 16, endIndent: 16),
                const SizedBox(height: 8),

                // Navigation Items
                Expanded(
                  child: ListView(
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    children: [
                      _buildNavItem(0, "Antigravity Chat GUI", Icons.chat_bubble, AppTheme.accentCyan),
                      _buildNavItem(1, "Agent Hobbi & Brain", Icons.psychology, AppTheme.primaryNeon),
                      _buildNavItem(2, "POS Kassa Console", Icons.point_of_sale, AppTheme.accentGreen),
                      _buildNavItem(3, "AI Video Studio", Icons.movie_creation, AppTheme.accentPink),
                      _buildNavItem(4, "Uzbek Voice TTS", Icons.record_voice_over, AppTheme.accentYellow),
                      _buildNavItem(5, "Multi-Agent Hub", Icons.hub, AppTheme.accentOrange),
                      _buildNavItem(6, "Live CLI & Terminal", Icons.terminal, AppTheme.accentGreen),
                    ],
                  ),
                ),

                // macOS System Info Footnote
                Container(
                  padding: const EdgeInsets.all(14),
                  margin: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: AppTheme.cardBg,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppTheme.glassBorder),
                  ),
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.apple, size: 16, color: Colors.white70),
                          SizedBox(width: 6),
                          Text("macOS Apple Silicon", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white)),
                        ],
                      ),
                      SizedBox(height: 4),
                      Text("Antigravity GUI Native Desktop App", style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Main Workspace Area
          Expanded(
            child: Column(
              children: [
                // Top Action Header Bar
                Container(
                  height: 60,
                  decoration: const BoxDecoration(
                    color: AppTheme.sidebarBg,
                    border: Border(bottom: BorderSide(color: AppTheme.glassBorder)),
                  ),
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _titles[_selectedIndex],
                        style: const TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.bold,
                          color: Colors.white,
                        ),
                      ),
                      Row(
                        children: [
                          _buildHeaderBadge("macOS Release Build", AppTheme.accentGreen),
                          const SizedBox(width: 10),
                          _buildHeaderBadge("Port 8777 Engine", AppTheme.accentCyan),
                        ],
                      ),
                    ],
                  ),
                ),

                // Active Tab Content
                Expanded(child: activeBody),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavItem(int index, String title, IconData icon, Color color) {
    bool isSelected = _selectedIndex == index;

    return Padding(
      padding: const EdgeInsets.only(bottom: 4.0),
      child: InkWell(
        onTap: () => setState(() => _selectedIndex = index),
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: isSelected ? color.withValues(alpha: 0.18) : Colors.transparent,
            borderRadius: BorderRadius.circular(10),
            border: isSelected ? Border.all(color: color.withValues(alpha: 0.5)) : null,
          ),
          child: Row(
            children: [
              Icon(icon, color: isSelected ? color : AppTheme.textSecondary, size: 18),
              const SizedBox(width: 12),
              Text(
                title,
                style: TextStyle(
                  color: isSelected ? Colors.white : AppTheme.textSecondary,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeaderBadge(String label, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: color),
      ),
    );
  }
}
