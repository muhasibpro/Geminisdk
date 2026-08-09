import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://localhost:8777';

  // Check connection status
  static Future<Map<String, dynamic>?> getStatus() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/status')).timeout(const Duration(seconds: 3));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {
      return null; // Offline / Not running
    }
    return null;
  }

  // Get list of all jobs/chats
  static Future<List<dynamic>> getJobs() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/jobs')).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data is List) return data;
      }
    } catch (_) {}
    return [];
  }

  // Get detailed job output (Reasoning, tool calls, text acts)
  static Future<Map<String, dynamic>?> getJobDetails(String jobId, {int from = 0}) async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/job?id=${Uri.encodeComponent(jobId)}&from=$from')).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        return jsonDecode(response.body) as Map<String, dynamic>;
      }
    } catch (_) {}
    return null;
  }

  // Send user prompt to http://localhost:8777/api/chat
  static Future<bool> sendPrompt(String prompt) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'prompt': prompt}),
      ).timeout(const Duration(seconds: 8));

      if (response.statusCode == 200) {
        return true;
      }
    } catch (_) {}
    return false;
  }

  // Start new chat session
  static Future<bool> startNewChat() async {
    try {
      final response = await http.post(Uri.parse('$baseUrl/api/new-chat')).timeout(const Duration(seconds: 4));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // Stop currently running job
  static Future<bool> stopJob() async {
    try {
      final response = await http.post(Uri.parse('$baseUrl/api/job/stop')).timeout(const Duration(seconds: 4));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // List project directory files
  static Future<List<dynamic>> listFiles([String path = '']) async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/api/ls?path=${Uri.encodeComponent(path)}')).timeout(const Duration(seconds: 4));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data is List) return data;
      }
    } catch (_) {}
    return [];
  }
}
