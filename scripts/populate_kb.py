#!/usr/bin/env python3
"""
Populate Knowledge Base Script

Loads documents from data/knowledge_base/ into PostgreSQL.

Usage:
    python scripts/populate_kb.py --postgres-url postgresql://...
    python scripts/populate_kb.py --postgres-url postgresql://... --kb-dir data/knowledge_base
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from bot.storage import Storage
from bot.ai_client import AIClient
from bot.knowledge_base import KnowledgeBase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Populate knowledge base with documents")
    parser.add_argument(
        "--postgres-url",
        required=True,
        help="PostgreSQL connection URL",
    )
    parser.add_argument(
        "--openai-api-key",
        required=True,
        help="OpenAI API key for embeddings",
    )
    parser.add_argument(
        "--kb-dir",
        default="data/knowledge_base",
        help="Knowledge base directory (default: data/knowledge_base)",
    )
    parser.add_argument(
        "--embedding-model",
        default="text-embedding-3-small",
        help="OpenAI embedding model (default: text-embedding-3-small)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="Chunk size in tokens (default: 512)",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=50,
        help="Chunk overlap in tokens (default: 50)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Knowledge Base Population")
    logger.info("=" * 60)
    logger.info(f"PostgreSQL URL: {args.postgres_url[:30]}...")
    logger.info(f"KB Directory: {args.kb_dir}")
    logger.info(f"Embedding Model: {args.embedding_model}")
    logger.info(f"Chunk Size: {args.chunk_size}, Overlap: {args.chunk_overlap}")
    logger.info("=" * 60)

    kb_dir = Path(args.kb_dir)
    if not kb_dir.exists():
        logger.error(f"KB directory not found: {kb_dir}")
        sys.exit(1)

    # Initialize components
    try:
        logger.info("Connecting to PostgreSQL...")
        storage = Storage(
            postgres_url=args.postgres_url,
            use_postgres=True,
        )

        logger.info("Initializing AI client...")
        ai_client = AIClient(
            openai_api_key=args.openai_api_key,
            embedding_model=args.embedding_model,
        )

        logger.info("Initializing Knowledge Base...")
        kb = KnowledgeBase(
            storage=storage,
            ai_client=ai_client,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Process each document type directory
    doc_types = {
        "policies": "policy",
        "faqs": "faq",
        "instructions": "instruction",
    }

    total_docs = 0
    for dir_name, doc_type in doc_types.items():
        dir_path = kb_dir / dir_name

        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}, skipping...")
            continue

        logger.info(f"\n--- Processing {dir_name} ({doc_type}) ---")

        try:
            doc_ids = kb.batch_add_documents(
                directory=dir_path,
                document_type=doc_type,
                pattern="*.md",
            )
            total_docs += len(doc_ids)
            logger.info(f"✓ Added {len(doc_ids)} documents from {dir_name}")

        except Exception as e:
            logger.error(f"Failed to process {dir_name}: {e}")
            import traceback
            traceback.print_exc()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Population Summary")
    logger.info("=" * 60)
    logger.info(f"Total documents added: {total_docs}")
    logger.info("=" * 60)

    if total_docs > 0:
        logger.info("✓ Knowledge base populated successfully!")
    else:
        logger.warning("⚠ No documents were added")

    # Cleanup
    storage.close()


if __name__ == "__main__":
    main()
