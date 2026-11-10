"""
Serviço de orquestração do RAG e roteamento semântico por intenção da pergunta.
Isola a inteligência do fluxo de consulta da camada de transporte HTTP.
"""

import logging
from typing import Optional, List, Dict, Any, Callable
from app.graph import Neo4jManager
from app.llm import get_entities_from_question, generate_final_answer

logger = logging.getLogger("graphpolitics.services.chat")

class ChatService:
    """Orquestra extração de entidades, busca contextual no grafo, roteamento de intenção e resposta via LLM."""

    def __init__(
        self,
        db: Optional[Neo4jManager] = None,
        entity_extractor: Optional[Callable[[str], List[str]]] = None,
        answer_generator: Optional[Callable[[str, str], str]] = None
    ):
        self.db = db
        self.entity_extractor = entity_extractor or get_entities_from_question
        self.answer_generator = answer_generator or generate_final_answer

    def _ensure_db(self) -> Neo4jManager:
        if self.db is None:
            self.db = Neo4jManager()
        return self.db

    def detect_intent(self, question: str) -> Dict[str, bool]:
        """Detecta intenções semânticas da pergunta do usuário."""
        q_lower = question.lower()
        return {
            "is_party_query": any(w in q_lower for w in ['partid', 'eleito', 'sigla', 'bancada', 'legenda', 'quantos deputados']),
            "is_bills_query": any(w in q_lower for w in ['projet', 'propost', 'leis', 'principais pl', 'produção']),
            "is_colleagues_query": any(w in q_lower for w in ['mesmo partid', 'mesma legend', 'mesma sigl', 'colegas', 'companheiros', 'outros deputados'])
        }

    def process_chat_query(
        self,
        question: str,
        depth: int = 1,
        max_nodes: int = 25
    ) -> Dict[str, Any]:
        """
        Executa o pipeline RAG completo:
        1. Extração multi-entidade
        2. Roteamento por intenção e recuperação de contexto + subgrafo
        3. Síntese grounded via LLM
        4. Recuperação do card oficial de parlamentar (se presente)
        """
        clean_question = question.strip()
        if not clean_question:
            raise ValueError("A pergunta não pode estar vazia.")

        db = self._ensure_db()
        rag_depth = 2  # Profundidade semântica padrão para contexto textual
        graph_depth = max(1, min(depth or 1, 3))
        safe_max_nodes = max(5, min(max_nodes or 25, 500))

        # Extração multi-entidade
        entities = self.entity_extractor(clean_question)
        intents = self.detect_intent(clean_question)

        # Roteamento de contexto e subgrafo
        if not entities:
            if intents["is_bills_query"]:
                context = db.get_bancada_bills_context(limit=25)
                subgraph = db.get_bancada_bills_subgraph(max_nodes=safe_max_nodes)
                resolved_entities = ["Bancada MG", "Proposições"]
            else:
                context = db.get_bancada_parties_context()
                subgraph = db.get_parties_subgraph(max_nodes=safe_max_nodes)
                resolved_entities = ["Bancada MG", "Partidos"]
        else:
            resolved_entities = entities
            if intents["is_colleagues_query"] and len(entities) == 1:
                subgraph = db.get_party_colleagues_subgraph(entities[0], max_nodes=safe_max_nodes)
                context = db.get_context_for_entities(entities, depth=2, include_colleagues=True)
            else:
                context = db.get_context_for_entities(entities, depth=rag_depth, include_colleagues=False)
                subgraph = db.get_subgraph_data_for_entities(entities, max_nodes=safe_max_nodes, depth=graph_depth)

        # Geração da resposta fundamentada
        answer = self.answer_generator(context, clean_question)

        # Busca do perfil oficial de parlamentar se aplicável
        politician_card = None
        for ent in resolved_entities:
            pol = db.get_politician_details(ent)
            if pol:
                politician_card = pol
                break

        return {
            "question": clean_question,
            "entities": resolved_entities,
            "answer": answer,
            "graph": subgraph,
            "politician": politician_card
        }
