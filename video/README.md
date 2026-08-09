# Animatsion video tayyorlash (haqiqiy harakat, rasm slayd emas)

Bu papka HTML/SVG animatsiyani **kadrma-kadr MP4** ga aylantiradi. Personajlar
bo'g'inlari (son, tizza, yelka, tirsak) bilan harakatlanadi, og'iz gapiradi,
ko'z pirpiraydi, kamera surilib zoom qiladi.

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `render_anim.py` | Umumiy dvigatel: HTML → kadrlar → MP4 (headless Chrome + ffmpeg) |
| `multik_energetik.html` | Sahna: bola do'konga kiradi, energetik oladi, kassada MUHASIB haqida so'raydi |
| `make_multik.py` | To'liq quvur: o'zbek ovozlari (edge-tts) → vaqt jadvali → render |
| `timeline.json` | Sahna vaqtlari (avtomatik yoziladi) |
| `audio/` | Sintez qilingan ovozlar |

## Ishga tushirish

```bash
.venv/bin/python video/make_multik.py
```

Natija: `muhasib_energetik_multik.mp4` (1920×1080, 30 fps, o'zbek ovozi bilan).

## Yangi sahna yozish

`render_anim.py` istalgan HTML bilan ishlaydi. HTML faqat ikkita narsani
e'lon qilishi kerak:

```js
window.DURATION = 30;               // soniya
window.SEEK = function(t){ ... };   // t soniyaga mos holatni chizadi
```

**Muhim:** CSS animatsiya yoki `requestAnimationFrame` ISHLATMANG. Butun harakat
`SEEK(t)` ichida `t` dan hisoblanishi kerak — shunda render deterministik bo'ladi
va ovoz bilan aniq mos tushadi.

```bash
python3 video/render_anim.py \
  --html video/mening_sahnam.html \
  --out natija.mp4 --fps 30 --w 1920 --h 1080 \
  --audio video/audio/gap1.mp3@12.2 \
  --audio video/audio/gap2.mp3@17.9 \
  --config video/timeline.json      # → sahifada window.CONFIG
```

Tez ko'rish uchun: `--fps 12 --w 960 --h 540` (bir necha soniyada tayyor bo'ladi).

## O'zbek ovozi

`edge-tts` bepul neural ovozlar beradi:

- `uz-UZ-SardorNeural` — erkak
- `uz-UZ-MadinaNeural` — ayol

```bash
uv pip install --python .venv/bin/python edge-tts
```

## REAL IMAGE-TO-VIDEO (haqiqiy inson motion)

Real rasmda yuz mimikasi, qo'l harakati va butun tana tabiiy harakatlanishi
kerak bo'lsa, 2D rig emas, bulutdagi image-to-video model ishlatiladi. Bu quvur
reference rasmni Gemini Veo (standart), Fal AI yoki Replicate API'ga yuboradi, yangi video
yaratadi va unga `edge-tts` o'zbekcha ovozini qo'shadi.

Bir marta kutubxonalarni o'rnating:

```bash
uv pip install --python .venv/bin/python fal-client replicate google-genai python-dotenv
```

So'ng `.env.example` nusxasini `.env` deb oling va Google AI Studio'dan olingan
**faqat o'zingizning** Gemini API kalitingizni yozing. 8777 ichidagi Google login
alohida — u Gemini API kaliti sifatida ishlamaydi:

```env
GEMINI_API_KEY=your_google_ai_studio_key
AI_VIDEO_PROVIDER=gemini
AI_VIDEO_GEMINI_MODEL=veo-3.1-generate-preview
```

`./start.sh` bilan 8777 ishga tushgach, kalitni brauzer orqali ham kiriting:
**Explorer → Sozlamalar → Gemini Veo Video**. Kalit faqat lokal `.env` fayliga
yoziladi va keyin interfeysda qayta ko'rsatilmaydi.

Kalitni tekshirish va yangi video yaratish:

```bash
.venv/bin/python video/make_ai_real_promo.py --check-config
.venv/bin/python video/make_ai_real_promo.py images_real/real_1.jpg \
  --motion-prompt "The person smiles, speaks and gestures naturally with realistic facial expressions and full-body motion. Preserve identity and clothing."
```

Natija loyiha ildizida `muhasib_ai_real_motion_YYYYMMDD_HHMMSS.mp4`, manba klip
esa `video/outputs/` ichida saqlanadi. Gemini Veo haqiqiy rasm→video sintez qiladi
va jarayon tugamaguncha 8777 tayyor deb belgilamaydi. Fal ga qaytish uchun
`AI_VIDEO_PROVIDER=fal` va `FAL_KEY` yozing; Replicate uchun esa
`AI_VIDEO_PROVIDER=replicate` hamda uning token/model sozlamalarini yozing.

## Personaj rigi (multik_energetik.html ichida)

- `poseLeg(son, tizza, burchak1, burchak2, yelka_y)` — oyoq bo'g'inlari
- `poseArm(yelka, tirsak, burchak1, burchak2, yelka_y)` — qo'l bo'g'inlari
- `armTip(...)` — kaftning aniq koordinatasi (buyum qo'lga "yopishishi" uchun)
- `mouthTalk(...)` — gapirayotganda og'iz ochilib-yopiladi
- `blink(...)` — ko'z pirpirashi
- `seg(t, t0, t1)` — [t0,t1] oralig'idagi 0..1 progress; barcha sahna shu bilan quriladi

## REAL RASMDAN 2D RIG animatsiyasi

AI generatsiya qilingan (yoki suratga olingan) rasm qatlamlarga bo'linadi va
bo'g'inlar atrofida harakatlantiriladi. Bu shunchaki zoom emas, ammo **2D rig**:
u bitta suratdan insonning tabiiy, to'liq 3D harakatini sintez qila olmaydi.

```bash
.venv/bin/python video/make_real_demo.py images/scene_1.jpg
```

Natija: `muhasib_real_reklama.mp4`.

### Bosqichlar

| Fayl | Vazifasi |
|---|---|
| `cutout.py` | macOS Vision bilan personajni fondan ajratadi → shaffof PNG (internet/model kerak emas) |
| `prepare_scene.py` | Kesib olish + fonni tozalash (teshikni yonidagi kontent bilan to'ldiradi) + `_rig.json` |
| `multik_real.html` | Qatlamlarni animatsiya qiladi: yurish, nafas, kamera yaqinlashishi, POS kartasi, skaner |
| `make_real_demo.py` | Hammasini birlashtiradi + o'zbek ovozi |

`layers/<nom>_rig.json` ichidagi qiymatlarni qo'lda to'g'rilash mumkin:

- `hipY` — son chizig'i (shu chiziqdan pastda oyoqlar ajraladi)
- `splitX` — oyoqlar orasidagi chegara
- `legBackPivot`, `legFrontPivot` — aylanish markazlari

### Cheklov (halol aytganda)

Bitta tekis rasmdan **qo'l va bosh alohida** harakatlanmaydi — buning uchun rasmni
qo'shimcha qismlarga (yelka, tirsak, bo'yin) qo'lda kesish kerak. Hozir ishlaydigani:

- oyoqlar bo'g'inda aylanadi (haqiqiy yurish)
- gavda tebranadi, egiladi, nafas oladi
- kamera suriladi/yaqinlashadi, fon parallaks
- ustiga vektor qatlam: POS kartasi, skaner nuri, narx, logotip

Bu quvurga “haqiqiy odamdek yursin, yuz mimikasi va butun tana tabiiy harakat qilsin”
degan natija mos kelmaydi. Bunday talab uchun identity-preserving **image-to-video**
modeli kerak; u ushbu lokal quvurga kiritilmagan. Model mavjud bo'lmasa, 2D rigni
haqiqiy inson videosi deb ko'rsatish yoki eski MP4 faylni qayta berish mumkin emas.

Eng yaxshi natija uchun rasm generatsiya qilayotganda **personaj to'liq ko'rinadigan,
yon tomondan turgan** kadr so'ralsa — kesish ham, yurish ham tabiiy chiqadi.

## Nega slayd emas

`zoompan` bilan rasmni surish (eski `render_animated_mp4.sh`, `build_*_video.sh`)
faqat kamerani qimirlatadi — personaj qotib qoladi. Bu quvurda esa har bir kadr
qaytadan chiziladi, shuning uchun qadam, qo'l, og'iz — hammasi haqiqatan harakatlanadi.
