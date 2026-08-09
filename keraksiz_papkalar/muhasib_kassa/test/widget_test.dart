import 'package:flutter_test/flutter_test.dart';
import 'package:muhasib_kassa/main.dart';

void main() {
  testWidgets('App load test', (WidgetTester tester) async {
    await tester.pumpWidget(const MuhasibApp());
    expect(find.byType(MuhasibApp), findsOneWidget);
  });
}
