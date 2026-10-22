"""
Módulo de grafos Neo4j: conexão, esquema, resolução de entidades, repositório,
contexto RAG e subgrafos visuais.
Exporta Neo4jManager para compatibilidade com a interface legada.
"""

from typing import List, Optional
from neo4j import Driver
from app.graph.connection import Neo4jConnection
from app.graph.resolver import EntityResolver
from app.graph.repositories import GraphRepository
from app.graph.context import GraphContextProvider
from app.graph.subgraph import GraphVisualizer

class Neo4jManager:
    """
    Fachada unificada para o ecossistema de grafos.
    Integra conexão, resolução, persistência, geração de contexto RAG e subgrafos visuais.
    """

    def __init__(self, uri: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None):
        self._connection = Neo4jConnection(uri, user, password)
        self._resolver = EntityResolver(self._connection.driver)
        self._repo = GraphRepository(self._connection.driver, resolve_fn=self._resolver.resolve_entity)
        self._context = GraphContextProvider(
            self._connection.driver,
            resolve_fn=self._resolver.resolve_entity,
            get_profile_fn=self._repo.get_politician_details
        )
        self._visualizer = GraphVisualizer(self._connection.driver, resolve_fn=self._resolver.resolve_entity)

    @property
    def driver(self) -> Driver:
        return self._connection.driver

    def close(self):
        self._connection.close()

    def verify_health(self) -> bool:
        return self._connection.verify_health()

    def init_schema(self):
        self._connection.init_schema()

    def resolve_entity(self, entity_query: str) -> Optional[str]:
        return self._resolver.resolve_entity(entity_query)

    def _get_all_entity_names(self) -> List[str]:
        return self._resolver._get_all_entity_names()

    def _resolve_entity_uncached(self, entity_query: str) -> Optional[str]:
        return self._resolver._resolve_entity_uncached(entity_query)

    def save_structured_triple(self, subj: str, subj_label: str, rel: str, obj: str, obj_label: str):
        self._repo.save_structured_triple(subj, subj_label, rel, obj, obj_label)

    def save_politician_profile(self, name: str, party: str, photo_url: Optional[str] = None,
                                email: Optional[str] = None, camara_id: Optional[int] = None,
                                uf: str = "MG", gabinete: Optional[str] = None, bio: Optional[str] = None):
        self._repo.save_politician_profile(name, party, photo_url, email, camara_id, uf, gabinete, bio)

    def get_politician_details(self, name: str) -> Optional[dict]:
        return self._repo.get_politician_details(name)

    def get_bill_details(self, bill_name: str) -> Optional[dict]:
        return self._repo.get_bill_details(bill_name)

    def get_graph_stats(self) -> dict:
        return self._repo.get_graph_stats()

    def get_popular_politicians(self, limit: int = 8) -> List[dict]:
        return self._repo.get_popular_politicians(limit=limit)

    def get_all_politicians(self) -> List[dict]:
        return self._repo.get_all_politicians()

    def find_paths_between(self, entity_a: str, entity_b: str, max_depth: int = 3) -> List[str]:
        return self._context.find_paths_between(entity_a, entity_b, max_depth=max_depth)

    def get_context_for_entities(self, entities: List[str], depth: int = 2, include_colleagues: bool = False) -> str:
        return self._context.get_context_for_entities(entities, depth=depth, include_colleagues=include_colleagues)

    def _get_direct_relations(self, entity_name: str, limit: int = 25) -> List[str]:
        return self._context._get_direct_relations(entity_name, limit=limit)

    def _get_second_hop_relations(self, entity_name: str, limit: int = 20) -> List[str]:
        return self._context._get_second_hop_relations(entity_name, limit=limit)

    def get_bancada_parties_context(self) -> str:
        return self._context.get_bancada_parties_context()

    def get_bancada_bills_context(self, limit: int = 25) -> str:
        return self._context.get_bancada_bills_context(limit=limit)

    def get_context_multi_hop(self, entity_name: str, depth: int = 2) -> str:
        return self._context.get_context_multi_hop(entity_name, depth=depth)

    def get_parties_subgraph(self, max_nodes: int = 40) -> dict:
        return self._visualizer.get_parties_subgraph(max_nodes=max_nodes)

    def get_party_colleagues_subgraph(self, politician_or_party: str, max_nodes: int = 50) -> dict:
        return self._visualizer.get_party_colleagues_subgraph(politician_or_party, max_nodes=max_nodes)

    def get_bancada_bills_subgraph(self, max_nodes: int = 40) -> dict:
        return self._visualizer.get_bancada_bills_subgraph(max_nodes=max_nodes)

    def get_subgraph_data_for_entities(self, entities: List[str], max_nodes: int = 40, depth: int = 1) -> dict:
        return self._visualizer.get_subgraph_data_for_entities(entities, max_nodes=max_nodes, depth=depth)

__all__ = [
    "Neo4jConnection",
    "EntityResolver",
    "GraphRepository",
    "GraphContextProvider",
    "GraphVisualizer",
    "Neo4jManager",
]
