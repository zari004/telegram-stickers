# telegram-stickers

Telegram uchun stiker to'plami (sticker pack) yaratish vositalari. Uchta qism:

1. **Interaktiv bot** (`bot/`) — foydalanuvchi rasm yoki matn yuboradi, bot uni
   stikerga aylantirib, o'z Telegram stiker to'plamiga qo'shadi. Hammasi
   tugmali menyu bilan boshqariladi; stil (rang/shrift) sozlash, kompaniya
   logotipini fon qilib qo'yish va yaratilgan to'plamlarni ro'yxatlab
   tahrirlash/o'chirish ham mumkin.
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
- \U0001F195 **Yangi to'plam** — nom so'raladi, yozgach to'plam boshlanadi
- \U0001F4E6 **Mening to'plamlarim** — avval yaratilgan to'plamlar ro'yxati
- \U0001F3A8 **Stil sozlash** — matnli stikerlar ko'rinishini tugmalar bilan sozlash
- \U0001F3E2 **Kompaniya logotipi** — logotipni yuklab, avtomatik fon qilib qo'shish
- ❓ **Yordam**

**To'plam yaratish**: menyudan \U0001F195 tugmasini bosib nom yozing (yoki
`/newpack Nomi` buyrug'ini yuboring). Keyin:
- Rasm yuboring — avtomatik stikerga aylantirib to'plamga qo'shadi
  (rasmga izoh sifatida bitta emoji yuborsangiz, o'shani ishlatadi, aks
  holda 🙂 qo'yiladi)
- Oddiy matn yuboring — matndan stiker yasab to'plamga qo'shadi (joriy
  stil sozlamalari bilan)
- `/addtext Salom! | 😀` — matndan stiker yasaydi, `|` dan keyin emoji
  ko'rsatish ixtiyoriy
- `/done` — to'plamni yakunlaydi va `t.me/addstickers/...` havolasini beradi
- `/cancel` — joriy to'plam yaratishni bekor qiladi

**Stil sozlash** (`/style` yoki menyudagi \U0001F3A8 tugma): fon rangi, matn
rangi, chiziq (outline) yoniq/o'chiq va shrift (qalin/oddiy) — barchasi
tugmalar bilan tanlanadi, tanlov saqlanadi va shu foydalanuvchining barcha
keyingi matnli stikerlarida qo'llanadi.

**Kompaniya logotipi** (`/company` yoki menyudagi \U0001F3E2 tugma):
logotipingizni bir marta rasm qilib yuboring — u saqlanadi va "Kompaniya
rejimi" yoqilganda keyingi barcha stikerlarning (matnli va rasmli)
orqa foniga avtomatik qo'yiladi. Matnli stikerlarda fon shaffof bo'lib
qoladi (logotip aniq ko'rinishi uchun), rasmli stikerlarda esa rasm
biroz kichraytirilib, atrofidan logotip "ramka" bo'lib ko'rinadi.
Tugmalar orqali istalgan payt yoqib/o'chirib yoki logotipni
almashtirib/o'chirib turish mumkin.

**Mening to'plamlarim** (`/mypacks` yoki menyudagi \U0001F4E6 tugma): bot
o'zi yaratgan barcha to'plamlaringizni ro'yxat qilib ko'rsatadi (Telegram
API "mening barcha to'plamlarim" degan so'rovni qo'llab-quvvatlamaydi,
shuning uchun bot buni o'zi eslab qoladi — quyidagi "Eslatmalar" bo'limiga
qarang). Har bir to'plamni tanlab:
- ➕ davom qo'shish (yopilgan to'plamga yana stiker qo'shish)
- ✏️ nomini o'zgartirish
- \U0001F5D1 butunlay o'chirish (Telegram'dagi to'plamning o'zi ham o'chadi)

Har bir stiker to'plami avtomatik ravishda `<slug>_<user_id>_by_<bot_username>`
nomi bilan yaratiladi — Telegramning nomlash talablariga mos keladi.

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
  config.py          - .env / BOT_TOKEN o'qish
bot/                 - interaktiv Telegram bot
  main.py, handlers.py, state.py
data/                - ishga tushirilganda avtomatik yaratiladi (logotiplar, to'plamlar ro'yxati)
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
- Bitta stiker to'plamida Telegram bo'yicha eng ko'pi bilan 120 ta statik
  stiker bo'lishi mumkin; bot bu chegarani nazorat qiladi.
- Animatsion (TGS/WEBM) stikerlar bu loyihada qo'llab-quvvatlanmaydi —
  faqat statik PNG stikerlar bilan ishlaydi.
- Stil sozlamalari, kompaniya logotipi va "Mening to'plamlarim" ro'yxati
  `data/` papkasida (xotirada emas, diskda) saqlanadi. **Bepul Render
  rejasida doimiy disk yo'q** — shuning uchun bot qayta ishga tushganda
  (redeploy yoki uzoq vaqt uxlab, qayta uyg'ongandan keyin) bu ma'lumotlar
  o'chib ketishi mumkin va foydalanuvchilar logotipni qayta yuklashga
  to'g'ri kelishi mumkin. To'liq doimiy saqlash kerak bo'lsa, Render'da
  pullik "Persistent Disk" ulash yoki tashqi bazaga (masalan Postgres)
  o'tkazish kerak bo'ladi.
