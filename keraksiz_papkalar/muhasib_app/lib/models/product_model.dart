class ProductModel {
  final String id;
  final String name;
  final double price;
  final String category;
  final int stock;
  final String barcode;
  final String icon;

  ProductModel({
    required this.id,
    required this.name,
    required this.price,
    required this.category,
    required this.stock,
    required this.barcode,
    required this.icon,
  });
}

class CartItem {
  final ProductModel product;
  int quantity;

  CartItem({required this.product, this.quantity = 1});

  double get total => product.price * quantity;
}
