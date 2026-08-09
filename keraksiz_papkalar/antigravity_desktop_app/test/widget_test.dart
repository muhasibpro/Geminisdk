import 'package:flutter_test/flutter_test.dart';
import 'package:antigravity_desktop_app/main.dart';

void main() {
  testWidgets('App load test', (WidgetTester tester) async {
    await tester.pumpWidget(const AntigravityRealDesktopApp());
    expect(find.text('ANTIGRAVITY'), findsOneWidget);
  });
}
