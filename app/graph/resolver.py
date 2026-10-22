"""
Resolução de entidades para nomes canônicos no grafo Neo4j.
Suporta consultas fonéticas, tolerância a acentos, Lucene fulltext e heurísticas de sobreposição.
"""

import re
import time
import logging
from typing import List, Optional
from neo4j import Driver
from app.core.normalization import normalize_party_name, KNOWN_PARTIES, remove_accents

logger = logging.getLogger("graphpolitics.graph.resolver")

class EntityResolver:
    """Resolve menções informais para o identificador exato de nós no grafo."""

    def __init__(self, driver: Driver, ttl_seconds: float = 3600.0, max_cache_size: int = 2000):
        self._driver = driver
        self._resolve_cache: dict = {}
        self._entity_names_cache: Optional[List[str]] = None
        self._entity_names_cache_ts: float = 0.0
        self._ENTITY_NAMES_TTL = ttl_seconds
        self._max_cache_size = max_cache_size

    def clear_cache(self):
        """Limpa o cache de resolução e a lista de entidades."""
        self._resolve_cache.clear()
        self._entity_names_cache = None
        self._entity_names_cache_ts = 0.0

    def resolve_entity(self, entity_query: str) -> Optional[str]:
        """
        Versão com cache de alto desempenho para resolução de entidades.
        Apenas resoluções bem-sucedidas são salvas no cache.
        """
        key = (entity_query or "").strip().lower()
        if not key:
            return None
        if key in self._resolve_cache:
            return self._resolve_cache[key]

        result = self._resolve_entity_uncached(entity_query)
        if result:
            if len(self._resolve_cache) >= self._max_cache_size:
                self._resolve_cache.clear()
            self._resolve_cache[key] = result
        return result

    def _get_all_entity_names(self) -> List[str]:
        """Lista de nomes de entidades carregada com TTL para suportar atualizações contínuas."""
        now = time.time()
        if self._entity_names_cache is None or (now - self._entity_names_cache_ts > self._ENTITY_NAMES_TTL):
            with self._driver.session() as session:
                self._entity_names_cache = [
                    r["name"] for r in session.run("MATCH (e:Entity) RETURN e.name AS name").data()
                ]
                self._entity_names_cache_ts = now
        return self._entity_names_cache

    def _resolve_entity_uncached(self, entity_query: str) -> Optional[str]:
        """
        Resolve uma menção (ex: 'Nikolas', 'PL', 'Aecio', 'Celia Xakriaba') para o nó canônico.
        """
        entity_query = entity_query.strip()
        if not entity_query:
            return None

        norm_query = remove_accents(entity_query)

        # 0. Verificação imediata de partido (sigla ou nome por extenso)
        clean_party = normalize_party_name(entity_query)
        with self._driver.session() as session:
            if clean_party in KNOWN_PARTIES:
                party_match = session.run(
                    "MATCH (p:Party) WHERE toLower(p.name) = toLower($pty) RETURN p.name AS name LIMIT 1",
                    pty=clean_party
                ).single()
                if party_match:
                    return party_match["name"]

            # 1. Match exato no banco (case-insensitive)
            q_exact = """
            MATCH (e:Entity)
            WHERE toLower(e.name) = toLower($name)
            RETURN e.name AS name
            LIMIT 1
            """
            res = session.run(q_exact, name=entity_query).single()
            if res:
                return res["name"]

            # 2. Busca Fulltext (Lucene)
            try:
                words = re.findall(r'\w+', entity_query)
                if words:
                    lucene_query = " AND ".join([f"{w}~" if len(w) > 3 else w for w in words])
                    q_fulltext = """
                    CALL db.index.fulltext.queryNodes("entity_name_fulltext", $search_str)
                    YIELD node, score
                    RETURN node.name AS name, score
                    ORDER BY score DESC
                    LIMIT 1
                    """
                    ft_res = session.run(q_fulltext, search_str=lucene_query).single()
                    if ft_res and ft_res.get("score", 0) > 1.0:
                        return ft_res["name"]
            except Exception:
                pass

            # 3. Match sem acentos em nós de Politician e Entity
            all_entities = self._get_all_entity_names()
            
            # Match exato sem acentos
            for ent in all_entities:
                if remove_accents(ent) == norm_query:
                    return ent

            # Match por palavra inteira ou substring qualificada
            substring_candidates = []
            for ent in all_entities:
                norm_ent = remove_accents(ent)
                if len(norm_query) < 4:
                    if re.search(r'\b' + re.escape(norm_query) + r'\b', norm_ent):
                        substring_candidates.append(ent)
                else:
                    if norm_query in norm_ent or norm_ent in norm_query:
                        substring_candidates.append(ent)

            if substring_candidates:
                substring_candidates.sort(key=lambda x: abs(len(remove_accents(x)) - len(norm_query)))
                return substring_candidates[0]

            # Match por sobreposição de termos
            query_words = set(re.findall(r'\b\w{3,}\b', norm_query))
            if query_words:
                best_match = None
                best_overlap = 0
                for ent in all_entities:
                    ent_words = set(re.findall(r'\b\w{3,}\b', remove_accents(ent)))
                    overlap = len(query_words.intersection(ent_words))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_match = ent

                if best_match and (best_overlap >= 2 or (len(query_words) == 1 and best_overlap == 1)):
                    return best_match

        return None
