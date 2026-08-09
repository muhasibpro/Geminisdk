import 'dart:io';
import 'package:excel/excel.dart';
import 'package:file_picker/file_picker.dart';
import 'package:path_provider/path_provider.dart';
import '../models/product.dart';

class ExcelService {
  /// Import products from an Excel file selected by user or custom path
  static Future<List<Product>> importFromExcel([String? filePath]) async {
    List<Product> products = [];
    
    String? targetPath = filePath;
    if (targetPath == null) {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['xlsx', 'xls'],
      );
      if (result != null && result.files.single.path != null) {
        targetPath = result.files.single.path;
      }
    }

    if (targetPath == null) return products;

    var bytes = File(targetPath).readAsBytesSync();
    var excel = Excel.decodeBytes(bytes);

    for (var table in excel.tables.keys) {
      var sheet = excel.tables[table];
      if (sheet == null) continue;

      bool headersFound = false;
      int nameCol = 1;
      int barcodeCol = 2;
      int priceCol = 3;

      for (var row in sheet.rows) {
        if (row.isEmpty) continue;

        List<String> rowValues = row.map((cell) => cell?.value?.toString().trim() ?? '').toList();
        
        if (!headersFound) {
          for (int i = 0; i < rowValues.length; i++) {
            String val = rowValues[i].toLowerCase();
            if (val.contains('nomi') || val.contains('tovar')) nameCol = i;
            if (val.contains('barcode') || val.contains('shtrix')) barcodeCol = i;
            if (val.contains('kirim') || val.contains('narx') || val.contains('narxi')) priceCol = i;
          }
          if (rowValues.any((val) => val.toLowerCase().contains('tovar') || val.toLowerCase().contains('narx'))) {
            headersFound = true;
          }
          continue;
        }

        if (rowValues.length > nameCol && rowValues[nameCol].isNotEmpty) {
          String name = rowValues[nameCol];
          if (name.toLowerCase().contains('jami') || name.toLowerCase().contains('umumiy')) continue;

          String barcode = rowValues.length > barcodeCol ? rowValues[barcodeCol] : '';
          
          String priceStr = rowValues.length > priceCol ? rowValues[priceCol] : '0';
          priceStr = priceStr.replaceAll(RegExp(r'[^0-9.]'), '');
          double buyPrice = double.tryParse(priceStr) ?? 0.0;
          double sellPrice = (buyPrice * 1.25).roundToDouble();

          if (name.isNotEmpty && buyPrice > 0) {
            products.add(Product(
              id: DateTime.now().microsecondsSinceEpoch.toString() + products.length.toString(),
              name: name,
              barcode: barcode.isEmpty ? '47800${100000 + products.length}' : barcode,
              buyPrice: buyPrice,
              sellPrice: sellPrice,
              quantity: 50,
            ));
          }
        }
      }
    }
    return products;
  }

  /// Export list of products to Excel file
  static Future<String?> exportToExcel(List<Product> products) async {
    var excel = Excel.createExcel();
    Sheet sheetObject = excel['Tovarlar'];
    excel.delete('Sheet1');

    CellStyle headerStyle = CellStyle(
      bold: true,
    );

    sheetObject.appendRow([
      TextCellValue('№'),
      TextCellValue('Tovar nomi'),
      TextCellValue('Shtrixkod (Barcode)'),
      TextCellValue('Kirim narxi (so\'m)'),
      TextCellValue('Sotish narxi (so\'m)'),
      TextCellValue('Soni (Omborda)'),
    ]);

    for (int col = 0; col < 6; col++) {
      sheetObject.cell(CellIndex.indexByColumnRow(columnIndex: col, rowIndex: 0)).cellStyle = headerStyle;
    }

    for (int i = 0; i < products.length; i++) {
      var p = products[i];
      sheetObject.appendRow([
        IntCellValue(i + 1),
        TextCellValue(p.name),
        TextCellValue(p.barcode),
        DoubleCellValue(p.buyPrice),
        DoubleCellValue(p.sellPrice),
        IntCellValue(p.quantity),
      ]);
    }

    Directory? appDocDir;
    if (Platform.isMacOS || Platform.isWindows || Platform.isLinux) {
      appDocDir = await getDownloadsDirectory() ?? await getApplicationDocumentsDirectory();
    } else {
      appDocDir = await getApplicationDocumentsDirectory();
    }

    String path = "${appDocDir.path}/MUHASIB_Tovarlar_${DateTime.now().millisecondsSinceEpoch}.xlsx";
    List<int>? fileBytes = excel.save();
    if (fileBytes != null) {
      File(path)
        ..createSync(recursive: true)
        ..writeAsBytesSync(fileBytes);
      return path;
    }
    return null;
  }
}
