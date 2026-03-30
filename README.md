# Fleet AI Telegram Bot

Телеграм-бот для автопарка, который:
- принимает сообщения от водителей;
- классифицирует заявки (выходной / посадка на авто / общее) через Groq AI;
- сохраняет заявки и чаты в SQLite;
- уведомляет администраторов по заявкам;
- делает рассылки по подключённым чатам.

## Важно по безопасности
Вы отправили секретные ключи в открытом чате. **Обязательно отзовите и перевыпустите ключи**:
- Telegram Bot Token (через @BotFather);
- Groq API key.

Ключи не хранятся в коде — только через переменные окружения.

## Быстрый старт

```bash
python3 -m venv .venv
source .venv/bin/activate
cp .env.example .env
```

Заполните `.env`:

```bash
TELEGRAM_BOT_TOKEN=...
GROQ_API_KEY=...
ADMIN_IDS=123456789,987654321
```

Запуск:

```bash
export $(grep -v '^#' .env | xargs)
python -m bot.main
```

## Команды

Для всех:
- `/start`
- `/help`

Для админов (`ADMIN_IDS`):
- `/broadcast <текст>` — рассылка;
- `/chats` — список чатов.

## Как это работает
1. Бот получает обновления через Telegram long polling (`getUpdates`).
2. Сообщения классифицируются ИИ (Groq API).
3. Если это заявка на выходной/авто — запись попадает в SQLite и пересылается админам.
4. Водитель получает ответ ассистента.
5. Если Groq недоступен, бот использует встроенную эвристику и продолжает работать.

## Автономный запуск на сервере (`systemd`)

```ini
[Unit]
Description=Fleet AI Telegram Bot
After=network.target

[Service]
WorkingDirectory=/opt/fleet-bot
EnvironmentFile=/opt/fleet-bot/.env
ExecStart=/opt/fleet-bot/.venv/bin/python -m bot.main
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

## Публикация на GitHub

```bash
git init
git add .
git commit -m "feat: add fleet AI telegram bot"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## Если бот не отвечает
1. Убедитесь, что вы написали **в личку боту** и нажали `/start`.
2. Проверьте, что токен корректный и процесс запущен без ошибок.
3. Если раньше использовался webhook, текущий код сам вызывает `deleteWebhook` при старте.
4. Для групп отключите privacy mode в @BotFather, если бот должен видеть все сообщения.


## Быстрый деплой в Docker (24/7)

```bash
cp .env.example .env
# заполните TELEGRAM_BOT_TOKEN, ADMIN_IDS, при желании GROQ_API_KEY
mkdir -p data
docker compose up -d --build
```

Проверка логов:

```bash
docker compose logs -f fleet-bot
```

## Автодеплой с GitHub Actions

В репозитории добавлен workflow `.github/workflows/deploy.yml`, который деплоит на ваш сервер по SSH при пуше в `main`.

Нужно добавить GitHub Secrets:
- `DEPLOY_HOST` — IP/домен сервера;
- `DEPLOY_USER` — ssh-пользователь;
- `DEPLOY_SSH_KEY` — приватный ключ.

На сервере должен быть установлен Docker + Docker Compose.


## Важно: GitHub сам по себе не запускает бота

Коротко: **если просто загрузить код на GitHub, бот работать не будет**.
GitHub — это хранилище кода, а не постоянный сервер для long-polling Telegram бота.

Чтобы бот отвечал 24/7, нужен хостинг:
- VPS (Ubuntu + Docker/systemd),
- Render / Railway / Fly.io,
- любой сервер с постоянным процессом.

## Быстрый деплой на Render (из GitHub)
1. Загрузите репозиторий в GitHub.
2. В Render создайте **New + Blueprint** и укажите репозиторий.
3. Render подхватит `render.yaml` и создаст worker-сервис.
4. В Render задайте переменные:
   - `TELEGRAM_BOT_TOKEN`
   - `ADMIN_IDS`
   - `GROQ_API_KEY` (опционально)
5. Нажмите Deploy.

После деплоя бот будет запущен постоянно и начнет отвечать.


## Тесты

```bash
python -m unittest discover -s tests -v
```


## Vercel: да, можно (через webhook)

На Vercel нельзя держать бесконечный long-polling процесс, поэтому для Vercel нужен режим **webhook**.
В репозитории добавлены:
- `api/telegram.py` — webhook endpoint для Telegram;
- `scripts/set_webhook.py` — установка webhook в Telegram API;
- `vercel.json` — конфиг Python functions.

### Шаги
1. Деплойте репозиторий на Vercel.
2. В Vercel задайте env:
   - `TELEGRAM_BOT_TOKEN`
   - `ADMIN_IDS`
   - `GROQ_API_KEY` (опционально)
   - `TELEGRAM_WEBHOOK_SECRET` (рекомендуется)
3. После деплоя выполните локально:

```bash
export TELEGRAM_BOT_TOKEN=... 
export PUBLIC_BASE_URL=https://<your-vercel-domain>
export TELEGRAM_WEBHOOK_SECRET=...
python scripts/set_webhook.py
```

После этого Telegram будет отправлять апдейты на `https://<your-vercel-domain>/api/telegram`.

> Важно: SQLite на Vercel эфемерная. Для production лучше вынести БД в внешний сервис (Postgres/Redis/Supabase).

### Быстрый one-shot деплой на Vercel

```bash
# нужны TELEGRAM_BOT_TOKEN и ADMIN_IDS, опционально GROQ_API_KEY и TELEGRAM_WEBHOOK_SECRET
bash scripts/deploy_vercel.sh
```

Скрипт:
1. добавляет env в Vercel;
2. делает `vercel --prod`;
3. автоматически вызывает `setWebhook`.

