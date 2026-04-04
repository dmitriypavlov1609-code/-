# 🚀 Быстрый старт: Fleet AI Telegram Bot v2.0

## ✅ Что готово

### Реализовано полностью:
- ✅ **PostgreSQL Migration** - переход с SQLite на Supabase
- ✅ **RAG Pipeline** - умные ответы на основе базы знаний
- ✅ **Driver Profiles** - профили и статистика водителей
- ✅ **Knowledge Base** - 6 готовых документов
- ✅ **Admin Tools** - команды для управления водителями
- ✅ **Migration Scripts** - автоматическая миграция данных
- ✅ **Full Documentation** - 4 руководства

### Контакт начальника парка добавлен:
- **Павлов Д.**
- Telegram: @P_a_v_l_o_v_D
- Телефон: +7 (991) 702-68-39
- Добавлен в `data/knowledge_base/faqs/contacts.md`

## 📁 Ваши файлы для базы знаний

Готовы к конвертации:
1. ✅ `Регламент работ.docx` (36KB)
2. ✅ `Вводный инструктаж.pptx` (10MB)
3. ✅ `Школа Грузовичкоф (инструктаж).mp4` (160MB)

**См. подробную инструкцию:** `KB_CONVERSION_GUIDE.md`

## 🎯 Следующие шаги (по порядку)

### Шаг 1: Настройка Supabase (5 минут)

```bash
# 1. Зарегистрируйтесь на supabase.com
# 2. Создайте новый проект
# 3. Получите POSTGRES_URL:
#    Settings → Database → Connection string (URI)
```

### Шаг 2: Создание схемы БД (2 минуты)

```bash
# В Supabase SQL Editor:
# 1. Открыть schemas/postgres_schema.sql
# 2. Скопировать весь SQL код
# 3. Вставить и запустить (Run)
```

### Шаг 3: Миграция данных (если есть старая БД)

```bash
python scripts/migrate_to_supabase.py \
  --sqlite-path bot_data.sqlite3 \
  --postgres-url "postgresql://postgres:PASSWORD@HOST:5432/postgres"
```

### Шаг 4: Конвертация ваших документов (10-15 минут)

```bash
# Установить зависимости
pip install python-docx python-pptx openai-whisper

# Конвертировать Регламент работ
python scripts/convert_docs_to_kb.py \
  "/Users/dmitrijpavlov/Downloads/Регламент работ.docx" \
  --output-dir data/knowledge_base/policies

# Конвертировать Вводный инструктаж
python scripts/convert_docs_to_kb.py \
  "/Users/dmitrijpavlov/Downloads/Вводный инструктаж..pptx" \
  --output-dir data/knowledge_base/instructions

# Транскрибировать видео (займет ~10 минут)
whisper "/Users/dmitrijpavlov/Downloads/Школа Грузовичкоф (инструктаж) (2).mp4" \
  --language ru \
  --model medium \
  --output_format txt \
  --output_dir data/knowledge_base/instructions/
```

**Альтернатива:** Ручная конвертация (см. `KB_CONVERSION_GUIDE.md`)

### Шаг 5: Загрузка базы знаний (5 минут)

```bash
python scripts/populate_kb.py \
  --postgres-url "postgresql://postgres:PASSWORD@HOST:5432/postgres" \
  --openai-api-key "sk-YOUR-OPENAI-KEY" \
  --kb-dir data/knowledge_base
```

### Шаг 6: Настройка .env

```bash
# Скопируйте .env.example в .env
cp .env.example .env

# Отредактируйте .env:
TELEGRAM_BOT_TOKEN=your_bot_token
COMETAPI_API_KEY=your_cometapi_key
ADMIN_IDS=your_telegram_user_id

# PostgreSQL
USE_POSTGRES=true
POSTGRES_URL=postgresql://postgres:PASSWORD@HOST:5432/postgres

# RAG
RAG_ENABLED=true
OPENAI_API_KEY=sk-YOUR-OPENAI-KEY
```

### Шаг 7: Тестирование локально

```bash
# Проверка настроек
python scripts/test_setup.py

# Запуск бота
python serve.py
```

Отправьте боту:
```
Привет!
Как запросить выходной?
```

Бот должен ответить на основе документов из базы знаний.

### Шаг 8: Deployment на Vercel

```bash
# Установка Vercel CLI
npm install -g vercel

# Настройка env vars
vercel env add TELEGRAM_BOT_TOKEN
vercel env add COMETAPI_API_KEY
vercel env add ADMIN_IDS
vercel env add USE_POSTGRES
vercel env add POSTGRES_URL
vercel env add RAG_ENABLED
vercel env add OPENAI_API_KEY

# Deploy
vercel --prod

# Установка webhook
python scripts/set_webhook.py
```

## 🧪 Тестирование RAG

После запуска, протестируйте бота с разными вопросами:

### Вопросы о правилах работы:
```
- Какие правила работы в автопарке?
- Сколько смен?
- Когда утренняя смена?
- Какой штраф за опоздание?
```

### Вопросы о выходных:
```
- Как запросить выходной?
- За сколько дней подавать заявку?
- Сколько выходных можно взять в месяц?
- Что делать если срочно нужен выходной?
```

### Вопросы о постановке на авто:
```
- Как запросить постановку на авто?
- Можно ли выбирать автомобиль?
- Как узнать на какой авто меня поставили?
```

### Контакты:
```
- Как связаться с начальником парка?
- Кому звонить если заболел?
```

Бот должен отвечать точно на основе документов в базе знаний.

## 📊 Admin команды

```
/driver_info 123456789     # Информация о водителе
/driver_stats 123456789    # Статистика водителя
/set_driver_pref 123456789 shift_preference morning
/chats                     # Список подключенных чатов
/broadcast Текст рассылки  # Рассылка всем
```

## 📚 Документация

1. **README.md** - Полное описание проекта
2. **MIGRATION_GUIDE.md** - Подробная инструкция по миграции
3. **KB_CONVERSION_GUIDE.md** - Конвертация ваших файлов
4. **IMPLEMENTATION_SUMMARY.md** - Что реализовано
5. **QUICKSTART.md** - Этот файл

## 💰 Стоимость (~$1-2/мес)

- Supabase PostgreSQL: $0 (free tier)
- OpenAI Embeddings: ~$1/мес
- CometAPI: согласно вашему плану
- Vercel: $0 (free tier)

## 🔧 Troubleshooting

### Бот не отвечает
```bash
# Проверьте логи
python serve.py

# Проверьте webhook
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

### RAG не работает
```bash
# 1. Проверьте .env
grep RAG_ENABLED .env  # должно быть true

# 2. Проверьте БД
python -c "
from bot.storage import Storage
s = Storage(postgres_url='...', use_postgres=True)
# SQL: SELECT COUNT(*) FROM kb_documents;
"
```

### База знаний пустая
```bash
# Загрузите документы
python scripts/populate_kb.py --postgres-url ... --openai-api-key ...
```

## 📞 Поддержка

- **GitHub:** (ваш репозиторий)
- **Telegram:** @P_a_v_l_o_v_D
- **Документация:** См. README.md

---

**Готово к production! 🎉**

**Версия:** 2.0.0
**Дата:** 2026-04-04
