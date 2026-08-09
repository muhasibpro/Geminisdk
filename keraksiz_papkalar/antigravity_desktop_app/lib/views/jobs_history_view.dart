import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_theme.dart';
import '../widgets/glass_card.dart';

class JobsHistoryView extends StatefulWidget {
  const JobsHistoryView({super.key});

  @override
  State<JobsHistoryView> createState() => _JobsHistoryViewState();
}

class _JobsHistoryViewState extends State<JobsHistoryView> {
  List<dynamic> _jobs = [];
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchJobs();
  }

  Future<void> _fetchJobs() async {
    setState(() => _isLoading = true);
    final list = await ApiService.getJobs();
    if (mounted) {
      setState(() {
        _jobs = list;
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
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    "Antigravity Job Queue & History (/api/jobs)",
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: Colors.white),
                  ),
                  SizedBox(height: 4),
                  Text(
                    "http://localhost:8777 backendidagi barcha bajarilgan vazifalar jurnali",
                    style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                  ),
                ],
              ),
              ElevatedButton.icon(
                onPressed: _fetchJobs,
                icon: const Icon(Icons.refresh, color: Colors.black, size: 16),
                label: const Text("YANGILASH", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 11)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.accentCyan,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          Expanded(
            child: _isLoading
                ? const Center(child: CircularProgressIndicator(color: AppTheme.accentCyan))
                : _jobs.isEmpty
                    ? const Center(child: Text("Hozircha vazifalar jurnali bo'sh", style: TextStyle(color: AppTheme.textMuted)))
                    : ListView.builder(
                        itemCount: _jobs.length,
                        itemBuilder: (context, index) {
                          final job = _jobs[index];
                          final id = job['id'] ?? 'job-${index + 1}';
                          final prompt = job['prompt'] ?? 'No prompt text';
                          final status = job['status'] ?? 'done';
                          final actsCount = job['acts'] is List ? (job['acts'] as List).length : 0;

                          Color statusColor = AppTheme.accentGreen;
                          if (status == 'running') statusColor = AppTheme.accentCyan;
                          if (status == 'error') statusColor = AppTheme.accentPink;

                          return Padding(
                            padding: const EdgeInsets.only(bottom: 10.0),
                            child: GlassCard(
                              child: Row(
                                children: [
                                  Container(
                                    padding: const EdgeInsets.all(10),
                                    decoration: BoxDecoration(
                                      color: statusColor.withValues(alpha: 0.15),
                                      shape: BoxShape.circle,
                                    ),
                                    child: Icon(
                                      status == 'running' ? Icons.sync : Icons.check_circle,
                                      color: statusColor,
                                      size: 20,
                                    ),
                                  ),
                                  const SizedBox(width: 14),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                          children: [
                                            Text(
                                              "JOB ID: $id",
                                              style: const TextStyle(fontSize: 11, fontFamily: 'monospace', color: AppTheme.accentCyan, fontWeight: FontWeight.bold),
                                            ),
                                            Container(
                                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                              decoration: BoxDecoration(
                                                color: statusColor.withValues(alpha: 0.2),
                                                borderRadius: BorderRadius.circular(6),
                                              ),
                                              child: Text(
                                                status.toUpperCase(),
                                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold, color: statusColor),
                                              ),
                                            ),
                                          ],
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          prompt,
                                          style: const TextStyle(fontWeight: FontWeight.w600, color: Colors.white, fontSize: 13),
                                          maxLines: 2,
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                        const SizedBox(height: 4),
                                        Text(
                                          "Harakatlar soni (Acts): $actsCount",
                                          style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
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
          ),
        ],
      ),
    );
  }
}
