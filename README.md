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

## Botni doimiy ishlashi uchun serverga joylashtirish (Railway)

Botni uzluksiz ishlatish uchun uni doimiy ishlaydigan serverga qo'yish kerak
(shaxsiy kompyuter yopilsa, bot ham to'xtaydi). Railway.app bepul sinov
krediti bilan buni eng oson qiladi:

1. **GitHub'ga kirish**: [railway.app](https://railway.app) saytiga o'ting
   va "Login with GitHub" tugmasi orqali ro'yxatdan o'ting.
2. **Yangi loyiha yarating**: Dashboard'da **New Project** →
   **Deploy from GitHub repo** ni tanlang, so'ng ro'yxatdan
   `zari004/telegram-stickers` repositoriyasini tanlang (agar ko'rinmasa,
   "Configure GitHub App" orqali ruxsat bering).
3. **Branch'ni tekshiring**: Railway odatda `main` branch'ni oladi — bu
   to'g'ri, chunki barcha kod shu yerda.
4. **Muhit o'zgaruvchisini qo'shing**: yaratilgan servisga kiring →
   **Variables** bo'limi → **New Variable** → nomi `BOT_TOKEN`, qiymati esa
   @BotFather'dan olgan tokeningiz. Saqlang.
5. **Ishga tushirish buyrug'ini tekshiring**: Railway repo ildizidagi
   `Procfile` faylini (`worker: python -m bot.main`) avtomatik aniqlaydi va
   shu buyruq bilan botni fon jarayoni (worker) sifatida ishga tushiradi.
   Agar avtomatik aniqlamasa, servis sozlamalarida **Settings → Deploy →
   Custom Start Command** ga qo'lda `python -m bot.main` deb yozing.
6. **Deploy bo'lishini kuting**: **Deployments** bo'limida jarayonni
   kuzating. Tugagach **View Logs** ni oching — xatosiz ishga tushgan
   bo'lsa, log oqimida xatolik ko'rinmaydi (bot `run_polling` rejimida
   kutib turadi, alohida "started" xabari chiqmasligi mumkin — bu normal).
7. **Sinab ko'ring**: Telegramda botingizga o'ting, `/start` yozing —
   javob kelsa, bot ishga tushgan va doimiy ishlab turibdi.
8. **Yangilash**: keyinchalik kodga o'zgartirish kiritib GitHub'dagi `main`
   branch'iga push qilsangiz, Railway avtomatik qayta deploy qiladi.

> Eslatma: Railway'ning bepul rejasi oylik kredit chegarasiga ega (odatda
> kichik botlar uchun yetarli). Agar kredit tugasa, to'lov usulini
> ulashingiz yoki Render/Fly.io kabi boshqa xizmatga o'tishingiz mumkin —
> ular ham xuddi shu `Procfile` va `BOT_TOKEN` o'zgaruvchisi bilan ishlaydi.

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
