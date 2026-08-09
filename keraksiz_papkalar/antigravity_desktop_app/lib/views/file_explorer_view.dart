import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class FileExplorerView extends StatefulWidget {
  const FileExplorerView({super.key});

  @override
  State<FileExplorerView> createState() => _FileExplorerViewState();
}

class _FileExplorerViewState extends State<FileExplorerView> {
  List<dynamic> _files = [];
  bool _isLoading = true;
  String _currentPath = '';

  @override
  void initState() {
    super.initState();
    _loadFiles();
  }

  Future<void> _loadFiles([String path = '']) async {
    setState(() => _isLoading = true);
    final filesList = await ApiService.listFiles(path);
    if (mounted) {
      setState(() {
        _files = filesList;
        _currentPath = path;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    "Real Localhost File Explorer (/api/ls)",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _currentPath.isEmpty ? "Loyiha ildiz papkasi: /Users/muhasibpro/Desktop/Geminisdk" : "Papkada: $_currentPath",
                    style: const TextStyle(fontSize: 12, color: AppTheme.accentCyan),
                  ),
                ],
              ),

              ElevatedButton.icon(
                onPressed: () => _loadFiles(_currentPath),
                icon: const Icon(Icons.refresh, color: Colors.black, size: 16),
                label: const Text("YANGILASH", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 11)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.accentGreen,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: AppTheme.accentCyan))
                : _files.isEmpty
                    ? const Center(child: Text("Fayllar topilmadi", style: TextStyle(color: AppTheme.textMuted)))
                    : ListView.builder(
                        itemCount: _files.length,
                        itemBuilder: (context, index) {
                          final item = _files[index];
                          final String name = item['name'] ?? item.toString();
                          final bool isDir = item['isDir'] ?? item['is_dir'] ?? false;
                          final int size = item['sizeBytes'] ?? item['size'] ?? 0;

                          IconData iconData = isDir ? Icons.folder : Icons.insert_drive_file;
                          Color iconColor = isDir ? AppTheme.accentYellow : AppTheme.textSecondary;
                          if (name.endsWith('.mp4')) {
                            iconData = Icons.video_library;
                            iconColor = AppTheme.accentPink;
                          } else if (name.endsWith('.xlsx')) {
                            iconData = Icons.table_chart;
                            iconColor = AppTheme.accentGreen;
                          } else if (name.endsWith('.py')) {
                            iconData = Icons.code;
                            iconColor = AppTheme.accentCyan;
                          }

                          return Padding(
                            padding: const EdgeInsets.only(bottom: 6.0),
                            child: GlassCard(
                              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                              onTap: isDir ? () => _loadFiles(name) : null,
                              child: Row(
                                children: [
                                  Icon(iconData, color: iconColor, size: 22),
                                  const SizedBox(width: 14),
                                  Expanded(
                                    child: Text(
                                      name,
                                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w500, fontSize: 13),
                                    ),
                                  ),
                                  if (!isDir && size > 0)
                                    Text(
                                      "${(size / 1024).toStringAsFixed(1)} KB",
                                      style: const TextStyle(color: AppTheme.textMuted, fontSize: 11),
                                    ),
                                  if (isDir)
                                    const Icon(Icons.arrow_forward_ios, size: 12, color: AppTheme.textMuted),
                                ],
                              ),
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
