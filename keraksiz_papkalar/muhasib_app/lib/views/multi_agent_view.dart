import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/agent_task.dart';
import '../widgets/glass_card.dart';

class MultiAgentView extends StatefulWidget {
  const MultiAgentView({super.key});

  @override
  State<MultiAgentView> createState() => _MultiAgentViewState();
}

class _MultiAgentViewState extends State<MultiAgentView> {
  final List<AgentTask> _tasks = [
    AgentTask(
      id: 'sub-001',
      title: 'Codebase Research & Audit',
      agentRole: 'Codebase Researcher',
      description: 'MUHASIB kassa tovarlar bazasi va Excel export mexanizmini tekshirish.',
      progress: 1.0,
      status: TaskStatus.completed,
      timestamp: DateTime.now().subtract(const Duration(minutes: 15)),
    ),
    AgentTask(
      id: 'sub-002',
      title: 'Vector Cartoon Animation Generation',
      agentRole: 'Motion Render Agent',
      description: 'video/make_multik.py skripti yordamida kassa reklama sahnalarini render qilish.',
      progress: 0.75,
      status: TaskStatus.running,
      timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
    ),
    AgentTask(
      id: 'sub-003',
      title: 'Edge-TTS Uzbek Voice Synthesis',
      agentRole: 'Audio Synthesis Subagent',
      description: 'uz-UZ-SardorNeural ovozida kassa matnini mp3 aylantirish.',
      progress: 0.90,
      status: TaskStatus.running,
      timestamp: DateTime.now().subtract(const Duration(minutes: 2)),
    ),
    AgentTask(
      id: 'sub-004',
      title: 'macOS Flutter App Bundle Compiler',
      agentRole: 'macOS Build Subagent',
      description: 'flutter build macos buyrug\'ini yuritib, Native Release binarini tayyorlash.',
      progress: 0.35,
      status: TaskStatus.running,
      timestamp: DateTime.now(),
    ),
  ];

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
                    "Multi-Agent Subagent Orchestrator",
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  SizedBox(height: 4),
                  Text(
                    "Parallel AI subagentlari (invoke_subagent) va topshiriqlar muvofiqlashtiruvchisi",
                    style: TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: () {
                  setState(() {
                    _tasks.add(
                      AgentTask(
                        id: 'sub-00${_tasks.length + 1}',
                        title: 'Dynamic Vision Cutout Task',
                        agentRole: 'AI Segmentation Agent',
                        description: 'images_real/ papkasidagi rasmlarni cutout qilish.',
                        progress: 0.1,
                        status: TaskStatus.running,
                        timestamp: DateTime.now(),
                      ),
                    );
                  });
                },
                icon: const Icon(Icons.add_task, color: Colors.black),
                label: const Text("YANGI SUBAGENT SOHASINI ISHGA TUSHIRISH", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.primaryNeon,
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ],
          ),

          const SizedBox(height: 20),

          // Subagent Grid
          ListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _tasks.length,
            itemBuilder: (context, index) {
              final task = _tasks[index];
              return Padding(
                padding: const EdgeInsets.only(bottom: 12.0),
                child: GlassCard(
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: _getStatusColor(task.status).withOpacity(0.2),
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          _getStatusIcon(task.status),
                          color: _getStatusColor(task.status),
                          size: 24,
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text(
                                  task.title,
                                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: Colors.white),
                                ),
                                Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: _getStatusColor(task.status).withOpacity(0.15),
                                    borderRadius: BorderRadius.circular(8),
                                    border: Border.all(color: _getStatusColor(task.status)),
                                  ),
                                  child: Text(
                                    task.agentRole.toUpperCase(),
                                    style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: _getStatusColor(task.status)),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Text(task.description, style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary)),
                            const SizedBox(height: 10),

                            // Progress Bar
                            Row(
                              children: [
                                Expanded(
                                  child: LinearProgressIndicator(
                                    value: task.progress,
                                    backgroundColor: Colors.black26,
                                    valueColor: AlwaysStoppedAnimation<Color>(_getStatusColor(task.status)),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                Text(
                                  "${(task.progress * 100).toInt()}%",
                                  style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 12),
                                ),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Color _getStatusColor(TaskStatus status) {
    switch (status) {
      case TaskStatus.completed:
        return AppTheme.accentGreen;
      case TaskStatus.running:
        return AppTheme.accentCyan;
      case TaskStatus.pending:
        return AppTheme.accentYellow;
      case TaskStatus.failed:
        return AppTheme.accentPink;
    }
  }

  IconData _getStatusIcon(TaskStatus status) {
    switch (status) {
      case TaskStatus.completed:
        return Icons.check_circle;
      case TaskStatus.running:
        return Icons.sync;
      case TaskStatus.pending:
        return Icons.hourglass_empty;
      case TaskStatus.failed:
        return Icons.error;
    }
  }
}
