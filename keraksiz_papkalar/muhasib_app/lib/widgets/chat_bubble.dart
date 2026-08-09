import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import 'glass_card.dart';

class ChatMessageModel {
  final String id;
  final String sender; // 'user' or 'antigravity'
  final String text;
  final String? thought;
  final List<Map<String, String>>? toolCalls; // [{'name': 'run_command', 'args': '...', 'status': '0'}]
  final String? mediaPath; // '/path/to/video.mp4' or image
  final String? mediaType; // 'video', 'audio', 'image'
  final DateTime timestamp;

  ChatMessageModel({
    required this.id,
    required this.sender,
    required this.text,
    this.thought,
    this.toolCalls,
    this.mediaPath,
    this.mediaType,
    required this.timestamp,
  });
}

class ChatBubbleWidget extends StatefulWidget {
  final ChatMessageModel message;

  const ChatBubbleWidget({super.key, required this.message});

  @override
  State<ChatBubbleWidget> createState() => _ChatBubbleWidgetState();
}

class _ChatBubbleWidgetState extends State<ChatBubbleWidget> {
  bool _isThoughtExpanded = false;

  @override
  Widget build(BuildContext context) {
    bool isUser = widget.message.sender == 'user';

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10.0, horizontal: 16.0),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.primaryNeon.withValues(alpha: 0.2),
                shape: BoxShape.circle,
                border: Border.all(color: AppTheme.primaryNeon),
              ),
              child: const Icon(Icons.auto_awesome, size: 20, color: AppTheme.accentCyan),
            ),
            const SizedBox(width: 12),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.65),
              decoration: BoxDecoration(
                color: isUser
                    ? AppTheme.primaryNeon.withValues(alpha: 0.25)
                    : AppTheme.cardBg.withValues(alpha: 0.85),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(16),
                  topRight: const Radius.circular(16),
                  bottomLeft: Radius.circular(isUser ? 16 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 16),
                ),
                border: Border.all(
                  color: isUser
                      ? AppTheme.primaryNeon.withValues(alpha: 0.5)
                      : AppTheme.glassBorder,
                ),
              ),
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Sender Header
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        isUser ? "Siz (User)" : "Antigravity AI Agent",
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                          color: isUser ? AppTheme.accentCyan : AppTheme.accentGreen,
                        ),
                      ),
                      Text(
                        "${widget.message.timestamp.hour.toString().padLeft(2, '0')}:${widget.message.timestamp.minute.toString().padLeft(2, '0')}",
                        style: const TextStyle(fontSize: 10, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),

                  // Thought Process Accordion (if AI)
                  if (!isUser && widget.message.thought != null) ...[
                    InkWell(
                      onTap: () => setState(() => _isThoughtExpanded = !_isThoughtExpanded),
                      borderRadius: BorderRadius.circular(8),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.3),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(color: AppTheme.glassBorder),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            const Icon(Icons.psychology, size: 14, color: AppTheme.accentYellow),
                            const SizedBox(width: 6),
                            const Text("Reasoning & Thought Process", style: TextStyle(fontSize: 11, color: AppTheme.accentYellow, fontWeight: FontWeight.bold)),
                            const SizedBox(width: 6),
                            Icon(_isThoughtExpanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down, size: 14, color: AppTheme.accentYellow),
                          ],
                        ),
                      ),
                    ),
                    if (_isThoughtExpanded) ...[
                      const SizedBox(height: 8),
                      Container(
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.4),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          widget.message.thought!,
                          style: const TextStyle(fontSize: 12, color: AppTheme.textSecondary, fontFamily: 'monospace'),
                        ),
                      ),
                    ],
                    const SizedBox(height: 10),
                  ],

                  // Tool Calls Badges (if AI)
                  if (!isUser && widget.message.toolCalls != null && widget.message.toolCalls!.isNotEmpty) ...[
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: widget.message.toolCalls!.map((tc) {
                        return Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: AppTheme.accentCyan.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: AppTheme.accentCyan.withValues(alpha: 0.4)),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const Icon(Icons.build_circle, size: 12, color: AppTheme.accentCyan),
                              const SizedBox(width: 6),
                              Text(
                                "${tc['name']}: ${tc['args']}",
                                style: const TextStyle(fontSize: 11, fontFamily: 'monospace', color: AppTheme.accentCyan),
                              ),
                            ],
                          ),
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 10),
                  ],

                  // Main Text Content
                  SelectableText(
                    widget.message.text,
                    style: const TextStyle(
                      fontSize: 14,
                      color: Colors.white,
                      height: 1.45,
                    ),
                  ),

                  // Media Card Embed (if video, image or audio generated)
                  if (widget.message.mediaPath != null) ...[
                    const SizedBox(height: 12),
                    GlassCard(
                      padding: const EdgeInsets.all(12),
                      backgroundColor: Colors.black.withValues(alpha: 0.4),
                      borderColor: AppTheme.accentGreen.withValues(alpha: 0.5),
                      child: Row(
                        children: [
                          Icon(
                            widget.message.mediaType == 'video'
                                ? Icons.video_collection
                                : (widget.message.mediaType == 'audio' ? Icons.audiotrack : Icons.image),
                            color: AppTheme.accentGreen,
                            size: 28,
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  widget.message.mediaPath!.split('/').last,
                                  style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 13),
                                  overflow: TextOverflow.ellipsis,
                                ),
                                const SizedBox(height: 2),
                                Text(
                                  "Generated Artifact | Click to preview",
                                  style: TextStyle(fontSize: 11, color: AppTheme.accentGreen.withValues(alpha: 0.8)),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.play_circle_fill, color: AppTheme.accentGreen, size: 28),
                            onPressed: () {},
                          ),
                        ],
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 12),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: const BoxDecoration(
                color: AppTheme.accentCyan,
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.person, size: 18, color: Colors.black),
            ),
          ],
        ],
      ),
    );
  }
}
