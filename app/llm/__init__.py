"""
Módulo de Inteligência Artificial e Modelos de Linguagem (LLM).
Provedores (Groq, Gemini), fallback automático, prompts, extração de triplas e geração.
"""

from app.llm.schemas import Triple, TripleList, ExtractedEntities
from app.llm.providers import LLMProviderManager, llm_provider
from app.llm.prompts import (
    get_triple_extraction_prompt,
    get_entity_extraction_prompt,
    get_grounded_answer_prompt
)
from app.llm.extraction import (
    extract_triples,
    get_entities_from_question,
    get_entity_from_question
)
from app.llm.generation import generate_final_answer

__all__ = [
    "Triple",
    "TripleList",
    "ExtractedEntities",
    "LLMProviderManager",
    "llm_provider",
    "get_triple_extraction_prompt",
    "get_entity_extraction_prompt",
    "get_grounded_answer_prompt",
    "extract_triples",
    "get_entities_from_question",
    "get_entity_from_question",
    "generate_final_answer",
]
