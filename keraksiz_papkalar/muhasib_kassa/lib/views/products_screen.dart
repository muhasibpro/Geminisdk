import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/product.dart';
import '../services/excel_service.dart';

class ProductsScreen extends StatefulWidget {
  final List<Product> products;
  final Function(Product) onAddProduct;
  final Function(Product) onUpdateProduct;
  final Function(String) onDeleteProduct;
  final Function(List<Product>) onImportProducts;

  const ProductsScreen({
    super.key,
    required this.products,
    required this.onAddProduct,
    required this.onUpdateProduct,
    required this.onDeleteProduct,
    required this.onImportProducts,
  });

  @override
  State<ProductsScreen> createState() => _ProductsScreenState();
}

class _ProductsScreenState extends State<ProductsScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _searchQuery = '';

  final currencyFormat = NumberFormat("#,##0", "uz_UZ");

  List<Product> get _filteredProducts {
    if (_searchQuery.isEmpty) return widget.products;
    return widget.products.where((p) {
      return p.name.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          p.barcode.contains(_searchQuery);
    }).toList();
  }

  double get _totalKirimSum {
    return widget.products.fold(0, (sum, p) => sum + (p.buyPrice * p.quantity));
  }

  double get _totalSotishSum {
    return widget.products.fold(0, (sum, p) => sum + (p.sellPrice * p.quantity));
  }

  void _showProductDialog([Product? product]) {
    final nameController = TextEditingController(text: product?.name ?? '');
    final barcodeController = TextEditingController(text: product?.barcode ?? '');
    final buyPriceController = TextEditingController(text: product?.buyPrice.toStringAsFixed(0) ?? '');
    final sellPriceController = TextEditingController(text: product?.sellPrice.toStringAsFixed(0) ?? '');
    final quantityController = TextEditingController(text: product?.quantity.toString() ?? '10');

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: Text(
          product == null ? '➕ Yangi Tovar Qo\'shish' : '✏️ Tovarni Tahrirlash',
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _buildTextField(nameController, 'Tovar nomi', Icons.shopping_bag_outlined),
              const SizedBox(height: 12),
              _buildTextField(barcodeController, 'Shtrixkod (Barcode)', Icons.qr_code_scanner),
              const SizedBox(height: 12),
              _buildTextField(buyPriceController, 'Kirim narxi (so\'m)', Icons.download_outlined, isNumber: true),
              const SizedBox(height: 12),
              _buildTextField(sellPriceController, 'Sotish narxi (so\'m)', Icons.sell_outlined, isNumber: true),
              const SizedBox(height: 12),
              _buildTextField(quantityController, 'Soni (Omborda)', Icons.inventory_2_outlined, isNumber: true),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Bekor qilish', style: TextStyle(color: Colors.grey)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF3B82F6),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
            ),
            onPressed: () {
              if (nameController.text.isEmpty) return;
              final double buyPrice = double.tryParse(buyPriceController.text) ?? 0.0;
              final double sellPrice = double.tryParse(sellPriceController.text) ?? (buyPrice * 1.2);
              final int quantity = int.tryParse(quantityController.text) ?? 1;

              final newProd = Product(
                id: product?.id ?? DateTime.now().millisecondsSinceEpoch.toString(),
                name: nameController.text.trim(),
                barcode: barcodeController.text.trim(),
                buyPrice: buyPrice,
                sellPrice: sellPrice,
                quantity: quantity,
              );

              if (product == null) {
                widget.onAddProduct(newProd);
              } else {
                widget.onUpdateProduct(newProd);
              }
              Navigator.pop(ctx);
            },
            child: Text(product == null ? 'Qo\'shish' : 'Saqlash', style: const TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String label, IconData icon, {bool isNumber = false}) {
    return TextField(
      controller: controller,
      keyboardType: isNumber ? TextInputType.number : TextInputType.text,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.grey),
        prefixIcon: Icon(icon, color: const Color(0xFF3B82F6)),
        enabledBorder: OutlineInputBorder(
          borderSide: const BorderSide(color: Color(0xFF334155)),
          borderRadius: BorderRadius.circular(8),
        ),
        focusedBorder: OutlineInputBorder(
          borderSide: const BorderSide(color: Color(0xFF3B82F6)),
          borderRadius: BorderRadius.circular(8),
        ),
        filled: true,
        fillColor: const Color(0xFF0F172A),
      ),
    );
  }

  Future<void> _handleImportExcel() async {
    final imported = await ExcelService.importFromExcel();
    if (imported.isNotEmpty) {
      widget.onImportProducts(imported);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('✅ Excel faylidan ${imported.length} ta tovar muvaffaqiyatli yuklandi!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    }
  }

  Future<void> _handleExportExcel() async {
    final path = await ExcelService.exportToExcel(widget.products);
    if (path != null && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('📁 Excel saqlandi: $path'),
          backgroundColor: Colors.blueAccent,
          duration: const Duration(seconds: 4),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            // Stats Summary Cards
            Row(
              children: [
                _buildStatCard('Tovarlar Turi', widget.products.length.toString(), Icons.inventory, Colors.blue),
                const SizedBox(width: 12),
                _buildStatCard('Kirim Summasi', '${currencyFormat.format(_totalKirimSum)} so\'m', Icons.arrow_downward, Colors.orange),
                const SizedBox(width: 12),
                _buildStatCard('Sotish Summasi', '${currencyFormat.format(_totalSotishSum)} so\'m', Icons.arrow_upward, Colors.green),
              ],
            ),
            const SizedBox(height: 16),

            // Toolbar: Search + Excel Actions + Add Button
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _searchController,
                    onChanged: (val) => setState(() => _searchQuery = val),
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: 'Tovar nomi yoki shtrixkod bo\'yicha qidiruv...',
                      hintStyle: const TextStyle(color: Colors.grey),
                      prefixIcon: const Icon(Icons.search, color: Color(0xFF3B82F6)),
                      filled: true,
                      fillColor: const Color(0xFF1E293B),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide.none,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: _handleImportExcel,
                  icon: const Icon(Icons.file_upload, color: Colors.white),
                  label: const Text('Excel Yuklash', style: TextStyle(color: Colors.white)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF10B981),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  onPressed: _handleExportExcel,
                  icon: const Icon(Icons.file_download, color: Colors.white),
                  label: const Text('Excel Saqlash', style: TextStyle(color: Colors.white)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF8B5CF6),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  onPressed: () => _showProductDialog(),
                  icon: const Icon(Icons.add, color: Colors.white),
                  label: const Text('Yangi Tovar', style: TextStyle(color: Colors.white)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF3B82F6),
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Table Header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFF1E293B),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Row(
                children: [
                  SizedBox(width: 40, child: Text('№', style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
                  Expanded(flex: 3, child: Text('Tovar nomi', style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
                  Expanded(flex: 2, child: Text('Shtrixkod', style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
                  Expanded(flex: 2, child: Text('Kirim narxi', style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
                  Expanded(flex: 2, child: Text('Sotish narxi', style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
                  SizedBox(width: 80, child: Text('Soni', style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
                  SizedBox(width: 80, child: Text('Amallar', style: TextStyle(color: Colors.grey, fontWeight: FontWeight.bold))),
                ],
              ),
            ),
            const SizedBox(height: 8),

            // Products List
            Expanded(
              child: ListView.separated(
                itemCount: _filteredProducts.length,
                separatorBuilder: (ctx, i) => const SizedBox(height: 6),
                itemBuilder: (ctx, index) {
                  final p = _filteredProducts[index];
                  return Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1E293B).withOpacity(0.6),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFF334155).withOpacity(0.5)),
                    ),
                    child: Row(
                      children: [
                        SizedBox(
                          width: 40,
                          child: Text('${index + 1}', style: const TextStyle(color: Colors.white70)),
                        ),
                        Expanded(
                          flex: 3,
                          child: Text(
                            p.name,
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                          ),
                        ),
                        Expanded(
                          flex: 2,
                          child: Row(
                            children: [
                              const Icon(Icons.qr_code, size: 16, color: Colors.blueAccent),
                              const SizedBox(width: 6),
                              Text(p.barcode, style: const TextStyle(color: Colors.white70, fontFamily: 'monospace')),
                            ],
                          ),
                        ),
                        Expanded(
                          flex: 2,
                          child: Text(
                            '${currencyFormat.format(p.buyPrice)} so\'m',
                            style: const TextStyle(color: Colors.orangeAccent, fontWeight: FontWeight.w600),
                          ),
                        ),
                        Expanded(
                          flex: 2,
                          child: Text(
                            '${currencyFormat.format(p.sellPrice)} so\'m',
                            style: const TextStyle(color: Colors.greenAccent, fontWeight: FontWeight.w600),
                          ),
                        ),
                        SizedBox(
                          width: 80,
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                            decoration: BoxDecoration(
                              color: const Color(0xFF334155),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: Text(
                              '${p.quantity} ta',
                              textAlign: TextAlign.center,
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
                            ),
                          ),
                        ),
                        SizedBox(
                          width: 80,
                          child: Row(
                            children: [
                              IconButton(
                                icon: const Icon(Icons.edit, color: Colors.blueAccent, size: 20),
                                onPressed: () => _showProductDialog(p),
                              ),
                              IconButton(
                                icon: const Icon(Icons.delete_outline, color: Colors.redAccent, size: 20),
                                onPressed: () => widget.onDeleteProduct(p.id),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatCard(String title, String value, IconData icon, Color color) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: const Color(0xFF1E293B),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: color.withOpacity(0.15),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: const TextStyle(color: Colors.grey, fontSize: 13)),
                  const SizedBox(height: 4),
                  Text(
                    value,
                    style: TextStyle(color: color, fontSize: 17, fontWeight: FontWeight.bold),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
