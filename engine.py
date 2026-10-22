"""
Fachada de retrocompatibilidade para engine.py.
Delega para os módulos especializados em app.llm.
"""

from app.llm import (
    Triple,
    TripleList,
    ExtractedEntities,
    extract_triples,
    get_entities_from_question,
    get_entity_from_question,
    generate_final_answer,
    llm_provider
)

__all__ = [
    "Triple",
    "TripleList",
    "ExtractedEntities",
    "extract_triples",
    "get_entities_from_question",
    "get_entity_from_question",
    "generate_final_answer",
    "llm_provider",
]
