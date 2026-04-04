# Руководство по конвертации файлов в базу знаний

## 📋 Ваши файлы

Найдены следующие файлы для базы знаний:

1. **Вводный инструктаж.pptx** (10MB) - PowerPoint презентация
2. **Регламент работ.docx** (36KB) - Word документ
3. **Школа Грузовичкоф (инструктаж).mp4** (160MB) - Видео инструктаж

Также доступны:
- Регламент (ред. июль 2025).docx
- Регламент ПЗ.xls
- Регламент по ложным подачам МСК.docx
- СИЭЛЬ - инструктаж.rtf

## 🔄 Конвертация документов (.docx, .pptx)

### Способ 1: Автоматическая конвертация (рекомендуется)

1. **Установите зависимости:**
```bash
pip install python-docx python-pptx
```

2. **Конвертируйте .docx файл:**
```bash
python scripts/convert_docs_to_kb.py \
  "/Users/dmitrijpavlov/Downloads/Регламент работ.docx" \
  --output-dir data/knowledge_base/policies
```

3. **Конвертируйте .pptx файл:**
```bash
python scripts/convert_docs_to_kb.py \
  "/Users/dmitrijpavlov/Downloads/Вводный инструктаж..pptx" \
  --output-dir data/knowledge_base/instructions
```

4. **Проверьте результаты:**
```bash
ls -lh data/knowledge_base/policies/
ls -lh data/knowledge_base/instructions/
```

5. **Отредактируйте markdown файлы** (при необходимости):
   - Добавьте форматирование
   - Разбейте на разделы
   - Удалите лишнее

### Способ 2: Ручная конвертация

1. **Откройте документ** в Word/PowerPoint
2. **Скопируйте текст**
3. **Создайте .md файл** в `data/knowledge_base/policies/`
4. **Вставьте текст** и добавьте markdown форматирование:

```markdown
# Название документа

## Раздел 1

Текст раздела...

## Раздел 2

Текст раздела...
```

## 🎥 Обработка видео (.mp4)

Видео **Школа Грузовичкоф (инструктаж).mp4** (160MB) нужно транскрибировать в текст.

### Способ 1: Онлайн сервисы (бесплатно/платно)

1. **YouTube** (бесплатно):
   - Загрузите видео на YouTube (приватно)
   - YouTube автоматически создаст субтитры
   - Скачайте субтитры как .srt или .txt

2. **Whisper от OpenAI** (локально, бесплатно):
```bash
# Установка
pip install openai-whisper

# Транскрипция (займет ~5-10 минут для 160MB видео)
whisper "/Users/dmitrijpavlov/Downloads/Школа Грузовичкоф (инструктаж) (2).mp4" \
  --language ru \
  --model medium \
  --output_format txt \
  --output_dir data/knowledge_base/instructions/
```

3. **AssemblyAI или Rev.ai** (платно, ~$1/час видео):
   - Очень точная транскрипция
   - Автоматическое разбиение на параграфы

### Способ 2: Ручная транскрипция

Если видео короткое (< 10 минут):
1. Просмотрите видео
2. Законспектируйте основные моменты
3. Создайте markdown файл с ключевыми пунктами

## 📝 Шаблон markdown файла

```markdown
# [Название документа]

*Источник: [название оригинального файла]*
*Дата: [дата]*
*Тип: [policy/faq/instruction]*

---

## Введение

Краткое описание документа...

## Основные разделы

### Раздел 1: [Название]

Текст раздела...

**Важно:** Ключевые моменты

### Раздел 2: [Название]

Текст раздела...

## Часто задаваемые вопросы

**Вопрос 1:** Как сделать X?
**Ответ:** Объяснение...

## Контакты

При возникновении вопросов обращайтесь:
- Начальник парка: @P_a_v_l_o_v_D (+7 991 702-68-39)
```

## 🚀 После конвертации

### 1. Проверьте файлы
```bash
ls -lh data/knowledge_base/*/
```

### 2. Загрузите в базу данных

```bash
python scripts/populate_kb.py \
  --postgres-url "postgresql://postgres:PASSWORD@HOST:5432/postgres" \
  --openai-api-key "sk-YOUR-KEY" \
  --kb-dir data/knowledge_base
```

### 3. Протестируйте RAG

Отправьте боту вопрос из документа:
```
"Какие правила работы в автопарке?"
"Как проходит вводный инструктаж?"
```

Бот должен ответить на основе загруженных документов.

## 📊 Рекомендуемая структура

```
data/knowledge_base/
├── policies/              # Регламенты, правила
│   ├── work_rules.md
│   ├── reglament_rabot.md          # Регламент работ.docx
│   ├── reglament_pz.md             # Регламент ПЗ
│   └── reglament_lozhnye_podachi.md
│
├── instructions/          # Инструктажи, обучение
│   ├── how_to_use_bot.md
│   ├── vvodnyi_instruktazh.md      # Вводный инструктаж.pptx
│   ├── shkola_gruzovichkof.md      # Школа Грузовичкоф (видео → текст)
│   └── siel_instruktazh.md         # СИЭЛЬ инструктаж
│
└── faqs/                  # FAQ
    ├── day_off_requests.md
    ├── vehicle_assignment.md
    └── contacts.md
```

## ⚡ Быстрый старт (для ваших файлов)

```bash
# 1. Установить зависимости
pip install python-docx python-pptx openai-whisper

# 2. Конвертировать Регламент работ
python scripts/convert_docs_to_kb.py \
  "/Users/dmitrijpavlov/Downloads/Регламент работ.docx" \
  --output-dir data/knowledge_base/policies

# 3. Конвертировать Вводный инструктаж
python scripts/convert_docs_to_kb.py \
  "/Users/dmitrijpavlov/Downloads/Вводный инструктаж..pptx" \
  --output-dir data/knowledge_base/instructions

# 4. Транскрибировать видео (займет ~10 минут)
whisper "/Users/dmitrijpavlov/Downloads/Школа Грузовичкоф (инструктаж) (2).mp4" \
  --language ru \
  --model medium \
  --output_format txt \
  --output_dir data/knowledge_base/instructions/

# 5. Проверить результаты
ls -lh data/knowledge_base/policies/
ls -lh data/knowledge_base/instructions/

# 6. Загрузить в БД
python scripts/populate_kb.py \
  --postgres-url "YOUR_POSTGRES_URL" \
  --openai-api-key "YOUR_OPENAI_KEY"
```

## 🔧 Troubleshooting

### "pip install openai-whisper" не работает

Используйте онлайн сервис или YouTube auto-captions.

### Транскрипция видео на английском вместо русского

Добавьте флаг `--language ru`:
```bash
whisper video.mp4 --language ru
```

### Слишком большой файл для обработки

Разбейте видео на части:
```bash
# Использование ffmpeg для разбиения
ffmpeg -i video.mp4 -t 00:10:00 -c copy part1.mp4
ffmpeg -i video.mp4 -ss 00:10:00 -c copy part2.mp4
```

### Markdown получился с ошибками

Отредактируйте файл вручную в любом текстовом редакторе.

---

**Нужна помощь?** Напишите вопрос, и я помогу!
