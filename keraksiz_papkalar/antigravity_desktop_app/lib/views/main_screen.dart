import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'antigravity_chat_view.dart';
import 'file_explorer_view.dart';
import 'jobs_history_view.dart';

class MainScreen extends StatefulWidget {
  const MainScreen({super.key});

  @override
  State<MainScreen> createState() => _MainScreenState();
}

class _MainScreenState extends State<MainScreen> {
  int _selectedIndex = 0;

  final List<String> _titles = [
    "Antigravity Live Chat Stream (http://localhost:8777)",
    "Project File Explorer (/api/ls)",
    "Antigravity Job History & Queue (/api/jobs)",
  ];

  @override
  Widget build(BuildContext context) {
    Widget activeBody;
    switch (_selectedIndex) {
      case 0:
        activeBody = const AntigravityChatView();
        break;
      case 1:
        activeBody = const FileExplorerView();
        break;
      case 2:
        activeBody = const JobsHistoryView();
        break;
      default:
        activeBody = const AntigravityChatView();
    }

    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Row(
        children: [
          // Left Navigation Sidebar
          Container(
            width: 240,
            color: AppTheme.sidebarBg,
            child: Column(
              children: [
                const SizedBox(height: 36),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16.0),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: AppTheme.primaryNeon.withValues(alpha: 0.2),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.primaryNeon),
                        ),
                        child: const Icon(Icons.rocket_launch, color: AppTheme.accentCyan, size: 22),
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
                            "Real Localhost 8777 Client",
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
                      _buildNavItem(0, "Live AI Chat (8777)", Icons.chat_bubble, AppTheme.accentCyan),
                      _buildNavItem(1, "File Explorer (/api/ls)", Icons.folder, AppTheme.accentYellow),
                      _buildNavItem(2, "Jobs Jurnali (/api/jobs)", Icons.work_history, AppTheme.accentGreen),
                    ],
                  ),
                ),

                // System Footer Info
                Container(
                  padding: const EdgeInsets.all(12),
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
                          Text("macOS Native Client", style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: Colors.white)),
                        ],
                      ),
                      SizedBox(height: 4),
                      Text("Real HTTP/REST Sync | Port 8777", style: TextStyle(fontSize: 10, color: AppTheme.textMuted)),
                    ],
                  ),
                ),
              ],
            ),
          ),

          // Main Content Area
          Expanded(
            child: Column(
              children: [
                // Top Header Bar
                Container(
                  height: 56,
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
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                        decoration: BoxDecoration(
                          color: AppTheme.accentGreen.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: AppTheme.accentGreen.withValues(alpha: 0.4)),
                        ),
                        child: const Text(
                          "REAL HTTP REST CONNECTED",
                          style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: AppTheme.accentGreen),
                        ),
                      ),
                    ],
                  ),
                ),

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
}
