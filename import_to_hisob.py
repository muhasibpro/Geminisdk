import openpyxl
import hisob

wb = openpyxl.load_workbook("mahsulotlar_10.xlsx")
ws = wb.active

ombor_nomi = "Abdurahim ombori"
kiritildi = []

for row in list(ws.iter_rows(values_only=True))[1:]:
    num, barkod, nom, miqdor, birlik, kirim, sotuv, jami = row
    if not num or num == "JAMI":
        continue
    
    miq = float(miqdor)
    kr_narx = float(kirim)
    tot_summa = round(miq * kr_narx, 2)
    
    res = hisob.amal_qoshish(
        tur="xarid",
        tovar=nom,
        miqdor=miq,
        birlik=str(birlik),
        narx=kr_narx,
        summa=tot_summa,
        kim="Abdurahim",
        ga_ombor=ombor_nomi,
        barkod=str(barkod),
        valyuta="USD",
        izoh=f"Excel prixod: {ombor_nomi}"
    )
    kiritildi.append(res)

print(f"Muvaffaqiyatli {len(kiritildi)} ta mahsulot '{ombor_nomi}'ga kirim qilindi!")
