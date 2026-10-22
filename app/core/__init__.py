"""
Módulo core: configurações globais e regras de normalização de entidades.
"""

from app.core.config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    GROQ_API_KEY,
    GEMINI_API_KEY,
    GROQ_EXTRACTION_MODEL,
    GROQ_CHAT_MODEL,
    GEMINI_MODEL,
    PORT,
    ENVIRONMENT,
    IS_DEV,
    CORS_ORIGINS,
)
from app.core.normalization import (
    normalize_party_name,
    PARTY_CANONICAL_MAP,
    KNOWN_PARTIES,
    PARTY_PATTERNS,
    GENERIC_IGNORE_ENTITIES,
    remove_accents,
    strip_accents,
)

__all__ = [
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "GROQ_API_KEY",
    "GEMINI_API_KEY",
    "GROQ_EXTRACTION_MODEL",
    "GROQ_CHAT_MODEL",
    "GEMINI_MODEL",
    "PORT",
    "ENVIRONMENT",
    "IS_DEV",
    "CORS_ORIGINS",
    "normalize_party_name",
    "PARTY_CANONICAL_MAP",
    "KNOWN_PARTIES",
    "PARTY_PATTERNS",
    "GENERIC_IGNORE_ENTITIES",
    "remove_accents",
    "strip_accents",
]
