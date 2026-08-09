import 'package:flutter_test/flutter_test.dart';
import 'package:muhasib_app/main.dart';

void main() {
  testWidgets('App load test', (WidgetTester tester) async {
    await tester.pumpWidget(const MuhasibAntigravityApp());
    expect(find.text('ANTIGRAVITY'), findsOneWidget);
  });
}
