import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../models/product_model.dart';
import '../widgets/glass_card.dart';

class PosKassaView extends StatefulWidget {
  const PosKassaView({super.key});

  @override
  State<PosKassaView> createState() => _PosKassaViewState();
}

class _PosKassaViewState extends State<PosKassaView> {
  final List<ProductModel> _products = [
    ProductModel(id: '1', name: 'Energetik Ichimlik Flash', price: 12000, category: 'Ichimliklar', stock: 140, barcode: '4780001', icon: '🥤'),
    ProductModel(id: '2', name: 'Pepsi 1.5L', price: 14000, category: 'Ichimliklar', stock: 85, barcode: '4780002', icon: '🥤'),
    ProductModel(id: '3', name: 'Non Tandir', price: 4000, category: 'Oziq-ovqat', stock: 200, barcode: '4780003', icon: '🍞'),
    ProductModel(id: '4', name: 'Saryog\' Premium', price: 35000, category: 'Sut mahsulotlari', stock: 45, barcode: '4780004', icon: '🧈'),
    ProductModel(id: '5', name: 'Shokolad Milliy', price: 18000, category: 'Shirinliklar', stock: 90, barcode: '4780005', icon: '🍫'),
    ProductModel(id: '6', name: 'Choy Qora 100g', price: 15000, category: 'Oziq-ovqat', stock: 120, barcode: '4780006', icon: '☕'),
  ];

  final List<CartItem> _cart = [];
  String _selectedCategory = 'Barchasi';
  String _searchQuery = '';
  final TextEditingController _barcodeController = TextEditingController();

  void _addToCart(ProductModel product) {
    setState(() {
      final existingIndex = _cart.indexWhere((item) => item.product.id == product.id);
      if (existingIndex >= 0) {
        _cart[existingIndex].quantity++;
      } else {
        _cart.add(CartItem(product: product));
      }
    });
  }

  void _removeFromCart(int index) {
    setState(() {
      if (_cart[index].quantity > 1) {
        _cart[index].quantity--;
      } else {
        _cart.removeAt(index);
      }
    });
  }

  double get _cartTotal => _cart.fold(0, (sum, item) => sum + item.total);

  void _checkout() {
    if (_cart.isEmpty) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.cardBg,
        title: const Row(
          children: [
            Icon(Icons.check_circle, color: AppTheme.accentGreen),
            SizedBox(width: 10),
            Text("Chek Chop Etildi!", style: TextStyle(color: Colors.white)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text("Jami summa: ${_cartTotal.toStringAsFixed(0)} so'm", style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: AppTheme.accentCyan)),
            const SizedBox(height: 10),
            const Text("MUHASIB Kassa tizimi orqali to'lov muvaffaqiyatli amalga oshirildi.", style: TextStyle(color: AppTheme.textSecondary)),
          ],
        ),
        actions: [
          ElevatedButton(
            onPressed: () {
              setState(() {
                _cart.clear();
              });
              Navigator.pop(ctx);
            },
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryNeon),
            child: const Text("Yangi Savdo", style: TextStyle(color: Colors.white)),
          )
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final filteredProducts = _products.where((p) {
      final matchesCat = _selectedCategory == 'Barchasi' || p.category == _selectedCategory;
      final matchesSearch = p.name.toLowerCase().contains(_searchQuery.toLowerCase()) || p.barcode.contains(_searchQuery);
      return matchesCat && matchesSearch;
    }).toList();

    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Product Catalog (Left Side 65%)
        Expanded(
          flex: 65,
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // POS Header Stats Bar
                Row(
                  children: [
                    _buildStatMiniCard("Bugungi Savdo", "4,850,000 so'm", Icons.trending_up, AppTheme.accentGreen),
                    const SizedBox(width: 12),
                    _buildStatMiniCard("Sotilgan Cheklar", "142 ta", Icons.receipt_long, AppTheme.accentCyan),
                    const SizedBox(width: 12),
                    _buildStatMiniCard("Ombor Qoldig'i", "680 ta", Icons.inventory_2, AppTheme.accentYellow),
                  ],
                ),
                const SizedBox(height: 20),

                // Search & Barcode Row
                Row(
                  children: [
                    Expanded(
                      child: TextField(
                        onChanged: (val) => setState(() => _searchQuery = val),
                        style: const TextStyle(color: Colors.white),
                        decoration: InputDecoration(
                          hintText: "Shtrix-kod skanerlang yoki tovar nomini kiriting...",
                          prefixIcon: const Icon(Icons.qr_code_scanner, color: AppTheme.accentCyan),
                          filled: true,
                          fillColor: AppTheme.cardBg,
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: AppTheme.glassBorder)),
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    ElevatedButton.icon(
                      onPressed: () {
                        // Demo barcode scan action
                        if (_products.isNotEmpty) {
                          _addToCart(_products.first);
                        }
                      },
                      icon: const Icon(Icons.center_focus_strong, color: Colors.black),
                      label: const Text("SKANER QILISH", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.accentCyan,
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 20),

                // Category Selector
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: ['Barchasi', 'Ichimliklar', 'Oziq-ovqat', 'Sut mahsulotlari', 'Shirinliklar'].map((cat) {
                      final isSel = _selectedCategory == cat;
                      return Padding(
                        padding: const EdgeInsets.only(right: 8.0),
                        child: ChoiceChip(
                          label: Text(cat),
                          selected: isSel,
                          onSelected: (selected) {
                            if (selected) setState(() => _selectedCategory = cat);
                          },
                          selectedColor: AppTheme.primaryNeon,
                          backgroundColor: AppTheme.cardBg,
                          labelStyle: TextStyle(color: isSel ? Colors.white : AppTheme.textSecondary, fontWeight: isSel ? FontWeight.bold : FontWeight.normal),
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 20),

                // Products Grid
                GridView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: 3,
                    crossAxisSpacing: 14,
                    mainAxisSpacing: 14,
                    childAspectRatio: 1.2,
                  ),
                  itemCount: filteredProducts.length,
                  itemBuilder: (context, index) {
                    final product = filteredProducts[index];
                    return GlassCard(
                      onTap: () => _addToCart(product),
                      padding: const EdgeInsets.all(14),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Text(product.icon, style: const TextStyle(fontSize: 28)),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(color: Colors.black26, borderRadius: BorderRadius.circular(8)),
                                child: Text("Qoldiq: ${product.stock}", style: const TextStyle(fontSize: 10, color: AppTheme.textSecondary)),
                              ),
                            ],
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(product.name, style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white, fontSize: 14), maxLines: 1, overflow: TextOverflow.ellipsis),
                              const SizedBox(height: 4),
                              Text("${product.price.toStringAsFixed(0)} so'm", style: const TextStyle(color: AppTheme.accentGreen, fontWeight: FontWeight.bold, fontSize: 13)),
                            ],
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ],
            ),
          ),
        ),

        // Cart / Checkout Panel (Right Side 35%)
        Expanded(
          flex: 35,
          child: Container(
            height: double.infinity,
            decoration: const BoxDecoration(
              color: AppTheme.sidebarBg,
              border: Border(left: BorderSide(color: AppTheme.glassBorder)),
            ),
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.shopping_cart, color: AppTheme.accentCyan),
                    SizedBox(width: 10),
                    Text("Joriy Kassa Cheki", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Colors.white)),
                  ],
                ),
                const SizedBox(height: 16),

                // Cart items list
                Expanded(
                  child: _cart.isEmpty
                      ? const Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.remove_shopping_cart, size: 48, color: AppTheme.textMuted),
                              SizedBox(height: 12),
                              Text("Savatcha bo'sh\nTovarlarni tanlang", textAlign: TextAlign.center, style: TextStyle(color: AppTheme.textMuted)),
                            ],
                          ),
                        )
                      : ListView.builder(
                          itemCount: _cart.length,
                          itemBuilder: (context, index) {
                            final item = _cart[index];
                            return Container(
                              margin: const EdgeInsets.only(bottom: 8),
                              padding: const EdgeInsets.all(10),
                              decoration: BoxDecoration(
                                color: AppTheme.cardBg,
                                borderRadius: BorderRadius.circular(10),
                                border: Border.all(color: AppTheme.glassBorder),
                              ),
                              child: Row(
                                children: [
                                  Text(item.product.icon, style: const TextStyle(fontSize: 20)),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(item.product.name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 13), maxLines: 1, overflow: TextOverflow.ellipsis),
                                        Text("${item.product.price.toStringAsFixed(0)} so'm", style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11)),
                                      ],
                                    ),
                                  ),
                                  Row(
                                    children: [
                                      IconButton(
                                        icon: const Icon(Icons.remove_circle_outline, size: 18, color: AppTheme.accentPink),
                                        onPressed: () => _removeFromCart(index),
                                      ),
                                      Text("${item.quantity}", style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                                      IconButton(
                                        icon: const Icon(Icons.add_circle_outline, size: 18, color: AppTheme.accentGreen),
                                        onPressed: () => _addToCart(item.product),
                                      ),
                                    ],
                                  ),
                                ],
                              ),
                            );
                          },
                        ),
                ),

                const Divider(),
                const SizedBox(height: 10),

                // Total Summary
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text("JAMI:", style: TextStyle(fontSize: 16, color: AppTheme.textSecondary)),
                    Text(
                      "${_cartTotal.toStringAsFixed(0)} so'm",
                      style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: AppTheme.accentGreen),
                    ),
                  ],
                ),
                const SizedBox(height: 16),

                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: ElevatedButton.icon(
                    onPressed: _cart.isEmpty ? null : _checkout,
                    icon: const Icon(Icons.print, color: Colors.black),
                    label: const Text("CHEK CHOP ETISH & TO'LOV", style: TextStyle(color: Colors.black, fontWeight: FontWeight.bold, fontSize: 15)),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.accentGreen,
                      disabledBackgroundColor: Colors.grey.shade800,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildStatMiniCard(String title, String value, IconData icon, Color color) {
    return Expanded(
      child: GlassCard(
        padding: const EdgeInsets.all(14),
        backgroundColor: color.withOpacity(0.08),
        borderColor: color.withOpacity(0.3),
        child: Row(
          children: [
            Icon(icon, color: color, size: 28),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
                const SizedBox(height: 2),
                Text(value, style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: color)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
