"""
RAG (Retrieval-Augmented Generation) Pipeline

Implements the full RAG workflow:
1. Retrieve relevant context from knowledge base
2. Augment prompt with context
3. Generate response with LLM
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    RAG pipeline for knowledge-enhanced question answering.

    Workflow:
    1. User query → embedding
    2. Vector search in KB → top-k relevant chunks
    3. Build augmented prompt with KB context + chat history
    4. LLM generation → answer with citations
    """

    def __init__(
        self,
        storage,
        ai_client,
        top_k: int = 5,
    ):
        """
        Args:
            storage: Storage instance (must support vector search)
            ai_client: AIClient with embeddings and chat support
            top_k: Number of chunks to retrieve
        """
        self.storage = storage
        self.ai_client = ai_client
        self.top_k = top_k

    def retrieve_context(
        self,
        query: str,
        top_k: int | None = None,
        document_type: str | None = None,
    ) -> list[dict]:
        """
        Retrieve relevant chunks from knowledge base.

        Args:
            query: User query
            top_k: Number of chunks to retrieve (default: self.top_k)
            document_type: Filter by document type

        Returns:
            List of chunks with metadata and similarity scores
        """
        top_k = top_k or self.top_k

        try:
            # Generate query embedding
            query_embedding = self.ai_client.get_embedding(query)

            # Vector search in KB
            results = self.storage.vector_search_kb(
                embedding=query_embedding,
                top_k=top_k,
                document_type=document_type,
            )

            logger.info(f"Retrieved {len(results)} chunks for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Failed to retrieve context: {e}")
            return []

    def augment_prompt(
        self,
        query: str,
        context: list[dict],
        history: list[dict[str, str]] | None = None,
        driver_profile: dict | None = None,
    ) -> list[dict[str, str]]:
        """
        Build augmented prompt with KB context and chat history.

        Args:
            query: User query
            context: Retrieved KB chunks
            history: Chat history
            driver_profile: Optional driver profile for personalization

        Returns:
            Messages list for LLM API
        """
        history = history or []

        # Build KB context section
        if context:
            context_parts = []
            for i, chunk in enumerate(context, 1):
                title = chunk.get('title', 'Unknown')
                doc_type = chunk.get('document_type', 'document')
                text = chunk.get('chunk_text', '')
                similarity = chunk.get('similarity', 0.0)

                context_parts.append(
                    f"[{i}] {title} ({doc_type}) [similarity: {similarity:.2f}]\n{text}"
                )

            kb_context = "\n\n---\n\n".join(context_parts)
        else:
            kb_context = "База знаний пуста или не содержит релевантной информации."

        # Build driver profile section
        profile_context = ""
        if driver_profile:
            profile_context = (
                f"\n\nПРОФИЛЬ ВОДИТЕЛЯ:\n"
                f"Имя: {driver_profile.get('full_name', 'Неизвестно')}\n"
                f"Username: @{driver_profile.get('username', 'неизвестно')}\n"
                f"Статус: {driver_profile.get('status', 'active')}"
            )
            if driver_profile.get('shift_preference'):
                profile_context += f"\nПредпочитаемая смена: {driver_profile['shift_preference']}"

        # Build system prompt
        system_prompt = (
            "Ты полезный и компетентный ассистент для водителей автопарка. "
            "Твоя задача - отвечать на вопросы на основе базы знаний компании.\n\n"
            "ИНСТРУКЦИИ:\n"
            "1. Используй ТОЛЬКО информацию из базы знаний ниже для ответа\n"
            "2. Если информации нет в базе знаний, честно скажи об этом\n"
            "3. Не выдумывай факты и не додумывай информацию\n"
            "4. Будь конкретным и давай прямые ответы\n"
            "5. Если нужна помощь диспетчера, порекомендуй обратиться к нему\n"
            "6. Учитывай контекст предыдущих сообщений\n\n"
            f"БАЗА ЗНАНИЙ:\n{kb_context}"
            f"{profile_context}\n\n"
            "Отвечай по-русски, естественно и по существу."
        )

        # Build messages
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]

        # Add recent chat history (limited to prevent context overflow)
        for msg in history[-8:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("text", "")[:1000],
            })

        # Add current query
        messages.append({"role": "user", "content": query})

        return messages

    def generate_answer(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        driver_profile: dict | None = None,
        document_type: str | None = None,
    ) -> tuple[str, list[dict]]:
        """
        Full RAG pipeline: retrieve → augment → generate.

        Args:
            query: User query
            history: Chat history
            driver_profile: Optional driver profile
            document_type: Filter KB by document type

        Returns:
            Tuple of (answer, citations)
            - answer: Generated response
            - citations: Retrieved KB chunks (for transparency)
        """
        # 1. Retrieve relevant KB chunks
        context = self.retrieve_context(
            query=query,
            document_type=document_type,
        )

        # 2. Build augmented prompt
        messages = self.augment_prompt(
            query=query,
            context=context,
            history=history,
            driver_profile=driver_profile,
        )

        # 3. Generate answer
        try:
            answer = self.ai_client._post_chat(
                messages=messages,
                temperature=0.7,
            )
            logger.info(f"Generated RAG answer for: {query[:50]}...")
        except Exception as e:
            logger.error(f"Failed to generate answer: {e}")
            # Fallback to simple response
            answer = (
                "Извините, не смог обработать ваш запрос. "
                "Попробуйте переформулировать или обратитесь к диспетчеру."
            )

        return answer, context

    def should_use_rag(self, query: str) -> bool:
        """
        Decide whether to use RAG for this query.

        RAG is beneficial for:
        - Questions about policies, rules, procedures
        - "How to" questions
        - Factual queries about company information

        RAG is NOT beneficial for:
        - Greetings, small talk
        - Very short messages (< 5 words)
        - Personal status updates

        Args:
            query: User query

        Returns:
            True if RAG should be used
        """
        query_lower = query.lower().strip()

        # Skip RAG for short messages
        if len(query.split()) < 5:
            return False

        # Skip RAG for greetings
        greetings = ["привет", "здравствуй", "добрый", "как дела", "спасибо", "пожалуйста"]
        if any(greeting in query_lower for greeting in greetings):
            return False

        # Use RAG for questions
        question_words = ["как", "что", "где", "когда", "почему", "можно ли", "нужно ли"]
        if any(word in query_lower for word in question_words):
            return True

        # Use RAG for policy/procedure queries
        kb_keywords = [
            "правил", "инструкц", "процедур", "политик",
            "выходн", "отпуск", "смен", "график",
            "зарплат", "оплат", "штраф", "премия"
        ]
        if any(keyword in query_lower for keyword in kb_keywords):
            return True

        # Default: don't use RAG for unclear cases
        return False
