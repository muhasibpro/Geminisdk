import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

class ChatBubbleWidget extends StatefulWidget {
  final Map<String, dynamic> messageData;

  const ChatBubbleWidget({super.key, required this.messageData});

  @override
  State<ChatBubbleWidget> createState() => _ChatBubbleWidgetState();
}

class _ChatBubbleWidgetState extends State<ChatBubbleWidget> {
  bool _isThoughtExpanded = false;

  @override
  Widget build(BuildContext context) {
    final sender = widget.messageData['sender'] ?? 'antigravity';
    final bool isUser = sender == 'user';
    final text = widget.messageData['text'] ?? '';
    final thought = widget.messageData['thought'];
    final List<dynamic>? toolCalls = widget.messageData['tool_calls'];
    final mediaPath = widget.messageData['media_path'];

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 16.0),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: AppTheme.primaryNeon.withValues(alpha: 0.2),
                shape: BoxShape.circle,
                border: Border.all(color: AppTheme.primaryNeon),
              ),
              child: const Icon(Icons.auto_awesome, size: 18, color: AppTheme.accentCyan),
            ),
            const SizedBox(width: 10),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.68),
              decoration: BoxDecoration(
                color: isUser
                    ? AppTheme.primaryNeon.withValues(alpha: 0.25)
                    : AppTheme.cardBg.withValues(alpha: 0.9),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(14),
                  topRight: const Radius.circular(14),
                  bottomLeft: Radius.circular(isUser ? 14 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 14),
                ),
                border: Border.all(
                  color: isUser ? AppTheme.primaryNeon.withValues(alpha: 0.5) : AppTheme.glassBorder,
                ),
              ),
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Sender Title
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        isUser ? "Siz (User)" : "Antigravity AI Agent",
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 12,
                          color: isUser ? AppTheme.accentCyan : AppTheme.accentGreen,
                        ),
                      ),
                      const Text(
                        "localhost:8777 Stream",
                        style: TextStyle(fontSize: 9, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),

                  // Reasoning / Thought accordion
                  if (!isUser && thought != null && thought.toString().isNotEmpty) ...[
                    InkWell(
                      onTap: () => setState(() => _isThoughtExpanded = !_isThoughtExpanded),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(6),
                          border: Border.all(color: AppTheme.glassBorder),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.psychology, size: 14, color: AppTheme.accentYellow),
                            const SizedBox(width: 4),
                            const Text("Thinking Process", style: TextStyle(fontSize: 11, color: AppTheme.accentYellow, fontWeight: FontWeight.bold)),
                            const SizedBox(width: 4),
                            Icon(_isThoughtExpanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down, size: 14, color: AppTheme.accentYellow),
                          ],
                        ),
                      ),
                    ),
                    if (_isThoughtExpanded) ...[
                      const SizedBox(height: 6),
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.4),
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          thought.toString(),
                          style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary, fontFamily: 'monospace'),
                        ),
                      ),
                    ],
                    const SizedBox(height: 8),
                  ],

                  // Tool Call Badges
                  if (!isUser && toolCalls != null && toolCalls.isNotEmpty) ...[
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: toolCalls.map((tc) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: AppTheme.accentCyan.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: AppTheme.accentCyan.withValues(alpha: 0.3)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.build_circle, size: 12, color: AppTheme.accentCyan),
                              const SizedBox(width: 4),
                              Text(
                                "${tc['name'] ?? tc['tool']}: ${tc['args'] ?? tc['command'] ?? ''}",
                                style: const TextStyle(fontSize: 10, fontFamily: 'monospace', color: AppTheme.accentCyan),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 8),
                  ],

                  // Text Message Content
                  SelectableText(
                    text,
                    style: const TextStyle(fontSize: 13, color: Colors.white, height: 1.4),
                  ),

                  // Media Card
                  if (mediaPath != null) ...[
                    const SizedBox(height: 10),
                    GlassCard(
                      padding: const EdgeInsets.all(10),
                      backgroundColor: Colors.black.withValues(alpha: 0.4),
                      borderColor: AppTheme.accentGreen.withValues(alpha: 0.4),
                      child: Row(
                        children: [
                          const Icon(Icons.movie_creation, color: AppTheme.accentGreen, size: 24),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              mediaPath.toString().split('/').last,
                              style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const Icon(Icons.play_circle_fill, color: AppTheme.accentGreen, size: 24),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 10),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: const BoxDecoration(color: AppTheme.accentCyan, shape: BoxShape.circle),
              child: const Icon(Icons.person, size: 16, color: Colors.black),
            ),
          ],
        ],
      ),
    );
  }
}
