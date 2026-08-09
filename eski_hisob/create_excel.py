import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import datetime

# Create workbook and sheet
wb = openpyxl.Workbook()
ws = wb.active
ws.title = "Mahsulotlar"
ws.views.sheetView[0].showGridLines = True

# --- Theme & Style Definitions ---
COLOR_HEADER_BG = '1E293B'      # Slate 800
COLOR_HEADER_TEXT = 'FFFFFF'
COLOR_SUBTITLE = '94A3B8'

COLOR_KPI_BG = 'F8FAFC'          # Light Slate
COLOR_KPI_BORDER = 'CBD5E1'

COLOR_TBL_HEADER_BG = '1A73E8'   # POS Primary Blue
COLOR_TBL_HEADER_TEXT = 'FFFFFF'

COLOR_ZEBRA = 'F8FAFC'
COLOR_BORDER = 'E2E8F0'

# Fonts
font_title = Font(name='Arial', size=16, bold=True, color=COLOR_HEADER_TEXT)
font_subtitle = Font(name='Arial', size=10, italic=True, color=COLOR_SUBTITLE)

font_kpi_label = Font(name='Arial', size=9, bold=True, color='64748B')
font_kpi_val = Font(name='Arial', size=13, bold=True, color='0F172A')

font_tbl_header = Font(name='Arial', size=10, bold=True, color=COLOR_TBL_HEADER_TEXT)
font_data = Font(name='Arial', size=10, color='1E293B')
font_barcode = Font(name='Courier New', size=10, bold=True, color='1E40AF')
font_total_label = Font(name='Arial', size=11, bold=True, color='0F172A')
font_total_val = Font(name='Arial', size=11, bold=True, color='15803D')

# Fills
fill_header = PatternFill(start_color=COLOR_HEADER_BG, end_color=COLOR_HEADER_BG, fill_type='solid')
fill_tbl_header = PatternFill(start_color=COLOR_TBL_HEADER_BG, end_color=COLOR_TBL_HEADER_BG, fill_type='solid')
fill_zebra = PatternFill(start_color=COLOR_ZEBRA, end_color=COLOR_ZEBRA, fill_type='solid')
fill_kpi = PatternFill(start_color=COLOR_KPI_BG, end_color=COLOR_KPI_BG, fill_type='solid')

# Status Fills & Fonts
status_styles = {
    "Yetarli": {
        "fill": PatternFill(start_color='DCFCE7', end_color='DCFCE7', fill_type='solid'),
        "font": Font(name='Arial', size=10, bold=True, color='166534')
    },
    "Kam qoldi": {
        "fill": PatternFill(start_color='FFEDD5', end_color='FFEDD5', fill_type='solid'),
        "font": Font(name='Arial', size=10, bold=True, color='9A3412')
    },
    "Tugagan": {
        "fill": PatternFill(start_color='FEE2E2', end_color='FEE2E2', fill_type='solid'),
        "font": Font(name='Arial', size=10, bold=True, color='991B1B')
    }
}

# Borders
border_thin = Border(
    left=Side(style='thin', color=COLOR_BORDER),
    right=Side(style='thin', color=COLOR_BORDER),
    top=Side(style='thin', color=COLOR_BORDER),
    bottom=Side(style='thin', color=COLOR_BORDER)
)
border_kpi = Border(
    left=Side(style='thin', color=COLOR_KPI_BORDER),
    right=Side(style='thin', color=COLOR_KPI_BORDER),
    top=Side(style='thin', color=COLOR_KPI_BORDER),
    bottom=Side(style='thin', color=COLOR_KPI_BORDER)
)
border_tbl_header = Border(
    left=Side(style='thin', color='1557B0'),
    right=Side(style='thin', color='1557B0'),
    top=Side(style='medium', color='1557B0'),
    bottom=Side(style='medium', color='1557B0')
)
border_total = Border(
    top=Side(style='medium', color='1A73E8'),
    bottom=Side(style='double', color='1A73E8'),
    left=Side(style='thin', color=COLOR_BORDER),
    right=Side(style='thin', color=COLOR_BORDER)
)

# --- 1. Title Block ---
ws.merge_cells('A1:J1')
title_cell = ws['A1']
title_cell.value = "MUHASIB POS — Maxsulotlar va Qoldiqlar Hisoboti"
title_cell.font = font_title
title_cell.fill = fill_header
title_cell.alignment = Alignment(horizontal='center', vertical='center')
ws.row_dimensions[1].height = 36

# Subtitle / Metadata
ws.merge_cells('A2:J2')
sub_cell = ws['A2']
now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
sub_cell.value = f"Sana: {now_str}  |  Kassa: #1 (Asosiy Ombor)  |  Avtomatik shakllantirilgan Excel hisoboti"
sub_cell.font = font_subtitle
sub_cell.fill = fill_header
sub_cell.alignment = Alignment(horizontal='center', vertical='center')
ws.row_dimensions[2].height = 20

# Row 3 is spacer
ws.row_dimensions[3].height = 10

# --- 2. KPI Cards Block (Rows 4 & 5) ---
kpis = [
    ('A4:B4', 'A5:B5', 'JAMI MAHSULOT TURLARI', '=COUNTA(C8:C22)', '#,##0 "turdagi"'),
    ('C4:D4', 'C5:D5', 'UMUMIY OMBOR QOLDIG\'I', '=SUM(H8:H22)', '#,##0 "dona/kg"'),
    ('E4:G4', 'E5:G5', 'OMBOR UMUMIY QIYMATI', '=SUM(I8:I22)', '#,##0 "so\'m"'),
    ('H4:J4', 'H5:J5', 'KAM QOLGAN TOVARLAR', '=COUNTIF(H8:H22, "<=10")', '#,##0 "ta tovar"'),
]

for top_range, val_range, label, formula, num_fmt in kpis:
    ws.merge_cells(top_range)
    ws.merge_cells(val_range)
    
    top_left = ws[top_range.split(':')[0]]
    val_left = ws[val_range.split(':')[0]]
    
    top_left.value = label
    top_left.font = font_kpi_label
    top_left.alignment = Alignment(horizontal='center', vertical='center')
    
    val_left.value = formula
    val_left.font = font_kpi_val
    val_left.number_format = num_fmt
    val_left.alignment = Alignment(horizontal='center', vertical='center')
    
    # Border for KPI card
    cols = range(openpyxl.utils.column_index_from_string(top_range[0]), openpyxl.utils.column_index_from_string(top_range.split(':')[1][0]) + 1)
    for r in [4, 5]:
        for c in cols:
            cell = ws.cell(row=r, column=c)
            cell.fill = fill_kpi
            cell.border = border_kpi

ws.row_dimensions[4].height = 18
ws.row_dimensions[5].height = 24
ws.row_dimensions[6].height = 12

# --- 3. Table Headers (Row 7) ---
headers = [
    "№", "Shtrix-kod (Barcode)", "Maxsulot Nomi", "Kategoriya",
    "Birlik", "Keltirilgan Narx", "Sotish Narxi", "Qoldiq (Soni)",
    "Umumiy Qiymat", "Holat"
]
ws.row_dimensions[7].height = 28

for col_idx, header in enumerate(headers, 1):
    cell = ws.cell(row=7, column=col_idx, value=header)
    cell.fill = fill_tbl_header
    cell.font = font_tbl_header
    cell.alignment = Alignment(horizontal='center', vertical='center')
    cell.border = border_tbl_header

# --- 4. Products Data (Rows 8 to 22) ---
products = [
    (1, "4780001234015", "Coca-Cola 1.5L", "Ichimliklar", "dona", 11000, 14000, 85),
    (2, "4780001234022", "Pepsi 1.0L", "Ichimliklar", "dona", 8500, 11000, 120),
    (3, "4780001234039", "Nestlé Sut 1L (3.2%)", "Sut mahsulotlari", "dona", 13500, 16500, 42),
    (4, "4780001234046", "Musaffo Smetana 200g", "Sut mahsulotlari", "dona", 9000, 12000, 8),
    (5, "4780001234053", "Lays Kartoshka Chipsi 140g", "Sneklar", "dona", 14000, 18000, 65),
    (6, "4780001234060", "Cheetos Pishloqli 80g", "Sneklar", "dona", 6000, 8500, 4),
    (7, "4780001234077", "Nescafe Gold Qahva 100g", "Qahva va Choy", "dona", 36000, 45000, 18),
    (8, "4780001234084", "Greenfield Choy Qora 100g", "Qahva va Choy", "dona", 17000, 22000, 30),
    (9, "4780001234091", "Snickers Shokolad 50g", "Shirinliklar", "dona", 6500, 8500, 150),
    (10, "4780001234107", "Alpen Gold Shokolad 90g", "Shirinliklar", "dona", 9500, 12500, 0),
    (11, "4780001234114", "Dinay Tabiiy Shira 1L", "Ichimliklar", "dona", 11500, 15000, 24),
    (12, "4780001234121", "Bobi Guruch Alanga 1kg", "Oziq-ovqat", "kg", 19000, 24000, 210),
    (13, "4780001234138", "Makfa Makaron 500g", "Oziq-ovqat", "dona", 7500, 10000, 95),
    (14, "4780001234145", "Ariel Kir Yuvish Kukun 3kg", "Maishiy kimyo", "dona", 68000, 85000, 14),
    (15, "4780001234152", "Fairy Idish Yuvish Gel 500ml", "Maishiy kimyo", "dona", 16000, 21000, 6),
]

start_row = 8
for i, row_data in enumerate(products):
    current_row = start_row + i
    ws.row_dimensions[current_row].height = 22
    is_even = (i % 2 == 1)
    
    num, barcode, p_name, cat, unit, cost, price, stock = row_data
    
    # Values
    ws.cell(row=current_row, column=1, value=num)
    ws.cell(row=current_row, column=2, value=barcode)
    ws.cell(row=current_row, column=3, value=p_name)
    ws.cell(row=current_row, column=4, value=cat)
    ws.cell(row=current_row, column=5, value=unit)
    ws.cell(row=current_row, column=6, value=cost)
    ws.cell(row=current_row, column=7, value=price)
    ws.cell(row=current_row, column=8, value=stock)
    
    # Total Value Formula: Sotish Narxi * Qoldiq
    ws.cell(row=current_row, column=9, value=f"=G{current_row}*H{current_row}")
    
    # Status Formula logic check in python for cell styling
    if stock == 0:
        status_str = "Tugagan"
    elif stock <= 10:
        status_str = "Kam qoldi"
    else:
        status_str = "Yetarli"
        
    ws.cell(row=current_row, column=10, value=status_str)
    
    # Styling row cells
    for col_idx in range(1, 11):
        cell = ws.cell(row=current_row, column=col_idx)
        cell.border = border_thin
        cell.font = font_data
        
        if is_even:
            cell.fill = fill_zebra
            
        # Alignments & Formatting
        if col_idx in [1, 5]:  # №, Unit
            cell.alignment = Alignment(horizontal='center', vertical='center')
        elif col_idx == 2:  # Barcode
            cell.number_format = '@'
            cell.font = font_barcode
            cell.alignment = Alignment(horizontal='center', vertical='center')
        elif col_idx in [3, 4]:  # Name, Category
            cell.alignment = Alignment(horizontal='left', vertical='center')
        elif col_idx in [6, 7, 9]:  # Cost, Price, Total Value
            cell.number_format = '#,##0 "so\'m"'
            cell.alignment = Alignment(horizontal='right', vertical='center')
        elif col_idx == 8:  # Stock
            cell.number_format = '#,##0'
            cell.alignment = Alignment(horizontal='right', vertical='center')
        elif col_idx == 10:  # Status
            cell.alignment = Alignment(horizontal='center', vertical='center')
            st_style = status_styles.get(status_str, status_styles["Yetarli"])
            cell.fill = st_style["fill"]
            cell.font = st_style["font"]

# --- 5. Total Summary Row (Row 23) ---
tot_row = start_row + len(products)
ws.row_dimensions[tot_row].height = 26

ws.merge_cells(start_row=tot_row, start_column=1, end_row=tot_row, end_column=5)
tot_label = ws.cell(row=tot_row, column=1, value="Jami / O'rtacha Ko'rsatkichlar:")
tot_label.font = font_total_label
tot_label.alignment = Alignment(horizontal='right', vertical='center')

# Average Cost
cell_avg_cost = ws.cell(row=tot_row, column=6, value=f"=AVERAGE(F8:F{tot_row-1})")
cell_avg_cost.number_format = '#,##0 "so\'m"'
cell_avg_cost.font = font_total_label
cell_avg_cost.alignment = Alignment(horizontal='right', vertical='center')

# Average Selling Price
cell_avg_price = ws.cell(row=tot_row, column=7, value=f"=AVERAGE(G8:G{tot_row-1})")
cell_avg_price.number_format = '#,##0 "so\'m"'
cell_avg_price.font = font_total_label
cell_avg_price.alignment = Alignment(horizontal='right', vertical='center')

# Total Stock
cell_tot_stock = ws.cell(row=tot_row, column=8, value=f"=SUM(H8:H{tot_row-1})")
cell_tot_stock.number_format = '#,##0'
cell_tot_stock.font = font_total_val
cell_tot_stock.alignment = Alignment(horizontal='right', vertical='center')

# Grand Total Inventory Value
cell_tot_val = ws.cell(row=tot_row, column=9, value=f"=SUM(I8:I{tot_row-1})")
cell_tot_val.number_format = '#,##0 "so\'m"'
cell_tot_val.font = font_total_val
cell_tot_val.alignment = Alignment(horizontal='right', vertical='center')

# Total Row Status Cell
ws.cell(row=tot_row, column=10, value="")

for c in range(1, 11):
    cell = ws.cell(row=tot_row, column=c)
    cell.border = border_total

# --- 6. Auto Column Width Adjustment ---
min_widths = {
    'A': 6,   # №
    'B': 20,  # Barcode
    'C': 30,  # Maxsulot Nomi
    'D': 20,  # Kategoriya
    'E': 10,  # Birlik
    'F': 18,  # Keltirilgan Narx
    'G': 18,  # Sotish Narxi
    'H': 16,  # Qoldiq (Soni)
    'I': 22,  # Umumiy Qiymat
    'J': 14   # Holat
}

for col_letter, width in min_widths.items():
    ws.column_dimensions[col_letter].width = width

file_path = "/Users/muhasibpro/Desktop/Geminisdk/mahsulotlar.xlsx"
wb.save(file_path)
print(f"✅ MUHASIB POS Excel hisoboti muvaffaqiyatli yangilandi: {file_path}")

