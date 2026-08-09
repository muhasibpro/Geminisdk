import 'dart:math';
import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class AudioWavePainter extends CustomPainter {
  final double animationValue;
  final Color waveColor;
  final bool isPlaying;

  AudioWavePainter({
    required this.animationValue,
    this.waveColor = AppTheme.accentCyan,
    this.isPlaying = true,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = waveColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3.0
      ..strokeCap = StrokeCap.round;

    final barCount = 40;
    final width = size.width;
    final height = size.height;
    final spacing = width / barCount;

    for (int i = 0; i < barCount; i++) {
      final x = i * spacing + spacing / 2;
      double factor = isPlaying
          ? sin((i * 0.3) + (animationValue * 2 * pi)) * 0.5 + 0.5
          : 0.15;
      
      // Enhance center frequencies
      double centerFactor = sin(i / barCount * pi);
      double barHeight = max(6.0, height * factor * centerFactor * 0.85);

      final topY = (height - barHeight) / 2;
      final bottomY = topY + barHeight;

      final gradientPaint = Paint()
        ..shader = LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            waveColor,
            waveColor.withOpacity(0.4),
          ],
        ).createShader(Rect.fromLTRB(x, topY, x, bottomY))
        ..strokeWidth = 4.0
        ..strokeCap = StrokeCap.round;

      canvas.drawLine(Offset(x, topY), Offset(x, bottomY), gradientPaint);
    }
  }

  @override
  bool shouldRepaint(covariant AudioWavePainter oldDelegate) {
    return oldDelegate.animationValue != animationValue ||
        oldDelegate.isPlaying != isPlaying ||
        oldDelegate.waveColor != waveColor;
  }
}
