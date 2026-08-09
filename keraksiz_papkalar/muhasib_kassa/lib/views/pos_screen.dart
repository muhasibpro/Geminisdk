import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/product.dart';
import '../models/cart_item.dart';

class PosScreen extends StatefulWidget {
  final List<Product> products;
  final Function(Product) onProductSold;

  const PosScreen({
    super.key,
    required this.products,
    required this.onProductSold,
  });

  @override
  State<PosScreen> createState() => _PosScreenState();
}

class _PosScreenState extends State<PosScreen> {
  final List<CartItem> _cart = [];
  final TextEditingController _barcodeController = TextEditingController();
  final currencyFormat = NumberFormat("#,##0", "uz_UZ");

  double get _totalPrice => _cart.fold(0, (sum, item) => sum + item.totalPrice);

  void _addToCart(Product product) {
    setState(() {
      final index = _cart.indexWhere((item) => item.product.id == product.id);
      if (index >= 0) {
        if (_cart[index].quantity < product.quantity) {
          _cart[index].quantity++;
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('⚠️ Omborda yetarli tovar yo\'q!'), backgroundColor: Colors.orange),
          );
        }
      } else {
        if (product.quantity > 0) {
          _cart.add(CartItem(product: product));
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('⚠️ Tovar zaxirasi tugagan!'), backgroundColor: Colors.red),
          );
        }
      }
    });
  }

  void _scanBarcode(String barcode) {
    if (barcode.trim().isEmpty) return;
    final product = widget.products.firstWhere(
      (p) => p.barcode == barcode.trim(),
      orElse: () => Product(id: '', name: '', barcode: '', buyPrice: 0, sellPrice: 0, quantity: 0),
    );

    if (product.id.isNotEmpty) {
      _addToCart(product);
      _barcodeController.clear();
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('❌ Barcode bo\'yicha tovar topilmadi: $barcode'), backgroundColor: Colors.redAccent),
      );
    }
  }

  void _finishSale() {
    if (_cart.isEmpty) return;

    final saleTotal = _totalPrice;
    final soldItemsCount = _cart.fold(0, (sum, i) => sum + i.quantity);

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1E293B),
        title: const Row(
          children: [
            Icon(Icons.check_circle, color: Color(0xFF10B981), size: 28),
            SizedBox(width: 10),
            Text('Savdo Yakunlandi!', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Jami tovarlar soni: $soldItemsCount ta', style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: 8),
            Text(
              'Umumiy Summa: ${currencyFormat.format(saleTotal)} so\'m',
              style: const TextStyle(color: Color(0xFF10B981), fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const Divider(color: Colors.grey, height: 24),
            const Text('Chek tafsilotlari:', style: TextStyle(color: Colors.grey, fontSize: 12)),
            const SizedBox(height: 6),
            ..._cart.map((i) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2.0),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text('${i.product.name} x${i.quantity}', style: const TextStyle(color: Colors.white)),
                      Text('${currencyFormat.format(i.totalPrice)} so\'m', style: const TextStyle(color: Colors.white70)),
                    ],
                  ),
                )),
          ],
        ),
        actions: [
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF10B981)),
            onPressed: () {
              setState(() {
                _cart.clear();
              });
              Navigator.pop(ctx);
            },
            child: const Text('OK', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0F172A),
      body: Row(
        children: [
          // Left: Products Grid / Quick Select
          Expanded(
            flex: 6,
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  // Barcode Scan Field
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _barcodeController,
                          onSubmitted: _scanBarcode,
                          autofocus: true,
                          style: const TextStyle(color: Colors.white),
                          decoration: InputDecoration(
                            hintText: 'Shtrixkod skanerlang yoki kiriting...',
                            hintStyle: const TextStyle(color: Colors.grey),
                            prefixIcon: const Icon(Icons.qr_code_scanner, color: Color(0xFF10B981)),
                            filled: true,
                            fillColor: const Color(0xFF1E293B),
                            border: OutlineInputBorder(
                              borderRadius: BorderRadius.circular(10),
                              borderSide: BorderSide.none,
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        onPressed: () => _scanBarcode(_barcodeController.text),
                        icon: const Icon(Icons.search, color: Colors.white),
                        style: IconButton.styleFrom(
                          backgroundColor: const Color(0xFF10B981),
                          padding: const EdgeInsets.all(14),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),

                  // Products Grid
                  Expanded(
                    child: GridView.builder(
                      gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                        maxCrossAxisExtent: 220,
                        childAspectRatio: 1.1,
                        crossAxisSpacing: 12,
                        mainAxisSpacing: 12,
                      ),
                      itemCount: widget.products.length,
                      itemBuilder: (ctx, idx) {
                        final p = widget.products[idx];
                        return InkWell(
                          onTap: () => _addToCart(p),
                          borderRadius: BorderRadius.circular(12),
                          child: Container(
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFF1E293B),
                              borderRadius: BorderRadius.circular(12),
                              border: Border.all(color: const Color(0xFF334155)),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      p.name,
                                      style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      p.barcode,
                                      style: const TextStyle(color: Colors.grey, fontSize: 11, fontFamily: 'monospace'),
                                    ),
                                  ],
                                ),
                                Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    Text(
                                      '${currencyFormat.format(p.sellPrice)} so\'m',
                                      style: const TextStyle(color: Color(0xFF10B981), fontWeight: FontWeight.bold, fontSize: 13),
                                    ),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: const Color(0xFF0F172A),
                                        borderRadius: BorderRadius.circular(4),
                                      ),
                                      child: Text(
                                        '${p.quantity} ta',
                                        style: const TextStyle(color: Colors.white70, fontSize: 11),
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),

          // Right: Cart Panel
          Container(
            width: 360,
            color: const Color(0xFF1E293B),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  color: const Color(0xFF0F172A),
                  child: const Row(
                    children: [
                      Icon(Icons.shopping_cart, color: Color(0xFF10B981)),
                      SizedBox(width: 8),
                      Text('Xarid Savati', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
                    ],
                  ),
                ),

                // Cart items list
                Expanded(
                  child: _cart.isEmpty
                      ? const Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Icon(Icons.remove_shopping_cart, color: Colors.grey, size: 48),
                              SizedBox(height: 8),
                              Text('Savat hozircha bo\'sh', style: TextStyle(color: Colors.grey)),
                            ],
                          ),
                        )
                      : ListView.separated(
                          padding: const EdgeInsets.all(12),
                          itemCount: _cart.length,
                          separatorBuilder: (ctx, i) => const Divider(color: Color(0xFF334155)),
                          itemBuilder: (ctx, idx) {
                            final item = _cart[idx];
                            return Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      Text(item.product.name, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                      Text('${currencyFormat.format(item.product.sellPrice)} so\'m', style: const TextStyle(color: Colors.grey, fontSize: 12)),
                                    ],
                                  ),
                                ),
                                Row(
                                  children: [
                                    IconButton(
                                      icon: const Icon(Icons.remove_circle_outline, color: Colors.redAccent, size: 20),
                                      onPressed: () {
                                        setState(() {
                                          if (item.quantity > 1) {
                                            item.quantity--;
                                          } else {
                                            _cart.removeAt(idx);
                                          }
                                        });
                                      },
                                    ),
                                    Text('${item.quantity}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
                                    IconButton(
                                      icon: const Icon(Icons.add_circle_outline, color: Colors.greenAccent, size: 20),
                                      onPressed: () {
                                        setState(() {
                                          if (item.quantity < item.product.quantity) {
                                            item.quantity++;
                                          }
                                        });
                                      },
                                    ),
                                  ],
                                ),
                              ],
                            );
                          },
                        ),
                ),

                // Cart Total & Checkout Button
                Container(
                  padding: const EdgeInsets.all(16),
                  color: const Color(0xFF0F172A),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('Jami summa:', style: TextStyle(color: Colors.grey, fontSize: 16)),
                          Text(
                            '${currencyFormat.format(_totalPrice)} so\'m',
                            style: const TextStyle(color: Color(0xFF10B981), fontSize: 20, fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      SizedBox(
                        width: double.infinity,
                        height: 50,
                        child: ElevatedButton.icon(
                          onPressed: _cart.isNotEmpty ? _finishSale : null,
                          icon: const Icon(Icons.payment, color: Colors.white),
                          label: const Text('SAVDONI YAKUNLASH', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF10B981),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
