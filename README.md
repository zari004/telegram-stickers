# telegram-stickers

Telegram uchun stiker to'plami (sticker pack) yaratish vositalari. Uchta qism:

1. **Interaktiv bot** (`bot/`) — foydalanuvchi rasm yoki matn yuboradi, bot uni
   stikerga aylantirib, o'z Telegram stiker to'plamiga qo'shadi. Hammasi
   tugmali menyu bilan boshqariladi; stil (rang/shrift) sozlash, kompaniya
   logotipini fon qilib qo'yish, yaratilgan to'plamlarni ro'yxatlab
   tahrirlash/o'chirish va istalgan rasmni belgilangan o'lchamda qayta
   hajmga keltirish ham mumkin.
2. **Matndan stiker generatori** (`scripts/generate_text_stickers.py`) — hech
   qanday bot kerak emas, matn qatorlaridan 512x512 PNG stiker rasmlarini
   yasab beradi.
3. **Ommaviy yuklash skripti** (`scripts/upload_pack.py`) — bitta papkadagi
   barcha rasmlarni bitta buyruq bilan to'liq stiker to'plami qilib yuklaydi.

## O'rnatish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` faylini oching va `BOT_TOKEN` qatoriga [@BotFather](https://t.me/BotFather)
dan olingan bot tokenini yozing (`/newbot` buyrug'i bilan yaratiladi).

## 1) Interaktiv botni ishga tushirish

```bash
python -m bot.main
```

Botni birinchi marta ochganlar uchun hammasi tugmali: `/start` bosilgach
chiqadigan menyudan kerakli bo'limni tanlash kifoya, buyruqlarni yodlash
shart emas.

**Asosiy menyu** (`/start`):
- 🆕 **Yangi to'plam** — nom so'raladi, yozgach to'plam boshlanadi
- 📦 **Mening to'plamlarim** — avval yaratilgan to'plamlar ro'yxati
- 🎨 **Stil sozlash** — matnli stikerlar ko'rinishini tugmalar bilan sozlash
- 🏢 **Kompaniya logotipi** — logotipni yuklab, avtomatik fon qilib qo'shish
- 🖼 **Rasm o'lchamini o'zgartirish** — istalgan rasmni belgilangan px/dpi da qaytaradi
- ❓ **Yordam**

**To'plam yaratish**: menyudan 🆕 tugmasini bosib nom yozing (yoki
`/newpack Nomi` buyrug'ini yuboring). Keyin:
- Rasm yuboring — avtomatik stikerga aylantirib to'plamga qo'shadi
  (rasmga izoh sifatida bitta emoji yuborsangiz, o'shani ishlatadi, aks
  holda 🙂 qo'yiladi)
- Oddiy matn yuboring — matndan stiker yasab to'plamga qo'shadi (joriy
  stil sozlamalari bilan)
- `/addtext Salom! | 😀` — matndan stiker yasaydi, `|` dan keyin emoji
  ko'rsatish ixtiyoriy
- GIF yoki animatsiya yuboring — 🎬 **video-stiker** sifatida qo'shadi
  (Telegram video-stiker talablariga mos WEBM/VP9 formatga avtomatik
  o'giradi: uzunligi 3 soniyagacha qisqartiriladi, o'lchami 512px ga
  moslashtiriladi, hajmi 256KB dan oshmasligi uchun sifat avtomatik
  pasaytiriladi). Rasm/matn va GIFlarni bitta to'plamda istagan tartibda
  aralashtirib yuborish mumkin — Telegram bitta to'plamda ikkala formatni
  birga saqlamaydi, shuning uchun kerak bo'lganda bot buni fonda avtomatik
  moslashtiradi: agar to'plam GIF bilan boshlangan bo'lsa, keyin yuborgan
  matn/rasm ham qisqa video-stikerga aylantiriladi (bunda **shaffof fon oq
  rangga almashadi** — Telegram video-stikerlarda haqiqiy shaffoflikni
  to'liq ko'rsatmaydi, shuning uchun rasmning shaffof qismlari oq fon bilan
  "tekislanadi"); agar to'plam matn/rasm bilan boshlangan bo'lsa, keyin
  yuborgan GIFning birinchi kadri statik rasm sifatida qo'shiladi. Agar
  PNG rasmlaringizning shaffof foni albatta saqlanishi kerak bo'lsa, o'sha
  to'plamga GIF qo'shmang — faqat rasm/matndan iborat (statik) to'plamda
  shaffoflik to'liq saqlanadi. Bepul Render instansida video konvertatsiya
  protsessor kuchi cheklangani sabab bir necha o'n soniya davom etishi
  mumkin — shoshilmang, "GIF video-stikerga o'girilmoqda..." xabari
  chiqqach kuting.
- `/done` — to'plamni yakunlaydi va `t.me/addstickers/...` havolasini beradi
- `/cancel` — joriy to'plam yaratishni bekor qiladi

**Stil sozlash** (`/style` yoki menyudagi 🎨 tugma): fon rangi, matn
rangi, chiziq (outline) rangi va qalinligi (yoki o'chirish) va shrift —
barchasi tugmalar bilan tanlanadi (fon, matn va chiziq uchun HEX kod
kiritish orqali istalgan boshqa rangni ham tanlash mumkin), tanlov
saqlanadi va shu foydalanuvchining barcha keyingi matnli stikerlarida
qo'llanadi. Matn rangi ro'yxatining eng boshida 💚 **Yashil gradient**
varianti ham bor — matn chapdan o'ngga to'q yashildan yorqin yashilga
o'tuvchi gradient rangda chiqadi.

**O'z shriftingizni yuklash**: tayyor 4 ta shrift (Qalin/Oddiy/Klassik/
Mashinka) yetarli bo'lmasa, "📤 O'z shriftini yuklash" tugmasini bosib,
kompyuteringizdan TTF yoki OTF shrift faylini fayl (hujjat) sifatida
yuboring — u tekshirilib saqlanadi va darhol tanlanadi, keyinchalik ham
ro'yxatda 🔤 belgisi bilan qayta tanlash uchun turadi ("🗑 Yuklangan
shriftlarni tozalash" tugmasi bilan hammasini o'chirish mumkin).

**Kompaniya logotipi** (`/company` yoki menyudagi 🏢 tugma):
logotipingizni bir marta rasm qilib yuboring — u saqlanadi va "Kompaniya
rejimi" yoqilganda keyingi barcha stikerlarning (matnli va rasmli)
pastki o'ng qismiga kichik belgi (watermark) sifatida qo'yiladi — sticker
tarkibi to'liq ko'rinib turadi, logotip esa kichik va chiroyli holda
pastda joylashadi. Tugmalar orqali istalgan payt yoqib/o'chirish,
logotipni almashtirish/o'chirish, yoki logotip atrofiga kontur
qo'shish mumkin.

**Mening to'plamlarim** (`/mypacks` yoki menyudagi 📦 tugma): bot
o'zi yaratgan barcha to'plamlaringizni ro'yxat qilib ko'rsatadi (Telegram
API "mening barcha to'plamlarim" degan so'rovni qo'llab-quvvatlamaydi,
shuning uchun bot buni o'zi eslab qoladi — quyidagi "Eslatmalar" bo'limiga
qarang; ro'yxatda har bir to'plam formati 🖼 rasm/matn yoki 🎬 video/GIF
belgisi bilan ko'rsatiladi). Har bir to'plamni tanlab:
- ➕ davom qo'shish (yopilgan to'plamga yana stiker qo'shish)
- 🗑 bitta stikerni o'chirish (to'plamdagi stikerlar rasm sifatida ko'rsatiladi,
  har birining tagida "o'chirish" tugmasi bilan — qolganlari o'z joyida qoladi)
- ✏️ nomini o'zgartirish
- 🗑 butunlay o'chirish (Telegram'dagi to'plamning o'zi ham o'chadi)

Har bir stiker to'plami avtomatik ravishda `<slug>_<user_id>_by_<bot_username>`
nomi bilan yaratiladi — Telegramning nomlash talablariga mos keladi.

**Rasm o'lchamini o'zgartirish** (`/resize` yoki menyudagi 🖼 tugma): stiker
to'plami bilan bog'liq emas, mustaqil vosita — istalgan rasmni oldindan
sozlangan o'lchamda qaytarib beradi:
- Joriy sozlama (standart: `1080x1080 px, 72 dpi`) tugmalar bilan
  o'zgartiriladi: tayyor shablonlardan (Instagram post/Story, HD ekran,
  A4 chop etish @300dpi) birini tanlash yoki ✏️ tugmalari orqali
  kenglik/balandlik/DPI ni qo'lda (px, butun son) kiritish mumkin.
- Shundan keyin menga istalgan rasm yuboring — bittalab, ketma-ket bir
  nechtasini, rasm sifatida yoki fayl (hujjat) sifatida — har birini shu
  o'lchamda, nisbatini buzmasdan (cho'zmasdan, faqat ichiga sig'diradigan
  qilib) qaytarib beraman. Natija PNG fayl sifatida, sarlavhasida
  o'lcham va dpi yozilgan holda yuboriladi.
- Boshqa bo'limga o'tsangiz (yangi to'plam boshlasangiz yoki bosh menyuga
  qaytsangiz), bu rejim avtomatik o'chadi — tasodifan boshqa vaqt
  yuborilgan rasmlar qayta o'lchamlanib ketmaydi.

## 2) Matndan stiker rasm(lar) generatsiya qilish

Bot ishlatmasdan, faqat rasm fayllari kerak bo'lsa:

```bash
python scripts/generate_text_stickers.py \
  --text "Salom!" \
  --text "Rahmat 😊" \
  --bg "#FFD600" \
  --color "#1E1E1E" \
  --output-dir stickers_out
```

Yoki bir nechta iborani faylga qatorma-qator yozib:

```bash
python scripts/generate_text_stickers.py --texts-file phrases.txt --output-dir stickers_out
```

Natijada `stickers_out/` papkasida 512x512 o'lchamdagi PNG rasmlar paydo
bo'ladi — ularni `scripts/upload_pack.py` orqali yuklashingiz mumkin.

## 3) Papkadagi rasmlarni to'liq to'plam qilib yuklash

```bash
python scripts/upload_pack.py \
  --user-id 123456789 \
  --name mypack \
  --title "Mening to'plamim" \
  --images-dir ./stickers_out \
  --emojis emojis.json
```

- `--user-id` — to'plam egasi bo'ladigan Telegram foydalanuvchi ID (bot
  bilan avval kamida bir marta yozishgan bo'lishi kerak; ID ni
  [@userinfobot](https://t.me/userinfobot) orqali bilib olish mumkin).
- `--emojis` (ixtiyoriy) — `fayl_nomi.png -> emoji` xaritasini beruvchi
  JSON fayl, masalan:

  ```json
  {"001_salom.png": "👋", "002_rahmat.png": "🙏"}
  ```

  Xaritada yo'q fayllar uchun `--default-emoji` (standart: 🙂) ishlatiladi.

Skript avval to'plam mavjudligini tekshiradi: mavjud bo'lmasa yaratadi,
mavjud bo'lsa davomiga stiker qo'shib boradi — shuning uchun uni bir necha
marta, turli papkalar bilan qayta ishga tushirib, bitta to'plamni
kengaytirish ham mumkin.

## Botni doimiy ishlashi uchun serverga joylashtirish (bepul: Render)

Botni uzluksiz ishlatish uchun uni doimiy ishlaydigan serverga qo'yish kerak
(shaxsiy kompyuter yopilsa, bot ham to'xtaydi). [Render.com](https://render.com)
kredit karta talab qilmasdan bepul "Web Service" beradi — shundan
foydalanamiz. (Railway ham bor, lekin uning bepul sinov muddati tez tugaydi
va keyin to'lov so'raydi.)

Bot Render'ning "internetga ochiq port" talabiga javob berishi uchun
`bot/healthcheck.py` orqali kichik yordamchi server ham qo'shilgan — u
faqat Render kabi muhitda (PORT o'zgaruvchisi bo'lganda) ishga tushadi,
kompyuteringizda oddiy ishga tushirganingizda hech narsani o'zgartirmaydi.

1. **GitHub'ga kirish**: [render.com](https://render.com) saytiga o'ting va
   "Get Started" → "GitHub" orqali ro'yxatdan o'ting.
2. **Yangi servis yarating**: Dashboard'da **New +** → **Web Service** ni
   tanlang.
3. **Repo'ni ulang**: ro'yxatdan `zari004/telegram-stickers` ni tanlang
   (ko'rinmasa, "Configure account" orqali Render'ga repo'ga ruxsat
   bering). Branch — `main`.
4. **Sozlamalarni kiriting**:
   - **Name**: xohlagan nom (masalan `telegram-stickers-bot`)
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m bot.main`
   - **Instance Type**: `Free`
5. **Muhit o'zgaruvchisini qo'shing**: pastroqda **Environment Variables**
   bo'limida **Add Environment Variable** → nomi `BOT_TOKEN`, qiymati esa
   @BotFather'dan olgan tokeningiz.
6. **Create Web Service** tugmasini bosing va deploy tugashini kuting
   (bir necha daqiqa). **Logs** bo'limida xatolik yo'qligini tekshiring.
7. **Sinab ko'ring**: Telegramda botingizga `/start` yozing — javob kelsa,
   ishlayapti.
8. **Doim uyg'oq turishi uchun (muhim)**: Render'ning bepul rejasi 15
   daqiqa davomida hech qanday so'rov kelmasa, servisni "uxlatib qo'yadi".
   Buni oldini olish uchun bepul [cron-job.org](https://cron-job.org) yoki
   [UptimeRobot](https://uptimerobot.com) saytida hisob oching va Render
   bergan servis havolangizni (masalan `https://telegram-stickers-bot.onrender.com`)
   har 10 daqiqada bir marta "ping" qilib turishni sozlang. Shunda bot
   doim ishlab turadi.
9. **Yangilash**: keyinchalik kodni GitHub'dagi `main` branch'iga push
   qilsangiz, Render avtomatik qayta deploy qiladi.

## Loyihaning tuzilishi

```
stickerpack/        - qayta ishlatiladigan yadro (bot va skriptlar ishlatadi)
  image_utils.py     - istalgan rasmni Telegram stiker o'lchamiga keltiradi
  text_sticker.py    - matndan sticker rasm chizadi (avtomatik shrift o'lchami)
  sticker_api.py     - Telegram Bot API bilan stiker to'plami yaratish/kengaytirish
  compose.py         - stiker tarkibini fon (kompaniya logotipi) ustiga joylaydi
  logo_store.py      - har bir foydalanuvchining kompaniya logotipini saqlaydi
  pack_registry.py   - foydalanuvchi yaratgan to'plamlar ro'yxatini saqlaydi
  resizer.py         - istalgan rasmni belgilangan px o'lcham + dpi bilan qayta hajmga keltiradi
  video_sticker.py   - GIF/animatsiyani Telegram video-stiker (WEBM/VP9) formatiga o'giradi
  font_store.py      - har bir foydalanuvchi yuklagan shaxsiy shriftlarni saqlaydi
  config.py          - .env / BOT_TOKEN o'qish
bot/                 - interaktiv Telegram bot
  main.py, handlers.py, state.py
data/                - ishga tushirilganda avtomatik yaratiladi (logotiplar, shriftlar, to'plamlar ro'yxati)
scripts/
  upload_pack.py             - papkadagi rasmlarni to'plam qilib yuklash
  generate_text_stickers.py  - matndan stiker rasmlari generatsiya qilish
assets/fonts/        - matnli stikerlar uchun shrift (DejaVu Sans)
Procfile             - hosting xizmatlari uchun ishga tushirish buyrug'i
```

## Eslatmalar

- Statik stiker rasmi PNG bo'lishi va bir tomoni aniq 512px, ikkinchisi esa
  512px dan katta bo'lmasligi kerak — `image_utils.prepare_sticker_image`
  buni avtomatik ta'minlaydi.
- Bitta stiker to'plamida Telegram bo'yicha eng ko'pi bilan 120 ta stiker
  (statik yoki video) bo'lishi mumkin; bot bu chegarani nazorat qiladi.
- GIF/animatsiyalardan avtomatik yasaladigan video-stikerlar (WEBM/VP9)
  qo'llab-quvvatlanadi; Lottie-animatsiya (TGS) formatidagi stikerlar esa
  qo'llab-quvvatlanmaydi. Bitta to'plamda statik va video stikerlarni
  aralashtirib bo'lmaydi (Telegram cheklovi) — yuqoridagi "To'plam
  yaratish" bo'limiga qarang.
- Stil sozlamalari, kompaniya logotipi, yuklangan shaxsiy shriftlar va
  "Mening to'plamlarim" ro'yxati `data/` papkasida (xotirada emas,
  diskda) saqlanadi. **Bepul Render rejasida doimiy disk yo'q** —
  shuning uchun bot qayta ishga tushganda (redeploy yoki uzoq vaqt
  uxlab, qayta uyg'ongandan keyin) bu ma'lumotlar o'chib ketishi mumkin
  va foydalanuvchilar logotip/shriftni qayta yuklashga to'g'ri kelishi
  mumkin. To'liq doimiy saqlash kerak bo'lsa, Render'da
  pullik "Persistent Disk" ulash yoki tashqi bazaga (masalan Postgres)
  o'tkazish kerak bo'ladi. "Mening to'plamlarim" ro'yxati shu tarzda
  yo'qolib qolsa ham, to'plamning o'zi Telegram serverida butun saqlanadi —
  faqat bot uning nomini "unutgan" bo'ladi; `/mypacks` dagi "\U0001F517
  Yo'qolgan to'plamni tiklash" tugmasi orqali to'plamning
  `t.me/addstickers/...` havolasini yuborib, uni ro'yxatga qaytarish
  mumkin (nomida foydalanuvchining o'z ID'i borligi tekshiriladi, shuning
  uchun boshqa birovning to'plamini bunday tiklab bo'lmaydi).
