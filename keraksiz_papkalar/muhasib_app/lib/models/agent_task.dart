enum TaskStatus { pending, running, completed, failed }

class AgentTask {
  final String id;
  final String title;
  final String agentRole;
  final String description;
  final double progress; // 0.0 to 1.0
  final TaskStatus status;
  final DateTime timestamp;

  AgentTask({
    required this.id,
    required this.title,
    required this.agentRole,
    required this.description,
    required this.progress,
    required this.status,
    required this.timestamp,
  });

  AgentTask copyWith({
    String? id,
    String? title,
    String? agentRole,
    String? description,
    double? progress,
    TaskStatus? status,
    DateTime? timestamp,
  }) {
    return AgentTask(
      id: id ?? this.id,
      title: title ?? this.title,
      agentRole: agentRole ?? this.agentRole,
      description: description ?? this.description,
      progress: progress ?? this.progress,
      status: status ?? this.status,
      timestamp: timestamp ?? this.timestamp,
    );
  }
}
