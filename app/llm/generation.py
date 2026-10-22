"""
Geração de respostas políticas fundamentadas (grounded RAG) com base no contexto do grafo.
"""

import logging
from app.core.config import GROQ_CHAT_MODEL
from app.llm.prompts import get_grounded_answer_prompt
from app.llm.providers import llm_provider

logger = logging.getLogger("graphpolitics.llm.generation")

def generate_final_answer(context: str, question: str) -> str:
    """Gera resposta fundamentada baseada estritamente no contexto recuperado do grafo."""
    prompt = get_grounded_answer_prompt(context=context, question=question)
    return llm_provider.generate_text_with_fallback(
        prompt=prompt,
        groq_model=GROQ_CHAT_MODEL,
        max_retries=3
    )
