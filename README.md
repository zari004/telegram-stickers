# telegram-stickers

Telegram uchun stiker to'plami (sticker pack) yaratish vositalari. Uchta qism:

1. **Interaktiv bot** (`bot/`) — foydalanuvchi rasm yoki matn yuboradi, bot uni
   stikerga aylantirib, o'z Telegram stiker to'plamiga qo'shadi.
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

Botga Telegramda yozing:

- `/start` — yordam va buyruqlar ro'yxati
- `/newpack Mening to'plamim` — yangi to'plam boshlaydi
- Rasm yuboring — avtomatik stikerga aylantirib to'plamga qo'shadi
  (rasmga izoh sifatida bitta emoji yuborsangiz, o'shani ishlatadi, aks
  holda 🙂 qo'yiladi)
- Oddiy matn yuboring — matndan stiker yasab to'plamga qo'shadi
- `/addtext Salom! | 😀` — matndan stiker yasaydi, `|` dan keyin emoji
  ko'rsatish ixtiyoriy
- `/done` — to'plamni yakunlaydi va `t.me/addstickers/...` havolasini beradi
- `/cancel` — joriy to'plam yaratishni bekor qiladi

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
  config.py          - .env / BOT_TOKEN o'qish
bot/                 - interaktiv Telegram bot
  main.py, handlers.py, state.py
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
