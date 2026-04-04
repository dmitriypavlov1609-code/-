# Migration Guide: SQLite → PostgreSQL (Supabase)

This guide walks you through migrating your Fleet AI Telegram Bot from SQLite to PostgreSQL.

## Prerequisites

1. **Supabase Account**
   - Sign up at [supabase.com](https://supabase.com)
   - Create a new project

2. **Python Dependencies**
   ```bash
   pip install psycopg2-binary pgvector
   ```

## Step 1: Set Up Supabase

### 1.1 Create Supabase Project

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard)
2. Click "New Project"
3. Choose a name, database password, and region
4. Wait for project creation (~2 minutes)

### 1.2 Get Connection String

1. In your Supabase project, go to **Settings → Database**
2. Copy the **Connection string** (URI format)
3. Replace `[YOUR-PASSWORD]` with your database password

Example:
```
postgresql://postgres:your_password@db.abc123.supabase.co:5432/postgres
```

### 1.3 Enable pgvector Extension

1. In Supabase dashboard, go to **SQL Editor**
2. Run this SQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 1.4 Create Database Schema

1. Open `schemas/postgres_schema.sql` in this repo
2. Copy the entire contents
3. Paste into Supabase SQL Editor
4. Click "Run"

This will create all tables, indexes, and triggers.

## Step 2: Migrate Data from SQLite

### 2.1 Dry Run (Test Migration)

First, test the migration without writing any data:

```bash
python scripts/migrate_to_supabase.py \
  --sqlite-path bot_data.sqlite3 \
  --postgres-url "postgresql://postgres:your_password@db.abc123.supabase.co:5432/postgres" \
  --dry-run
```

You should see:
```
✓ Dry run completed successfully
```

### 2.2 Run Actual Migration

If dry run succeeds, run the real migration:

```bash
python scripts/migrate_to_supabase.py \
  --sqlite-path bot_data.sqlite3 \
  --postgres-url "postgresql://postgres:your_password@db.abc123.supabase.co:5432/postgres"
```

The script will:
- Migrate all chats
- Migrate all requests
- Migrate all chat messages
- Validate counts match

Expected output:
```
✓ Migration validated successfully!
✓ Migration completed successfully
```

## Step 3: Update Environment Variables

### 3.1 Local Development

Create/update `.env` file:

```bash
# Enable PostgreSQL
USE_POSTGRES=true
POSTGRES_URL=postgresql://postgres:your_password@db.abc123.supabase.co:5432/postgres

# Keep existing variables
TELEGRAM_BOT_TOKEN=your_bot_token
COMETAPI_API_KEY=your_api_key
ADMIN_IDS=123456789
```

### 3.2 Vercel Production

Add environment variables in Vercel dashboard:

```bash
vercel env add USE_POSTGRES
# Enter: true

vercel env add POSTGRES_URL
# Enter: postgresql://postgres:...
```

Or via CLI:
```bash
vercel env add USE_POSTGRES production
vercel env add POSTGRES_URL production
```

## Step 4: Test PostgreSQL Connection

### 4.1 Local Testing

```bash
python -c "
from bot.storage import Storage
s = Storage(postgres_url='postgresql://...', use_postgres=True)
print('✓ PostgreSQL connection successful')
s.close()
"
```

### 4.2 Run Bot Locally

```bash
python serve.py
```

Check logs for:
```
INFO: Using PostgreSQL storage
INFO: PostgreSQL connection pool created
```

## Step 5: Deploy to Vercel

```bash
# Deploy with new environment variables
vercel --prod

# Or redeploy existing
vercel redeploy --prod
```

## Verification Checklist

After migration, verify everything works:

- [ ] Bot responds to `/start` command
- [ ] Chat history is preserved
- [ ] New messages are saved
- [ ] Requests are saved and admins are notified
- [ ] `/chats` command shows correct count
- [ ] `/broadcast` works

## Rollback Plan

If something goes wrong, you can rollback to SQLite:

### Option 1: Environment Variable

```bash
# Set USE_POSTGRES=false in .env or Vercel
USE_POSTGRES=false
```

Bot will automatically use SQLite.

### Option 2: Remove Environment Variables

In Vercel dashboard:
1. Go to Settings → Environment Variables
2. Delete `USE_POSTGRES` and `POSTGRES_URL`
3. Redeploy

## Troubleshooting

### "psycopg2 not available"

Install PostgreSQL dependencies:
```bash
pip install psycopg2-binary pgvector
```

### "relation does not exist"

Schema not created. Run `schemas/postgres_schema.sql` in Supabase SQL Editor.

### "could not connect to server"

Check:
1. Connection string is correct
2. Database password is correct
3. Network allows connections to Supabase (check firewall)

### "ERROR: extension "vector" does not exist"

Enable pgvector:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

## Next Steps

After successful migration:

1. **Enable RAG** (Week 4-6)
   - Add OpenAI API key
   - Set `RAG_ENABLED=true`
   - Populate knowledge base

2. **Add Driver Profiles** (Week 7-8)
   - Profiles will be auto-created
   - No additional setup needed

3. **Monitor Performance**
   - Check Supabase dashboard for query performance
   - Monitor disk usage (free tier: 500MB)
   - Set up alerts for quota limits
