"""
Extração de entidades políticas e relações (triplas de conhecimento) a partir de texto.
"""

import re
import logging
from typing import List
from app.core.config import GROQ_EXTRACTION_MODEL, GROQ_CHAT_MODEL
from app.core.normalization import PARTY_PATTERNS, GENERIC_IGNORE_ENTITIES
from app.llm.schemas import Triple, TripleList, ExtractedEntities
from app.llm.prompts import get_triple_extraction_prompt, get_entity_extraction_prompt
from app.llm.providers import llm_provider

logger = logging.getLogger("graphpolitics.llm.extraction")

def extract_triples(text: str) -> List[Triple]:
    """Extrai entidades políticas e suas relações a partir de um texto."""
    client = llm_provider.groq_client
    if not client:
        logger.error("[Extraction] Cliente Groq não disponível para extração de triplas.")
        return []

    prompt = get_triple_extraction_prompt(text)
    try:
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=GROQ_EXTRACTION_MODEL,
            response_format={"type": "json_object"},
        )
        return TripleList.model_validate_json(completion.choices[0].message.content).triples
    except Exception as e:
        logger.error(f"[Extraction] Erro ao extrair triplas: {e}")
        return []

def get_entities_from_question(question: str) -> List[str]:
    """
    Extrai TODAS as entidades políticas relevantes mencionadas na pergunta do usuário.
    Suporta múltiplos políticos, partidos, projetos de lei e órgãos.
    """
    prompt = get_entity_extraction_prompt(question)
    data = llm_provider.generate_json_with_fallback(
        prompt=prompt,
        schema_cls=ExtractedEntities,
        groq_model=GROQ_CHAT_MODEL
    )

    clean_entities: List[str] = []
    if data and data.entities:
        clean_entities = [e.strip().replace('"', '').replace("'", "") for e in data.entities if e.strip()]
        
        # Filtra substantivos genéricos quando há outras entidades identificadas
        if len(clean_entities) > 1:
            filtered = [e for e in clean_entities if e.lower().strip() not in GENERIC_IGNORE_ENTITIES]
            if filtered:
                clean_entities = filtered

    # Reforço de partidos explícitos via Regex na pergunta
    for pat, canon in PARTY_PATTERNS:
        if re.search(pat, question, re.IGNORECASE):
            if not any(e.lower() == canon.lower() or canon.lower() in e.lower() for e in clean_entities):
                clean_entities.append(canon)

    return clean_entities

def get_entity_from_question(question: str) -> str:
    """Mantido para compatibilidade retroativa com código legado que espera string única."""
    ents = get_entities_from_question(question)
    return ents[0] if ents else ""
