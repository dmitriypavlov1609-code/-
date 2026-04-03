#!/usr/bin/env bash
set -euo pipefail

if ! command -v vercel >/dev/null 2>&1; then
  echo "❌ Vercel CLI не найден. Установите: npm i -g vercel"
  exit 1
fi

: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}"
: "${ADMIN_IDS:?ADMIN_IDS is required}"

# COMETAPI_API_KEY optional
# TELEGRAM_WEBHOOK_SECRET optional but recommended

vercel env add TELEGRAM_BOT_TOKEN production <<<"${TELEGRAM_BOT_TOKEN}" || true
vercel env add ADMIN_IDS production <<<"${ADMIN_IDS}" || true

if [[ -n "${COMETAPI_API_KEY:-}" ]]; then
  vercel env add COMETAPI_API_KEY production <<<"${COMETAPI_API_KEY}" || true
fi

if [[ -n "${COMETAPI_BASE_URL:-}" ]]; then
  vercel env add COMETAPI_BASE_URL production <<<"${COMETAPI_BASE_URL}" || true
fi

if [[ -n "${OPENAI_MODEL:-}" ]]; then
  vercel env add OPENAI_MODEL production <<<"${OPENAI_MODEL}" || true
fi

if [[ -n "${TELEGRAM_WEBHOOK_SECRET:-}" ]]; then
  vercel env add TELEGRAM_WEBHOOK_SECRET production <<<"${TELEGRAM_WEBHOOK_SECRET}" || true
fi

DEPLOY_URL=$(vercel --prod --yes)
DEPLOY_URL=${DEPLOY_URL#https://}
PUBLIC_BASE_URL="https://${DEPLOY_URL}" \
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN}" \
TELEGRAM_WEBHOOK_SECRET="${TELEGRAM_WEBHOOK_SECRET:-}" \
python scripts/set_webhook.py

echo "✅ Деплой завершён: https://${DEPLOY_URL}"
echo "✅ Webhook установлен: https://${DEPLOY_URL}/api/telegram"
