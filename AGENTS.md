# Loyiha qoidalari (agent uchun)

MUHASIB — POS kassa dasturi. Bu papkada uning reklama videolari va Antigravity
grafik interfeysi turadi.

## VIDEO — eng muhim qoida

Foydalanuvchi "animatsiya", "multfilm", "qimirlaydigan video", "reklama rolik"
so'rasa — **`video/` papkasidagi quvurdan foydalan**. Boshqa usul yozma.

### TAQIQLANGAN

`ffmpeg -loop 1 -i rasm.jpg ... zoompan` — bu **animatsiya emas**. Bu shunchaki
qotib qolgan rasmni surish (Ken Burns). Foydalanuvchi buni allaqachon rad etgan:
"HAQIYQIY QIMIRLAYDIGAN BOLSIN RASM DEK EMAS".

Shuningdek `crossfade`/`xfade` bilan slayd-shou ham yaramaydi.

### To'g'ri usul — ikkita yo'l bor

**1) Vektor multfilm** (personaj to'liq harakatlanadi: qo'l, oyoq, bosh, og'iz, ko'z)

```bash
.venv/bin/python video/make_multik.py
```

Ssenariyni o'zgartirish: `video/make_multik.py` ichidagi `LINES` (ovoz matnlari)
va `BUBBLE_CASH` / `BUBBLE_BOY` (gap puffagi matnlari). Sahna o'zi —
`video/multik_energetik.html`.

**2) Real rasmdan** (AI generatsiya qilgan rasm; oyoqlar bo'g'inda aylanadi)

```bash
.venv/bin/python video/make_real_demo.py images/scene_1.jpg
```

Bu rasmni avtomatik qatlamlarga ajratadi (`video/cutout.py` — macOS Vision),
fonni tozalaydi va animatsiya qiladi.

### Yangi sahna yozish

`video/render_anim.py` — umumiy dvigatel: **istalgan HTML** ni kadrma-kadr
render qiladi (headless Chrome → ffmpeg). HTML faqat ikkitasini e'lon qilishi kerak:

```js
window.DURATION = 30;               // soniya
window.SEEK = function(t){ ... };   // t soniyaga mos holatni chizadi
```

CSS animatsiya va `requestAnimationFrame` ISHLATMA — butun harakat `SEEK(t)`
ichida `t` dan hisoblanishi shart, aks holda ovoz bilan mos tushmaydi.

```bash
python3 video/render_anim.py --html video/sahna.html --out natija.mp4 \
  --fps 30 --w 1920 --h 1080 --audio video/audio/gap1.mp3@12.2
```

Tez ko'rish uchun: `--fps 12 --w 960 --h 540`.

To'liq qo'llanma: `video/README.md`.

## Ovoz

O'zbek ovozi uchun `edge-tts` (venv'da o'rnatilgan):

- `uz-UZ-SardorNeural` — erkak
- `uz-UZ-MadinaNeural` — ayol

`say` buyrug'ini ishlatma — unda o'zbek ovozi yo'q, natija tushunarsiz chiqadi.

Bu **video ovozi** uchun. 8777 dagi chat ovozi boshqa: u OpenAI'da ishlaydi
(`gpt-4o-mini-tts`, jonli suhbat `gpt-realtime-2.1`, nutq→matn `gpt-live-transcribe`).
U yerda faqat haqiqiy API ovoz ID'larini ishlat: `marin`, `cedar`, `coral`, `sage`,
`verse`, `ash`, `ballad`, `alloy`, `echo`, `shimmer`, `nova`, `fable`, `onyx`.
ChatGPT Desktop'dagi nomlar (`sol`, `breeze`, `cove`, `ember`, `vale`…) API ovozi
EMAS — ular 400 qaytaradi va jimgina edge-tts ga tushib ketadi.

"GPT-Live" — OpenAI'ning mahsulot nomi; API tomonida u `gpt-realtime` oilasi.
`gpt-live` degan suhbat modeli yo'q, izlama.

Jonli ovoz **hisob vositalarini chaqira oladi** (`realtime_tools()` → `amal_yozish`,
`hisobot_olish`, `amallar_royxati`, `amal_ochirish`, `biznes_sozlama`). Chaqiruv
brauzer data-channel orqali `/api/voice/tool` ga boradi. Fayl va terminal vositalari
ovozga ataylab BERILMAGAN — `run_voice_tool()` ularni rad etadi. Shu chegarani buzma.

## Python

Loyiha virtual muhiti: `.venv/bin/python` (unda `edge-tts`, `pyobjc` bor).
`pip` o'rniga `uv pip install --python .venv/bin/python <paket>` ishlat.

`PIL`/`Pillow`, `cv2`, `numpy` **o'rnatilmagan** — ularga tayanma yoki avval o'rnat.

## Eski fayllar

`render_animated_mp4.sh`, `build_multik_video.sh`, `build_sardor_madina_video.sh`,
`build_real_motion_muhasib.sh` — bular eski `zoompan` usuli. Namuna sifatida olma.

## Interfeys

`agy_app.py` — brauzerdagi chat (port 8777, `./start.sh` bilan ishga tushadi).
O'zgartirsang, foydalanuvchiga qayta ishga tushirish kerakligini ayt.

### Model tanlovi

| Tanlov | Nima qiladi |
|---|---|
| **ChatGPT Sol** (standart) | To'g'ridan-to'g'ri OpenAI Responses API — matn token-token oqadi, birinchi so'z ~1.5s. Fayl o'qish/yozish/tahrirlash, qidiruv va terminal vositalari shu yerda ishlaydi. |
| Composer Auto / model nomi | `agy` CLI (Google account) |
| Codex CLI | `codex exec` (ChatGPT hisobi) |

Sol yo'li `stream_sol_chat()` da. Kalit `.env` dagi `OPENAI_API_KEY`, model esa
`OPENAI_CHAT_MODEL` bilan almashtiriladi (standart `gpt-5.6-sol`).
Suhbat xotirasi `SOL_SESSIONS` da, har bir suhbat alohida.

### Vositalar

Asosiy vositalar (fayl, terminal, hisob-kitob) `SOL_TOOLS` da, `_sol_run_tool()`
ularni bajaradi. Brauzer, ekran, reja, web va rasm vositalari esa alohida
modulda — `vositalar.py`. Yangi vosita qo'shsang o'sha yerga qo'sh: sxemasi
`TOOLS` ro'yxatiga, bajaruvchisi mos guruh funksiyasiga. `agy_app.py` ni
o'zgartirish shart emas — `SOL_TOOLS += vositalar.TOOLS` hammasini ulaydi.

| Modul | Nima qiladi |
|---|---|
| `brauzer.py` | Chrome DevTools Protocol orqali haqiqiy Chrome. Tashqi kutubxona yo'q — WebSocket qo'lda yozilgan |
| `ekran.py` | macOS ekrani: `screencapture` + `cliclick` + `osascript` |
| `vositalar.py` | Yuqoridagilarni model chaqiradigan vositalarga o'raydi |

`sink` — vosita bilan interfeys orasidagi yon kanal. Vosita unga `image`
(modelga ko'rsatiladigan rasm), `reja` (jonli reja paneli) yoki `brauzer`
(brauzer paneli holati) qo'yadi, `stream_sol_chat()` esa ularni SSE hodisasiga
o'tkazadi.

### Aniqlik mexanizmlari

Bular agentning to'g'ri ishlashini kod darajasida ta'minlaydi — ko'rsatmadagi
iltimosga tashlab qo'yilmagan:

| Mexanizm | Qayerda | Nima qiladi |
|---|---|---|
| `_loyiha_qoidalari()` | `stream_sol_chat()` | Ish papkasi va ildizdagi **AGENTS.md ni har suhbatda ko'rsatmaga qo'shadi**. Ilgari "AGENTS.md ga amal qil" deb yozilgan-u, fayl hech qachon o'qilmasdi |
| `_git_konteksti()` | `stream_sol_chat()` | Tarmoq va o'zgargan fayllar ro'yxatini ko'rsatmaga qo'shadi |
| `_fayl_tekshir()` | `write_file`, `edit_file`, `multi_edit` | Yozilgan `.py`/`.js`/`.json` faylni **darrov sintaksisga tekshiradi** va xatoni o'sha zahoti vosita natijasiga qaytaradi |
| `_sol_ixchamlash()` | qadam siklida | Tarix `IXCHAM_CHEGARA` dan oshsa eskisini **xulosaga aylantiradi**, shunchaki kesib tashlamaydi |
| `_sol_stream_once()` | har so'rovda | 429/5xx/tarmoq xatosida uch marta qayta uriniladi |

`multi_edit` **atomik**: bitta `old_text` mos kelmasa yoki bir necha marta
uchrasa, hech narsa yozilmaydi. Yarim tahrirlangan fayl qolishi mumkin emas.

`fayl_ochirish` faylni o'chirmaydi — `~/.Trash` ga suradi. Xato o'chirish
qaytariladigan bo'lsin.

`yordamchi_agent` ga `vazifalar` ro'yxati berilsa, ular alohida oqimlarda
bir vaqtda ishlaydi (5 tagacha).

### Brauzer

Chrome `~/.agy_brauzer_profil` da, `AGY_BROWSER_PORT` (standart 9333) da turadi.
Profil saqlanadi — bir marta kirilgan saytda kirgan holda qoladi.

**Profil bitta Chrome'ga tegishli — bu qat'iy.** `SingletonLock` `host-PID` ga
ishora qiladi. Kod uni faqat **egasi o'lgan** bo'lsa tozalaydi (`_qulf_egasi()`
`os.kill(pid, 0)` bilan tekshiradi). Egasi tirik bo'lsa ishga tushirish rad
etiladi va tushunarli xato beriladi.

Qulfni shartsiz o'chirib qo'yma. Ilgari shunday edi va ikkita Chrome bitta
profilni ochib yuborardi — natijada profil buzilib, har ochilishda
*"Something went wrong when opening your profile"* chiqardi.

Shu sababdan Chrome'ni **majburan o'ldirma** (`pkill`, SIGKILL). `yopish()`
avval `Browser.close` yuboradi, keyin SIGTERM va faqat oxirida majburlaydi;
`atexit` unga ulangan, shuning uchun dastur qanday tugasa ham profil toza
qoladi. Sinov paytida ham `pkill -f agy_brauzer_profil` ishlatma.

`AGY_BROWSER_HEADLESS=1` — oynasiz rejim (sinov uchun). Oddiy holatda oyna
ko'rinadi: foydalanuvchi kerak bo'lsa o'zi kirib login qila oladi.

Sahifani iframe ichida ko'rsatib bo'lmaydi (`X-Frame-Options`), shuning uchun
paneldagi ko'rinish `/api/brauzer/oqim` dagi MJPEG kadr oqimi.

Panel **boshqariladi**: kadr ustidagi bosish, yozish va aylantirish
`/api/brauzer/amal` orqali Chrome'ga uzatiladi. Kadr `object-fit: contain`
bilan chiziladi, shuning uchun frontend koordinatani `naturalWidth` va
haqiqiy o'lchamga qarab qayta hisoblaydi — buni buzsang bosish siljib ketadi.

**Kirish (login) oqimi.** Sayt login yoki CAPTCHA so'rasa agent
`brauzer_login_kutish` ni chaqiradi. Vosita `LOGIN_KUTISH` hodisasida
bloklanib turadi, `LOGIN_SO_ROV` esa "kutilmoqda" holatini saqlaydi. So'rov
SSE bilan **yuborilmaydi** — vosita bloklangan paytda hodisa oqimi ham
to'xtab turadi. Buning o'rniga panel har 2 soniyada `/api/brauzer/holat` ni
so'raydi va bannerni ko'rsatadi; "Davom et" `/api/brauzer/davom` ga boradi.
Yangi bloklovchi vosita yozsang shu naqshni takrorla.

Qidiruvda `html.duckduckgo.com/html/` ishlatiladi — u serverda chiziladi va
tez. `duckduckgo.com` ning oddiy sahifasi avtomatlashtirishni sezib CAPTCHA
beradi, unga tayanma.

### Ekran

Skrinshot har doim ekranning MANTIQIY o'lchamiga (`sips` bilan) keltiriladi —
shunda model rasmda ko'rgan koordinatani to'g'ridan-to'g'ri `ekran_bosish` ga
bera oladi, Retina 2x hisob-kitobi kerak emas.

Ikkita macOS ruxsati kerak va ularni foydalanuvchi o'zi beradi: **Ekranni yozib
olish** (ko'rish uchun) va **Kirish imkoniyati** (bosish/yozish uchun). Ruxsat
berilgach dastur qayta ishga tushirilishi shart.

### Ish oqimi ko'rinishi

Suhbatda xom qadamlar ketma-ket to'kilmaydi. Model vosita chaqirishdan oldin
yozgan gap alohida qator bo'lib turadi (`oqim-izoh`), undan keyingi vositalar
esa bitta yig'ma qatorga yig'iladi: "ekran.py yaratildi va tahrirlandi, 1 ta
buyruq bajarildi  +230 −7". Qator bosilsa ichidagi qadamlar ochiladi.

Har bir vosita `_qadam_turi()` orqali turkumga ajratiladi (`oqish`, `buyruq`,
`brauzer`, `ekran`, ...) va `oqimXulosa()` shu turkumlarni o'zbekcha jumlaga
aylantiradi. Yangi turkum qo'shsang ikkala joyga ham qo'sh.

CLI agentlari (Composer, Codex) turkum yubormaydi — ular `qadam` turkumiga
tushadi va "N ta qadam bajarildi" deb ko'rsatiladi. Bu ataylab shunday: xato
turkumga tiqishdan ko'ra umumiy nom yaxshiroq.

`write_file` va `edit_file` `difflib` bilan +/− qatorlarni sanaydi va ularni
`sink["fayl"]` orqali interfeysga uzatadi.

Oqim tarixga ham saqlanadi, shuning uchun sahifa yangilanganda qadamlar
yo'qolmaydi. Ammo `compactSessions()` xabar maydonlarini oq ro'yxat bilan
qayta quradi — xabarga yangi maydon qo'shsang, o'sha ro'yxatga ham qo'sh,
aks holda jimgina tushib qoladi.

### Ulanishlar (`ulanish.py`)

Printer, TV, telefon va Telegram. Sozlamalar → Ulanishlar panelidan ulanadi,
agent esa `ulanishlar_holati`, `chop_etish`, `tv_buyruq`, `sms_yuborish`,
`qongiroq_qilish`, `telegram_yuborish` vositalari bilan ishlatadi.

| Ulanish | Qanday ishlaydi | Tasdiqlash |
|---|---|---|
| Printer | macOS CUPS (`lpstat`, `lp`) | kerak emas |
| TV | `androidtvremote2` (venv'da bor) | TV ekranidagi 6 xonali kod |
| iPhone | Messages/FaceTime `osascript` bilan | bir Apple ID + SMS uzatish |
| Android tel | `adb` | telefondagi USB debug so'rovi |
| Telegram | Bot API | `@BotFather` tokeni |
| Google Sheets | `jadval.py` — xizmat hisobi | JSON kalit + jadvalni ulashish |
| Kalendar/Eslatma/Mail | macOS ilovalari `osascript` bilan | macOS ruxsat so'rovi |
| Valyuta kursi | cbu.uz JSON | kerak emas |
| Excel | `openpyxl` | kerak emas |

**Google Sheets** (`jadval.py`) ikki xil ulanishni qo'llaydi:

1. **OAuth — asosiy yo'l.** Foydalanuvchining o'z Google hisobi. Ruxsat oynasi
   ichki brauzer panelida ochiladi, Google `http://<host>/api/ulanish/sheets/callback`
   ga qaytaradi, kod doimiy `refresh_token` ga almashtiriladi va `.env` dagi
   `GOOGLE_OAUTH_REFRESH` da saqlanadi. Kirish tokeni o'zi uzayadi. Bunda
   jadvalni alohida ulashish SHART EMAS — hisobdagi hamma jadval ochiladi.
   `GOOGLE_OAUTH_CLIENT` — Google Cloud'dan yuklangan `client_secret.json`
   (yo'li yoki mazmuni). Bu Google talabi, uni aylanib o'tib bo'lmaydi.
2. **Xizmat hisobi** — `GOOGLE_SA_JSON`. Bunda har bir jadval kalitdagi
   `client_email` ga Muharrir qilib ulashilishi kerak; 403/404 xatosida
   `jadval.py` shu pochtani xato matnida qaytaradi.

`_token()` avval OAuth ni sinaydi, keyin xizmat hisobiga tushadi.

**Avto-sinxron.** `hisob.py` dagi `_yoz()` har yozuvdan keyin `KUZATUVCHILAR`
ro'yxatidagi funksiyalarni chaqiradi. `jadval.kuzatuvni_yoq()` shu ro'yxatga
`_kechiktirib_yubor()` ni qo'shadi: u ~4 soniya kutadi (ketma-ket yozuvlar
bitta yuborishga birlashsin) va butun jurnalni jadvalga qayta yozadi.

To'liq qayta yozish ataylab: shunda **o'chirilgan amal ham jadvaldan yo'qoladi**
va ikki tomon har doim bir xil bo'ladi. Qo'shimcha qator qo'shish (append)
bilan bunga erishib bo'lmaydi.

Sozlama `.env` da (`SHEETS_AVTO_ID`, `SHEETS_AVTO_VARAQ`), ishga tushganda
`_sheets_avtosini_tikla()` uni tiklaydi — foydalanuvchi qayta sozlamaydi.

Kuzatuvchi xatosi daftarga yozishni buzmasligi kerak — `_yoz()` da har biri
alohida `try` ichida.

`sheets_*` vositalari `sink["jadval"]` ga ma'lumot qo'yadi → SSE hodisasi →
suhbat burchagidagi `#jadvalPanel`. Panel modal EMAS: agent ishni davom
ettiraveradi, foydalanuvchi jadvalni ko'rib turadi. Birinchi qator sarlavha
deb chiziladi.

Nomida `pos`/`receipt`/`58`/`80` bo'lgan printer chek printeri deb belgilanadi
(`printerlar()` dagi regex) — chek va tilxat shunga chiqadi.

**Parol so'raydigan avtomatlashtirish qo'shma.** Instagram va shunga o'xshash
saytlar uchun brauzer paneli bor: agent sahifani ochadi, foydalanuvchi o'zi
kiradi. Bu chegara `SOL_SYSTEM` da ham yozilgan.

**Xabar va qo'ng'iroq** — qaytarib bo'lmaydigan amal. Ko'rsatmada agent
yuborishdan oldin "Kimga / Matn / Yuborayinmi?" ko'rinishida tasdiq so'rashi
majburiy qilingan. Bu qoidani yumshatma.

`androidtvremote2` asyncio da ishlaydi; `ulanish.py` unga alohida doim yuruvchi
event loop beradi (`_tv_loop()`) — HTTP handler oddiy sinxron oqimda ishlagani
uchun shu kerak.

### Interfeys qoidalari

Sarlavha, hisob chizig'i va kompozitor ataylab ixcham: bitta qator, belgili
tugmalar, ortiqcha yozuvsiz. Yangi element qo'shishdan oldin o'yla — bu narsa
har safar ekranda turishga arziydimi yoki `⋯` menyusiga tushadimi.

- Agent javobi pufakcha EMAS (`.msg.model .bubble` — ramkasiz, to'liq
  kenglikda). Faqat foydalanuvchi xabari pufakcha bo'lib qoladi.
- Salomlashuv bloki suhbat bo'sh bo'lgandagina ko'rinadi (`paintWelcome()`).
  Chatga xabar qo'shadigan yangi yo'l yozsang, uni ham chaqir.
- Suhbat va kompozitor kengligi bir xil (900px) — birini o'zgartirsang
  ikkinchisini ham o'zgartir.
- YouTube havolasi `renderMD()` da pleyerga aylanadi (`youtube-nocookie`).
  Havolani agent o'zidan to'qimasligi kerak — `youtube_qidiruv` vositasi
  YouTube qidiruv sahifasidagi `ytInitialData` dan haqiqiy `videoId` larni
  oladi (API kaliti kerak emas). YouTube bu JSON tuzilmasini vaqti-vaqti
  bilan o'zgartiradi; `_yt_yur()` ishlamay qolsa o'sha yerni tekshir.

### Telefon

Interfeys 390px dan boshlab ishlaydi va uch joyda o'zgaradi:

- **Hisob chizig'i** yon tomonga suriladi (`overflow-x`), kataklar `flex: 0 0 auto`.
  Ilgari u telefonda butunlay `display: none` edi — qaytarma, kassa va qarzlar
  aynan telefonda ko'proq kerak bo'ladi.
- **Kompozitor chiplari** bitta qatorda qolib suriladi (`flex-wrap: nowrap`).
  Ikkinchi qatorga tushsa yuborish tugmasi ustiga chiqib qoladi.
- **Sarlavhada** `+` va Explorer belgilari yashiriladi — ☰ tugmasi ochadigan
  panelda ikkalasi ham bor.

Belgili tugmalar telefonda 38px dan kichik bo'lmasin.

### Xavfsizlik chegarasi

Parol, karta raqami va shaxsiy hujjat ma'lumotini agent kiritmaydi — bu
`SOL_SYSTEM` da qat'iy yozilgan. Brauzer oynasi ko'rinib turadi, shuning uchun
bunday joyda foydalanuvchining o'zi kiritadi. Bu chegarani bo'shatma.

## Hisob-kitob

Alohida dashboard YO'Q. Foydalanuvchi chatga oddiy gap yozadi ("Alisherga 200 ming
qarz berdim"), Sol uni `amal_yozish` vositasi bilan jurnalga yozadi. Sahifa tepasidagi
panel kassa, ombor, qarzdorlar, qarzlarim va foydani doim ko'rsatib turadi.

Yadro — `hisob.py`. Muhim tamoyil: **faqat amallar jurnali saqlanadi**, qolgan hamma
raqam (kassa, ombor qoldig'i, qarzlar, foyda) har safar shu jurnaldan qaytadan
hisoblanadi. Shuning uchun ular hech qachon bir-biriga zid bo'lmaydi va xato yozuvni
o'chirish kifoya — hamma narsa o'zi to'g'rilanadi.

| Fayl / joy | Vazifasi |
|---|---|
| `hisob.py` | Yadro: `amal_qoshish()`, `hisobot()`, `amallar()`, `amal_ochirish()` |
| `hisob.json` | Ma'lumot. `MUHASIB_HISOB_PATH` bilan boshqa faylga yo'naltiriladi (sinov uchun) |
| `SOL_TOOLS` ichida | `amal_yozish`, `hisobot_olish`, `amallar_royxati`, `amal_ochirish`, `biznes_sozlama` |
| `/api/hisob` | Panel shu yerdan o'qiydi |

Amal turlari: `sotuv`, `xarid`, `qarz_berdim`, `qarz_oldim`, `qarz_qaytardim`,
`qarz_qaytarildi`, `xarajat`, `kirim`, `boshlangich`. Yangi tur qo'shsang —
`hisob.py` dagi `TURLAR` jadvaliga ta'sirini ham yoz, aks holda hisobotga kirmaydi.

**Sinash paytida** `MUHASIB_HISOB_PATH` ni vaqtinchalik faylga qo'y — aks holda
foydalanuvchining haqiqiy daftariga sinov yozuvlari tushib qoladi.

Eski POS dashboard, barkod skaner va Excel omborlari olib tashlandi; ular
`eski_hisob/` papkasida zaxira sifatida turibdi. Ularni qaytarma.

## Buyruqlar

Bloklovchi (tugamaydigan) buyruqni ISHGA TUSHIRMA: `python3 -m http.server`,
`npx http-server`, `npm run dev`, `flask run` va shunga o'xshashlar abadiy osilib
qoladi va vazifa tugamaydi. Natijani ko'rsatish uchun fayl yoz — server ochma.

## Fotorealistik rasm

Foydalanuvchi "real rasm" so'rasa — `generate_image` ga **photorealistic, DSLR photo,
real people, natural lighting** deb ber. "Pixar", "3D render", "cartoon", "illustration"
so'zlarini ISHLATMA — u chizilgan chiqadi va foydalanuvchi rad etadi.

Rasmlarni `images_real/` ga `real_1.jpg … real_4.jpg` nomlari bilan saqla, keyin:

```bash
.venv/bin/python video/make_full_real.py real
```

1-rasm bola **yon tomondan, boshdan-oyoq to'liq** ko'rinadigan bo'lsin —
oyoq animatsiyasi shunda ishlaydi.

## "Image failed to generate" xatosi

Sabab odatda mualliflik huquqi: generator mashhur film/multfilm qahramonlarini
(Kung Fu Panda, Disney, Marvel, Pokemon va h.k.) chizishdan bosh tortadi.
Bu texnik nosozlik EMAS — qayta urinish, HTML chizish yoki Chrome skrinshot
bilan aylanib o'tishga urinma.

O'rniga personajni TASVIRLAB ber (nom aytmasdan):
"kimono kiygan katta semiz panda, jangovar holatda" — bu ishlaydi.
Foydalanuvchiga sababni bir gapda ayt va shu variantni taklif qil.
