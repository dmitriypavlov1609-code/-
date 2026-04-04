# Fleet AI Telegram Bot

Интеллектуальный Telegram-бот для управления автопарком с RAG (Retrieval-Augmented Generation), профилями водителей и базой знаний.

## 🎯 Возможности

### Для водителей:
- 📝 Запросы выходных дней через естественный язык
- 🚗 Заявки на постановку на автомобиль
- 💬 Ответы на вопросы о правилах, процедурах, оплате
- 🤖 Умный ассистент на базе GPT-5 (CometAPI)
- 📚 База знаний с правилами работы, FAQ, инструкциями

### Для администраторов:
- 📢 Рассылка сообщений всем водителям
- 👥 Управление профилями водителей
- 📊 Статистика по водителям (сообщения, заявки, активность)
- ⚙️ Настройка предпочтений водителей
- 🔔 Автоматические уведомления о новых заявках

### Технологические особенности:
- ✅ RAG (Retrieval-Augmented Generation) для точных ответов
- ✅ PostgreSQL (Supabase) с векторным поиском (pgvector)
- ✅ OpenAI embeddings для семантического поиска
- ✅ Персонализация на основе профилей водителей
- ✅ Persistent storage (нет потери данных на Vercel)
- ✅ Без внешних зависимостей для базового режима (только Python stdlib)

## 🏗️ Архитектура

```
Fleet AI Bot
├── SQLite (базовый режим) ────┐
│                               ├──> Telegram Bot
├── PostgreSQL + pgvector ──────┘
│   ├── Chats
│   ├── Requests
│   ├── Chat Messages
│   ├── Knowledge Base (docs + chunks + embeddings)
│   ├── Driver Profiles
│   └── Statistics
│
├── CometAPI GPT-5 (основная модель)
├── OpenAI API (embeddings)
│
└── RAG Pipeline
    ├── 1. Retrieve (vector search в KB)
    ├── 2. Augment (prompt + KB context + driver profile)
    └── 3. Generate (LLM answer)
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

**Базовый режим (только SQLite):**
```bash
# Никаких зависимостей! Работает на чистом Python
python serve.py
```

**Полный режим (PostgreSQL + RAG):**
```bash
pip install psycopg2-binary pgvector
```

### 2. Настройка переменных окружения

Скопируйте `.env.example` в `.env`:

```bash
cp .env.example .env
```

**Минимальная конфигурация:**
```bash
TELEGRAM_BOT_TOKEN=your_bot_token
COMETAPI_API_KEY=your_cometapi_key
ADMIN_IDS=123456789
```

**Полная конфигурация (с RAG):**
```bash
# Required
TELEGRAM_BOT_TOKEN=your_bot_token
COMETAPI_API_KEY=your_cometapi_key
ADMIN_IDS=123456789

# PostgreSQL
USE_POSTGRES=true
POSTGRES_URL=postgresql://postgres:password@host:5432/postgres

# RAG
RAG_ENABLED=true
OPENAI_API_KEY=sk-your-openai-key
```

### 3. Запуск бота

**Локально (long-polling):**
```bash
python serve.py
```

**На Vercel (webhook):**
```bash
vercel --prod
```

## 📚 Миграция на PostgreSQL

Подробная инструкция: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)

**Краткая версия:**

1. Создайте Supabase проект
2. Запустите SQL схему: `schemas/postgres_schema.sql`
3. Мигрируйте данные:
   ```bash
   python scripts/migrate_to_supabase.py \
     --sqlite-path bot_data.sqlite3 \
     --postgres-url "postgresql://..."
   ```
4. Обновите `.env`:
   ```bash
   USE_POSTGRES=true
   POSTGRES_URL=postgresql://...
   ```

## 🧠 Настройка RAG и базы знаний

### 1. Создайте документы

Структура:
```
data/knowledge_base/
├── policies/        # Правила, политики
│   ├── work_rules.md
│   └── discipline.md
├── faqs/            # Часто задаваемые вопросы
│   ├── day_off_requests.md
│   ├── vehicle_assignment.md
│   └── contacts.md
└── instructions/    # Пошаговые инструкции
    ├── how_to_request_day_off.md
    └── how_to_use_bot.md
```

Примеры уже созданы в `data/knowledge_base/`.

### 2. Загрузите в базу данных

```bash
python scripts/populate_kb.py \
  --postgres-url "postgresql://..." \
  --openai-api-key "sk-..." \
  --kb-dir data/knowledge_base
```

### 3. Включите RAG

В `.env`:
```bash
RAG_ENABLED=true
```

Бот автоматически будет использовать RAG для вопросов о правилах, процедурах и т.д.

## 👥 Профили водителей

Профили создаются автоматически при первом сообщении водителя.

### Admin команды:

**Информация о водителе:**
```
/driver_info 123456789
```

**Статистика водителя:**
```
/driver_stats 123456789
```

**Установить предпочтение:**
```
/set_driver_pref 123456789 shift_preference morning
```

Доступные предпочтения:
- `shift_preference`: morning | day | night
- `notification_preference`: all | important_only | off
- `language_preference`: ru | en

## 📊 Статистика

Автоматически отслеживается:
- Количество сообщений (по дням)
- Количество заявок (общее, по типам)
- Активные дни
- Последняя активность

Просмотр через `/driver_stats <user_id>`.

## 🔧 Структура проекта

```
vercel-fleet-bot-fix/
├── bot/
│   ├── __init__.py
│   ├── main.py              # Основная логика бота
│   ├── config.py            # Настройки и env vars
│   ├── storage.py           # Unified storage (SQLite + PostgreSQL)
│   ├── ai_client.py         # LLM + embeddings client
│   ├── rag.py               # RAG pipeline
│   ├── knowledge_base.py    # KB management, chunking
│   └── driver_profile.py    # Driver profiles & stats
│
├── api/
│   └── telegram.py          # Vercel webhook endpoint
│
├── scripts/
│   ├── migrate_to_supabase.py   # SQLite → PostgreSQL migration
│   ├── populate_kb.py           # Load KB documents
│   └── set_webhook.py           # Set Telegram webhook
│
├── schemas/
│   └── postgres_schema.sql      # PostgreSQL DB schema
│
├── data/
│   └── knowledge_base/          # KB documents (markdown)
│       ├── policies/
│       ├── faqs/
│       └── instructions/
│
├── serve.py                 # Local development server
├── requirements.txt         # Python dependencies
├── .env.example            # Example environment variables
├── README.md               # This file
└── MIGRATION_GUIDE.md      # Detailed migration guide
```

## 🌐 Deployment на Vercel

### 1. Установите Vercel CLI

```bash
npm install -g vercel
```

### 2. Настройте environment variables

```bash
vercel env add TELEGRAM_BOT_TOKEN
vercel env add COMETAPI_API_KEY
vercel env add ADMIN_IDS
vercel env add USE_POSTGRES
vercel env add POSTGRES_URL
vercel env add RAG_ENABLED
vercel env add OPENAI_API_KEY
```

### 3. Deploy

```bash
vercel --prod
```

### 4. Установите webhook

```bash
python scripts/set_webhook.py
```

## 💰 Стоимость

### Free Tier (SQLite mode):
- Vercel: $0
- CometAPI: ~$0-5/мес (в зависимости от использования)
- **Total: ~$0-5/мес**

### Full Mode (PostgreSQL + RAG):
- Vercel: $0 (в пределах free tier)
- Supabase PostgreSQL: $0 (free tier: 500MB DB)
- OpenAI Embeddings: ~$1/мес (1000 сообщений/день)
- CometAPI: ~$0-5/мес
- **Total: ~$1-6/мес**

## 🔐 Безопасность

- ✅ Admin команды доступны только ADMIN_IDS
- ✅ Webhook защищен Telegram secret token
- ✅ Sensitive данные только в env vars
- ✅ SQL injection защита (parametrized queries)
- ✅ Input validation

## 🧪 Тестирование

**Локальное тестирование:**
```bash
python serve.py
```

**Проверка подключения к PostgreSQL:**
```bash
python -c "
from bot.storage import Storage
s = Storage(postgres_url='postgresql://...', use_postgres=True)
print('✓ Connected')
s.close()
"
```

**Проверка RAG:**
```bash
python -c "
from bot.ai_client import AIClient
ai = AIClient(openai_api_key='sk-...')
emb = ai.get_embedding('тест')
print(f'✓ Embedding dimension: {len(emb)}')
"
```

## 📝 Примеры использования

### Водитель запрашивает выходной:

```
Водитель: Нужен выходной 15 апреля
Бот: Заявка принята. Уточните, пожалуйста, вашу смену.
Водитель: Дневная
Бот: Отлично. Заявка на выходной 15 апреля (дневная смена) передана 
     диспетчеру. Вы получите подтверждение в течение 24 часов.
```

### Водитель задает вопрос (с RAG):

```
Водитель: Как запросить выходной?
Бот: [Ищет в базе знаний]
     Для оформления выходного дня необходимо:
     1. Подать заявку минимум за 48 часов до желаемой даты
     2. Указать причину (по желанию)
     3. Получить подтверждение от диспетчера
     
     Вы можете отправить заявку через меня, указав дату выходного.
     Например: "Нужен выходной 15 апреля"
```

### Admin просматривает профиль:

```
Admin: /driver_info 123456789

Бот: 👤 Профиль водителя
     
     ID: 123456789
     Имя: Иван Иванов
     Username: @ivan_driver
     Статус: active
     Зарегистрирован: 2024-03-01
     
     📊 Статистика (последние 30 дней):
     Всего сообщений: 45
     Всего заявок: 8
     - Выходные: 5
     - Постановка на авто: 3
     Активных дней: 22
     
     ⚙️ Настройки:
     - shift_preference: morning
```

## 🐛 Troubleshooting

### Бот не отвечает

1. Проверьте логи: `python serve.py`
2. Проверьте TELEGRAM_BOT_TOKEN
3. Проверьте webhook: `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`

### RAG не работает

1. Проверьте `RAG_ENABLED=true`
2. Проверьте `USE_POSTGRES=true`
3. Проверьте OPENAI_API_KEY
4. Убедитесь, что KB загружена: `SELECT COUNT(*) FROM kb_documents;`

### PostgreSQL connection failed

1. Проверьте POSTGRES_URL
2. Проверьте пароль в connection string
3. Проверьте firewall/network
4. Проверьте Supabase project status

## 📞 Поддержка

- **GitHub Issues**: [github.com/your-repo/issues](https://github.com)
- **Telegram**: @P_a_v_l_o_v_D (начальник парка)
- **Email**: support@example.com

## 📄 Лицензия

MIT License

## 🙏 Благодарности

- CometAPI за GPT-5 API
- Supabase за бесплатный PostgreSQL hosting
- OpenAI за embeddings API
- Telegram за Bot API

---

**Создано с ❤️ для автопарка**

**Версия:** 2.0.0 (RAG + Profiles)
**Дата:** Апрель 2026
