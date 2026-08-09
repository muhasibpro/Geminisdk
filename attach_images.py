import hisob

images_mapping = {
    "iPhone 15 Pro Max 256GB": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/iphone_15_pro_1785768378510.jpg",
    "Macbook m4": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/macbook_m4_1785768392077.jpg",
    "Samsung Galaxy S24 Ultra": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/samsung_s24_ultra_1785768403964.jpg",
    "AirPods Pro 2 (USB-C)": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/airpods_pro_2_1785768414900.jpg",
    "Apple Watch Series 9 45mm": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/apple_watch_9_1785768428264.jpg",
    "Sony WH-1000XM5 Headset": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/sony_headphones_1785768440712.jpg",
    "iPad Air 5th Gen 64GB": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/ipad_air_5_1785768452254.jpg",
    "Xiaomi 14 Ultra 512GB": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/xiaomi_14_ultra_1785768464469.jpg",
    "Dell XPS 15 9530 i9": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/dell_xps_15_1785768476666.jpg",
    "LG OLED C3 55-inch TV": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/lg_oled_tv_1785768491139.jpg",
    "MacBook Air M3 15-inch": "/Users/muhasibpro/.gemini/antigravity-cli/brain/788c52d1-47a4-4383-a5d6-6d5d3e60655c/macbook_air_m3_1785768505480.jpg"
}

for tovar_nomi, rasm_path in images_mapping.items():
    res = hisob.rasm_biriktirish(tovar_nomi, rasm_path)
    print(f"Rasm biriktirildi: {tovar_nomi} -> {res['rasm']}")

print("Barcha rasmlar muvaffaqiyatli biriktirildi!")
