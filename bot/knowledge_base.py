"""
Knowledge Base Management

Handles document ingestion, chunking, and storage for RAG.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """A chunk of a document with metadata."""
    chunk_index: int
    chunk_text: str
    chunk_tokens: int


class KnowledgeBase:
    """
    Knowledge base manager for document ingestion and chunking.

    Features:
    - Smart chunking (splits on paragraphs, sentences)
    - Metadata extraction
    - Batch processing
    """

    def __init__(
        self,
        storage,
        ai_client,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """
        Args:
            storage: Storage instance (must support PostgreSQL)
            ai_client: AIClient instance with embeddings support
            chunk_size: Target chunk size in tokens
            chunk_overlap: Overlap between chunks in tokens
        """
        self.storage = storage
        self.ai_client = ai_client
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def add_document(
        self,
        title: str,
        content: str,
        document_type: str,
        category: str | None = None,
        source_file: str | None = None,
        generate_embeddings: bool = True,
    ) -> int:
        """
        Add a document to the knowledge base.

        Args:
            title: Document title
            content: Full document content
            document_type: Type ('policy', 'faq', 'instruction')
            category: Optional category
            source_file: Optional source file path
            generate_embeddings: Whether to generate embeddings immediately

        Returns:
            Document ID
        """
        # Save document
        doc_id = self.storage.add_kb_document(
            title=title,
            content=content,
            document_type=document_type,
            category=category,
            source_file=source_file,
        )
        logger.info(f"Added document: {title} (ID: {doc_id}, type: {document_type})")

        # Chunk document
        chunks = self.chunk_document(content)
        logger.info(f"Created {len(chunks)} chunks for document {doc_id}")

        # Generate embeddings and save chunks
        if generate_embeddings:
            self._process_chunks(doc_id, chunks)

        return doc_id

    def chunk_document(self, text: str) -> list[DocumentChunk]:
        """
        Split document into chunks using smart chunking strategy.

        Strategy:
        1. Split on paragraphs (double newlines)
        2. If paragraph too large, split on sentences
        3. If sentence too large, split on character limit with word boundaries

        Args:
            text: Document text

        Returns:
            List of DocumentChunk objects
        """
        chunks: list[DocumentChunk] = []

        # Normalize whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
        text = re.sub(r'[ \t]+', ' ', text)  # Single spaces

        # Split into paragraphs
        paragraphs = text.split('\n\n')

        current_chunk = ""
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_tokens = self._estimate_tokens(para)

            # If paragraph fits in chunk, add it
            if self._estimate_tokens(current_chunk + "\n\n" + para) <= self.chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
            else:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append(DocumentChunk(
                        chunk_index=chunk_index,
                        chunk_text=current_chunk,
                        chunk_tokens=self._estimate_tokens(current_chunk),
                    ))
                    chunk_index += 1

                # If paragraph is too large, split on sentences
                if para_tokens > self.chunk_size:
                    sub_chunks = self._split_large_paragraph(para)
                    for sub_chunk in sub_chunks:
                        chunks.append(DocumentChunk(
                            chunk_index=chunk_index,
                            chunk_text=sub_chunk,
                            chunk_tokens=self._estimate_tokens(sub_chunk),
                        ))
                        chunk_index += 1
                    current_chunk = ""
                else:
                    current_chunk = para

        # Add remaining chunk
        if current_chunk:
            chunks.append(DocumentChunk(
                chunk_index=chunk_index,
                chunk_text=current_chunk,
                chunk_tokens=self._estimate_tokens(current_chunk),
            ))

        return chunks

    def _split_large_paragraph(self, text: str) -> list[str]:
        """Split large paragraph into smaller chunks on sentence boundaries."""
        # Split on sentence boundaries
        sentences = re.split(r'([.!?]\s+)', text)

        # Reconstruct sentences (split removes delimiters)
        reconstructed = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i] + (sentences[i + 1] if i + 1 < len(sentences) else '')
            reconstructed.append(sentence.strip())

        # Group sentences into chunks
        chunks: list[str] = []
        current = ""

        for sentence in reconstructed:
            if self._estimate_tokens(current + " " + sentence) <= self.chunk_size:
                current = (current + " " + sentence).strip()
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        return chunks

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation).

        OpenAI GPT models: ~4 characters per token for English,
        ~2-3 for Russian.
        """
        # Conservative estimate: 2.5 chars per token
        return max(1, len(text) // 2)

    def _process_chunks(self, document_id: int, chunks: list[DocumentChunk]) -> None:
        """
        Generate embeddings for chunks and save to database.

        Uses batch embedding API for efficiency.
        """
        if not chunks:
            return

        # Extract texts
        texts = [chunk.chunk_text for chunk in chunks]

        # Generate embeddings in batches
        try:
            embeddings = self.ai_client.get_embeddings_batch(texts)
            logger.info(f"Generated {len(embeddings)} embeddings for document {document_id}")
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            # Save chunks without embeddings
            embeddings = [[0.0] * 1536] * len(chunks)

        # Save chunks with embeddings
        for chunk, embedding in zip(chunks, embeddings):
            try:
                self.storage.add_kb_chunk(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    chunk_text=chunk.chunk_text,
                    embedding=embedding,
                    chunk_tokens=chunk.chunk_tokens,
                )
            except Exception as e:
                logger.error(f"Failed to save chunk {chunk.chunk_index}: {e}")

    def add_document_from_file(
        self,
        file_path: str | Path,
        document_type: str,
        category: str | None = None,
    ) -> int:
        """
        Load and add document from file.

        Supports: .txt, .md files

        Args:
            file_path: Path to file
            document_type: Type ('policy', 'faq', 'instruction')
            category: Optional category

        Returns:
            Document ID
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read file
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract title from filename or first heading
        title = file_path.stem.replace('_', ' ').replace('-', ' ').title()

        # Try to extract title from first markdown heading
        first_line = content.split('\n')[0].strip()
        if first_line.startswith('#'):
            title = first_line.lstrip('#').strip()

        return self.add_document(
            title=title,
            content=content,
            document_type=document_type,
            category=category,
            source_file=str(file_path),
        )

    def batch_add_documents(
        self,
        directory: str | Path,
        document_type: str,
        pattern: str = "*.md",
    ) -> list[int]:
        """
        Add all documents from a directory.

        Args:
            directory: Directory path
            document_type: Type for all documents
            pattern: File pattern (e.g., "*.md", "*.txt")

        Returns:
            List of document IDs
        """
        directory = Path(directory)

        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        doc_ids = []
        files = list(directory.glob(pattern))

        logger.info(f"Found {len(files)} files in {directory}")

        for file_path in files:
            try:
                doc_id = self.add_document_from_file(
                    file_path=file_path,
                    document_type=document_type,
                    category=directory.name,
                )
                doc_ids.append(doc_id)
            except Exception as e:
                logger.error(f"Failed to add document {file_path}: {e}")

        logger.info(f"Successfully added {len(doc_ids)} documents")
        return doc_ids
