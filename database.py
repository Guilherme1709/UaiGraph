"""
Fachada de retrocompatibilidade para database.py.
Delega a implementação modular para os submódulos em app.graph e app.core.
"""

from app.core.normalization import normalize_party_name, PARTY_CANONICAL_MAP, KNOWN_PARTIES
from app.graph import Neo4jManager

__all__ = [
    "Neo4jManager",
    "normalize_party_name",
    "PARTY_CANONICAL_MAP",
    "KNOWN_PARTIES",
]
