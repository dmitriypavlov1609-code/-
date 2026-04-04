#!/usr/bin/env python3
"""
Quick setup test script

Tests that all components are properly configured.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 60)
print("Fleet AI Bot - Setup Test")
print("=" * 60)

# Test 1: Config loading
print("\n[1/5] Testing config...")
try:
    from bot.config import load_settings
    settings = load_settings()
    print(f"✓ Config loaded successfully")
    print(f"  - Telegram token: {'SET' if settings.telegram_token else 'NOT SET'}")
    print(f"  - LLM API key: {'SET' if settings.llm_api_key else 'NOT SET'}")
    print(f"  - PostgreSQL: {'ENABLED' if settings.use_postgres else 'DISABLED'}")
    print(f"  - RAG: {'ENABLED' if settings.rag_enabled else 'DISABLED'}")
except Exception as e:
    print(f"✗ Config loading failed: {e}")
    sys.exit(1)

# Test 2: Storage
print("\n[2/5] Testing storage...")
try:
    from bot.storage import Storage
    storage = Storage(
        db_path=settings.db_path,
        postgres_url=settings.postgres_url,
        use_postgres=settings.use_postgres,
    )
    print(f"✓ Storage initialized")
    print(f"  - Mode: {'PostgreSQL' if storage.use_postgres else 'SQLite'}")
    storage.close()
except Exception as e:
    print(f"✗ Storage initialization failed: {e}")
    sys.exit(1)

# Test 3: AI Client
print("\n[3/5] Testing AI client...")
try:
    from bot.ai_client import AIClient
    ai = AIClient(
        api_key=settings.llm_api_key,
        api_url=settings.llm_api_url,
        model_name=settings.model_name,
        openai_api_key=settings.openai_api_key,
        embedding_model=settings.embedding_model,
    )
    print(f"✓ AI client initialized")
    print(f"  - Model: {ai.model_name}")
    print(f"  - Embeddings: {'AVAILABLE' if ai.openai_api_key else 'NOT AVAILABLE'}")
except Exception as e:
    print(f"✗ AI client initialization failed: {e}")
    sys.exit(1)

# Test 4: RAG (if enabled)
if settings.rag_enabled and settings.use_postgres:
    print("\n[4/5] Testing RAG pipeline...")
    try:
        from bot.rag import RAGPipeline
        from bot.storage import Storage
        
        storage = Storage(
            postgres_url=settings.postgres_url,
            use_postgres=True,
        )
        
        rag = RAGPipeline(storage, ai, top_k=settings.rag_top_k)
        print(f"✓ RAG pipeline initialized")
        print(f"  - Top-K: {rag.top_k}")
        storage.close()
    except Exception as e:
        print(f"✗ RAG pipeline failed: {e}")
        print(f"  (This is OK if KB is not yet populated)")
else:
    print("\n[4/5] RAG pipeline - SKIPPED (not enabled)")

# Test 5: Knowledge Base (if enabled)
if settings.use_postgres:
    print("\n[5/5] Testing Knowledge Base...")
    try:
        from bot.knowledge_base import KnowledgeBase
        from bot.storage import Storage
        
        storage = Storage(
            postgres_url=settings.postgres_url,
            use_postgres=True,
        )
        
        kb = KnowledgeBase(
            storage=storage,
            ai_client=ai,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        print(f"✓ Knowledge Base initialized")
        print(f"  - Chunk size: {kb.chunk_size}")
        print(f"  - Chunk overlap: {kb.chunk_overlap}")
        storage.close()
    except Exception as e:
        print(f"✗ Knowledge Base failed: {e}")
        print(f"  (This is OK if PostgreSQL is not available)")
else:
    print("\n[5/5] Knowledge Base - SKIPPED (PostgreSQL not enabled)")

# Summary
print("\n" + "=" * 60)
print("Setup Test Summary")
print("=" * 60)
print("✓ All core components initialized successfully")
print("\nNext steps:")
if not settings.use_postgres:
    print("  1. Set up Supabase project")
    print("  2. Run schemas/postgres_schema.sql")
    print("  3. Update .env with POSTGRES_URL and USE_POSTGRES=true")
if not settings.rag_enabled:
    print("  4. Set RAG_ENABLED=true in .env")
    print("  5. Run scripts/populate_kb.py to load knowledge base")
print("\nTo start bot:")
print("  python serve.py")
print("=" * 60)
