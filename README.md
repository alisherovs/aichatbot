# TeleMind AI Bot

TeleMind AI Bot — aiogram 3, Telethon, SQLAlchemy async ORM va Groq AI asosida yozilgan Telegram AI yordamchi bot.

## Imkoniyatlar

- Toza o‘zbekcha inline menyu
- Groq orqali AI suhbat va AI vositalar
- Personajlar va doimiy foydalanuvchi prompti
- Kunlik AI limitlar: Free 30, Pro 150, Business 300
- Telegram account ulash va shifrlangan session saqlash
- Kiruvchi shaxsiy xabarlarga AI yordamchi orqali javob berish
- Confirm va auto javob rejimlari
- Telegram Stars orqali Pro va Business tarif sotib olish
- Admin panel: foydalanuvchilar, statistika, to‘lovlar, tarif berish, bonus berish, promokodlar, broadcast va bloklash
- Referal tizimi va bonus AI kreditlar
- SQLite asosidagi lokal baza, keyinchalik PostgreSQLga ko‘chirishga qulay arxitektura

## O‘rnatish

Python 3.11 yoki undan yuqori versiya kerak.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` faylini to‘ldiring:

```env
BOT_TOKEN=BotFather_dan_olingan_token
ADMIN_IDS=123456789,987654321
DATABASE_URL=sqlite+aiosqlite:///bot.db

GROQ_API_KEY=Groq_API_key
GROQ_MODEL=llama-3.3-70b-versatile
AI_PROVIDER=groq
AI_TEMPERATURE=0.2
AI_TOP_P=0.8
AI_MAX_TOKENS=700

TELEGRAM_API_ID=my.telegram.org_api_id
TELEGRAM_API_HASH=my.telegram.org_api_hash
SESSION_ENCRYPTION_KEY=fernet_key
```

Ishga tushirish:

```bash
python run.py
```

Baza jadvallari birinchi ishga tushishda avtomatik yaratiladi.

## Token va kalitlar

Bot token olish:

1. Telegramda `@BotFather` ga yozing.
2. `/newbot` buyrug‘i orqali bot yarating.
3. Berilgan tokenni `BOT_TOKEN` ga yozing.

Groq API key olish:

1. `https://console.groq.com/keys` sahifasiga kiring.
2. API key yarating.
3. Uni `GROQ_API_KEY` ga yozing.
4. Modelni `GROQ_MODEL` orqali tanlang. Standart model: `llama-3.3-70b-versatile`.

Telegram API ID va API HASH olish:

1. `https://my.telegram.org` sahifasiga kiring.
2. `API development tools` bo‘limida app yarating.
3. `api_id` va `api_hash` qiymatlarini `.env` ga yozing.

Fernet session kaliti yaratish:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Chiqqan qiymatni `SESSION_ENCRYPTION_KEY` ga yozing.

Admin ID qo‘shish:

```env
ADMIN_IDS=111111111,222222222
```

## Telegram Stars to‘lovlari

Bot Telegram Stars invoice yuboradi:

- Pro: 100 ⭐, 30 kun, kuniga 150 AI javob
- Business: 250 ⭐, 30 kun, kuniga 300 AI javob

Stars uchun `currency="XTR"` va `provider_token=""` ishlatiladi. To‘lov muvaffaqiyatli yakunlansa, tarif avtomatik faollashadi.

## Bonus, promokod va referal

Admin panel orqali:

- bitta foydalanuvchiga Free, Pro yoki Business tarifi berish;
- bitta foydalanuvchiga bonus AI kredit qo‘shish;
- kredit promokod yaratish;
- Pro yoki Business tarif promokod yaratish mumkin.

Bonus kreditlar kunlik limit tugagandan keyin ishlatiladi. Referal havola orqali kelgan foydalanuvchi va taklif qilgan foydalanuvchiga bonus kredit beriladi.

## Huquqiy hujjatlar

Bot ichida asosiy menyudan foydalanish shartlari va maxfiylik siyosatini ochish mumkin:

- `📄 Shartlar` — botdan foydalanish qoidalari.
- `🔐 Maxfiylik` — qanday ma’lumotlar saqlanishi va ishlatilishi haqida.

Repo ichidagi to‘liq matnlar:

- [TERMS.md](TERMS.md)
- [PRIVACY.md](PRIVACY.md)

## Linked account xavfsizligi

Telegram account ulash Telethon MTProto orqali ishlaydi.

- Login kodi bazaga yozilmaydi.
- 2FA parol bazaga yozilmaydi.
- Telethon `StringSession` Fernet bilan shifrlanib saqlanadi.
- Account uzilganda session o‘chiriladi.
- AI yordamchi faqat kiruvchi shaxsiy xabarlarga javob beradi.
- Guruh, kanal, bot, chiquvchi va bo‘sh xabarlar e’tiborsiz qoldiriladi.
- Auto mode per-peer queue bilan ishlaydi, shuning uchun ketma-ket kelgan xabarlar tartib bilan qayta ishlanadi.

## Ishlab chiqish

Asosiy struktura:

```text
app/
├── handlers/
├── keyboards/
├── services/
│   ├── ai/
│   └── telegram_account/
├── database/
├── states/
├── middlewares/
└── utils/
```

SQLite lokal ishga tushirish uchun yetarli. Production muhitda PostgreSQLga o‘tish uchun `DATABASE_URL` ni async PostgreSQL URL ga almashtiring va Alembic migratsiyalarini qo‘shing.
# aichatbot
