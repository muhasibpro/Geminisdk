import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class MotionCanvasPainter extends CustomPainter {
  final double progress; // 0.0 to 1.0 (SEEK position)
  final String mode; // 'cartoon' or 'real'

  MotionCanvasPainter({required this.progress, required this.mode});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final w = size.width;
    final h = size.height;

    // Background Gradient Grid / Studio Stage
    final bgGradient = RadialGradient(
      center: Alignment.center,
      radius: 0.85,
      colors: mode == 'cartoon'
          ? [const Color(0xFF2C1654), const Color(0xFF110B27)]
          : [const Color(0xFF142834), const Color(0xFF09131C)],
    );

    final bgRect = Rect.fromLTWH(0, 0, w, h);
    canvas.drawRect(bgRect, Paint()..shader = bgGradient.createShader(bgRect));

    // Floor Line
    final floorY = h * 0.75;
    canvas.drawLine(
      Offset(0, floorY),
      Offset(w, floorY),
      Paint()
        ..color = AppTheme.accentCyan.withOpacity(0.3)
        ..strokeWidth = 2,
    );

    // Dynamic Character Animation based on SEEK(t) -> progress
    double cycle = sin(progress * 2 * pi * 2);
    double legAngle = sin(progress * 2 * pi * 4) * 0.4;
    double handAngle = cos(progress * 2 * pi * 4) * 0.5;

    // Character X Position (Walking across stage)
    double charX = (w * 0.2) + (w * 0.6) * (progress % 1.0);
    double charY = floorY - 90 + cycle * 4;

    // Shadow
    canvas.drawOval(
      Rect.fromCenter(
        center: Offset(charX, floorY + 5),
        width: 70 - cycle * 5,
        height: 14,
      ),
      Paint()..color = Colors.black.withOpacity(0.4),
    );

    if (mode == 'cartoon') {
      // Draw Vector Cartoon Character (Muhasib Boy & Cashier)
      // Head
      final headCenter = Offset(charX, charY - 45);
      canvas.drawCircle(
        headCenter,
        22,
        Paint()..color = const Color(0xFFFFD1A4),
      );

      // Hair
      canvas.drawArc(
        Rect.fromCircle(center: headCenter, radius: 24),
        pi,
        pi,
        true,
        Paint()..color = const Color(0xFF3D2314),
      );

      // Eyes & Smile
      canvas.drawCircle(Offset(charX - 6, charY - 47), 3, Paint()..color = Colors.black);
      canvas.drawCircle(Offset(charX + 6, charY - 47), 3, Paint()..color = Colors.black);
      
      canvas.drawArc(
        Rect.fromCenter(center: Offset(charX, charY - 40), width: 14, height: 10),
        0,
        pi,
        false,
        Paint()
          ..color = Colors.black
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );

      // Body (Shirt)
      final bodyRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(charX, charY + 5), width: 36, height: 50),
        const Radius.circular(8),
      );
      canvas.drawRRect(bodyRect, Paint()..color = AppTheme.primaryNeon);

      // POS Cash Logo on Shirt
      canvas.drawCircle(Offset(charX, charY + 5), 8, Paint()..color = AppTheme.accentYellow);

      // Legs (Joint Rotations)
      final legPaint = Paint()
        ..color = const Color(0xFF1B263B)
        ..strokeWidth = 10
        ..strokeCap = StrokeCap.round;

      // Left Leg
      canvas.drawLine(
        Offset(charX - 8, charY + 30),
        Offset(charX - 8 + sin(legAngle) * 25, charY + 65),
        legPaint,
      );
      // Right Leg
      canvas.drawLine(
        Offset(charX + 8, charY + 30),
        Offset(charX + 8 - sin(legAngle) * 25, charY + 65),
        legPaint,
      );

      // Hands
      final handPaint = Paint()
        ..color = const Color(0xFFFFD1A4)
        ..strokeWidth = 8
        ..strokeCap = StrokeCap.round;

      canvas.drawLine(
        Offset(charX - 16, charY - 10),
        Offset(charX - 30, charY + 10 + handAngle * 15),
        handPaint,
      );
      canvas.drawLine(
        Offset(charX + 16, charY - 10),
        Offset(charX + 32, charY + 5 - handAngle * 15),
        handPaint,
      );

      // Speech Bubble (Gap Puffagi)
      final bubbleCenter = Offset(charX + 50, charY - 80);
      final bubbleRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: bubbleCenter, width: 140, height: 42),
        const Radius.circular(12),
      );
      canvas.drawRRect(bubbleRect, Paint()..color = Colors.white);
      
      final textPainter = TextPainter(
        text: const TextSpan(
          text: "MUHASIB POS - Tez!",
          style: TextStyle(
            color: Colors.black,
            fontSize: 12,
            fontWeight: FontWeight.bold,
          ),
        ),
        textDirection: TextDirection.ltr,
      );
      textPainter.layout();
      textPainter.paint(canvas, Offset(bubbleCenter.dx - 55, bubbleCenter.dy - 8));
    } else {
      // Real Motion Segmentation Mode (Photorealistic Cutout Layer Simulation)
      final cutoutPaint = Paint()
        ..color = AppTheme.accentCyan.withOpacity(0.8)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.0;

      // Realistic Avatar Silhouette Card
      final cardRect = RRect.fromRectAndRadius(
        Rect.fromCenter(center: Offset(charX, charY), width: 100, height: 140),
        const Radius.circular(16),
      );

      canvas.drawRRect(
        cardRect,
        Paint()..color = AppTheme.accentCyan.withOpacity(0.15),
      );
      canvas.drawRRect(cardRect, cutoutPaint);

      // Neural Segmentation Joints (macOS Vision Layer Cutout points)
      final joints = [
        Offset(charX, charY - 40),
        Offset(charX - 25, charY - 10),
        Offset(charX + 25, charY - 10),
        Offset(charX, charY + 20),
        Offset(charX - 20, charY + 60),
        Offset(charX + 20, charY + 60),
      ];

      for (var j in joints) {
        canvas.drawCircle(j, 5, Paint()..color = AppTheme.accentGreen);
        canvas.drawCircle(j, 8, Paint()..color = AppTheme.accentGreen.withOpacity(0.3)..style = PaintingStyle.stroke);
      }

      // Layer Status Overlay Text
      final statusPainter = TextPainter(
        text: TextSpan(
          text: "Vision Cutout: Layer 1 (Person)\nBG Cleaned: True\nSEEK: ${(progress * 30).toStringAsFixed(1)}s",
          style: const TextStyle(
            color: AppTheme.accentCyan,
            fontSize: 11,
            fontFamily: 'monospace',
          ),
        ),
        textDirection: TextDirection.ltr,
      );
      statusPainter.layout();
      statusPainter.paint(canvas, Offset(20, 20));
    }

    // Overlay FPS and Frame Info
    final frameInfo = TextPainter(
      text: TextSpan(
        text: "FRAME: ${(progress * 900).toInt()} / 900 | 30 FPS | 1080p | SEEK(t) Engine",
        style: const TextStyle(
          color: Colors.white70,
          fontSize: 12,
          fontWeight: FontWeight.w600,
        ),
      ),
      textDirection: TextDirection.ltr,
    );
    frameInfo.layout();
    frameInfo.paint(canvas, Offset(w - 380, 20));
  }

  @override
  bool shouldRepaint(covariant MotionCanvasPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.mode != mode;
  }
}
