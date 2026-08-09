class Product {
  String id;
  String name;
  String barcode;
  double buyPrice;  // Kirim narxi
  double sellPrice; // Sotish narxi
  int quantity;     // Ombordagi soni
  String category;

  Product({
    required this.id,
    required this.name,
    required this.barcode,
    required this.buyPrice,
    required this.sellPrice,
    required this.quantity,
    this.category = 'Umumiy',
  });

  Map<String, dynamic> toMap() {
    return {
      'id': id,
      'name': name,
      'barcode': barcode,
      'buyPrice': buyPrice,
      'sellPrice': sellPrice,
      'quantity': quantity,
      'category': category,
    };
  }

  factory Product.fromMap(Map<String, dynamic> map) {
    return Product(
      id: map['id'] ?? '',
      name: map['name'] ?? '',
      barcode: map['barcode'] ?? '',
      buyPrice: (map['buyPrice'] as num).toDouble(),
      sellPrice: (map['sellPrice'] as num).toDouble(),
      quantity: (map['quantity'] as num).toInt(),
      category: map['category'] ?? 'Umumiy',
    );
  }

  Product copyWith({
    String? id,
    String? name,
    String? barcode,
    double? buyPrice,
    double? sellPrice,
    int? quantity,
    String? category,
  }) {
    return Product(
      id: id ?? this.id,
      name: name ?? this.name,
      barcode: barcode ?? this.barcode,
      buyPrice: buyPrice ?? this.buyPrice,
      sellPrice: sellPrice ?? this.sellPrice,
      quantity: quantity ?? this.quantity,
      category: category ?? this.category,
    );
  }
}
