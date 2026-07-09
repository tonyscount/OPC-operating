import 'package:flutter_test/flutter_test.dart';
import 'package:opc_app/app.dart';

void main() {
  testWidgets('App renders without crashing', (WidgetTester tester) async {
    await tester.pumpWidget(const OPCApp());
    // Just verify the widget tree builds without errors
    expect(find.byType(OPCApp), findsOneWidget);
  });
}
