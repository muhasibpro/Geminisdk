import 'product.dart';

class CartItem {
  final Product product;
  int quantity;

  CartItem({
    required this.product,
    this.quantity = 1,
  });

  double get totalPrice => product.sellPrice * quantity;
  double get totalBuyPrice => product.buyPrice * quantity;
  double get totalProfit => totalPrice - totalBuyPrice;
}
