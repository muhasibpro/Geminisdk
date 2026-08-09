import 'package:flutter/material.dart';
import '../models/product.dart';
import 'products_screen.dart';
import 'pos_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _selectedIndex = 0;

  // Initial products with exact user Excel data
  final List<Product> _products = [
    Product(id: '1', name: 'Coca-Cola 1.5L', barcode: '4780000123456', buyPrice: 11500, sellPrice: 14000, quantity: 50),
    Product(id: '2', name: 'Pepsi 1.5L', barcode: '4780000123463', buyPrice: 11000, sellPrice: 13500, quantity: 45),
    Product(id: '3', name: 'Chortoq 0.5L (Gazli)', barcode: '4780000234567', buyPrice: 4500, sellPrice: 6000, quantity: 100),
    Product(id: '4', name: 'Nestle Sut 1L 3.2%', barcode: '4780000345678', buyPrice: 12000, sellPrice: 15000, quantity: 30),
    Product(id: '5', name: 'Lays Chipslari 140g', barcode: '4780000456789', buyPrice: 14500, sellPrice: 18000, quantity: 25),
    Product(id: '6', name: 'Crafers Shokolad 100g', barcode: '4780000567890', buyPrice: 9000, sellPrice: 12000, quantity: 40),
    Product(id: '7', name: 'Musaffo Sariyog\' 200g', barcode: '4780000678901', buyPrice: 22000, sellPrice: 26000, quantity: 20),
    Product(id: '8', name: 'MacCoffee 3in1 (1 dona)', barcode: '4780000789012', buyPrice: 2200, sellPrice: 3000, quantity: 200),
    Product(id: '9', name: 'Lipton Choy 100g', barcode: '4780000890123', buyPrice: 16500, sellPrice: 20000, quantity: 35),
    Product(id: '10', name: 'Dobriy Sharbat 1L', barcode: '4780000901234', buyPrice: 13000, sellPrice: 16000, quantity: 28),
  ];

  void _addProduct(Product p) {
    setState(() {
      _products.insert(0, p);
    });
  }

  void _updateProduct(Product updated) {
    setState(() {
      final index = _products.indexWhere((p) => p.id == updated.id);
      if (index >= 0) {
        _products[index] = updated;
      }
    });
  }

  void _deleteProduct(String id) {
    setState(() {
      _products.removeWhere((p) => p.id == id);
    });
  }

  void _importProducts(List<Product> imported) {
    setState(() {
      _products.addAll(imported);
    });
  }

  void _productSold(Product soldProduct) {
    setState(() {
      final index = _products.indexWhere((p) => p.id == soldProduct.id);
      if (index >= 0 && _products[index].quantity > 0) {
        _products[index].quantity--;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = [
      ProductsScreen(
        products: _products,
        onAddProduct: _addProduct,
        onUpdateProduct: _updateProduct,
        onDeleteProduct: _deleteProduct,
        onImportProducts: _importProducts,
      ),
      PosScreen(
        products: _products,
        onProductSold: _productSold,
      ),
    ];

    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF1E293B),
        elevation: 2,
        title: const Row(
          children: [
            Icon(Icons.point_of_sale, color: Color(0xFF3B82F6), size: 28),
            SizedBox(width: 10),
            Text(
              'MUHASIB POS — Tovar Boshqaruvi va Kassa',
              style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 18),
            ),
          ],
        ),
        actions: [
          Container(
            margin: const EdgeInsets.only(right: 16),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: const Color(0xFF10B981).withOpacity(0.2),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: const Color(0xFF10B981)),
            ),
            child: const Row(
              children: [
                Icon(Icons.circle, color: Color(0xFF10B981), size: 10),
                SizedBox(width: 6),
                Text('Tizim Faol', style: TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold, fontSize: 12)),
              ],
            ),
          ),
        ],
      ),
      body: pages[_selectedIndex],
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (idx) => setState(() => _selectedIndex = idx),
        backgroundColor: const Color(0xFF1E293B),
        selectedItemColor: const Color(0xFF3B82F6),
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.inventory_2),
            label: 'Tovarlar va Kirim (Excel)',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.point_of_sale),
            label: 'POS Kassa',
          ),
        ],
      ),
    );
  }
}
