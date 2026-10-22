"""
Testes unitários para o ChatService: orquestração do RAG e roteamento de intenção.
Utiliza mocks para isolar dependências externas (Neo4j e provedores de LLM).
"""

import unittest
from unittest.mock import MagicMock
from app.services.chat_service import ChatService

class TestChatService(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_extractor = MagicMock()
        self.mock_generator = MagicMock()

        self.service = ChatService(
            db=self.mock_db,
            entity_extractor=self.mock_extractor,
            answer_generator=self.mock_generator
        )

    def test_empty_question_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.service.process_chat_query("")
        with self.assertRaises(ValueError):
            self.service.process_chat_query("   ")

    def test_intent_detection(self):
        # Detecção de partidos/bancada
        intents = self.service.detect_intent("Quantos deputados foram eleitos pelo PL?")
        self.assertTrue(intents["is_party_query"])
        self.assertFalse(intents["is_bills_query"])

        # Detecção de projetos de lei
        intents = self.service.detect_intent("Quais os principais projetos de lei apresentados?")
        self.assertTrue(intents["is_bills_query"])

        # Detecção de colegas de partido
        intents = self.service.detect_intent("Quem são os outros deputados do mesmo partido de Nikolas Ferreira?")
        self.assertTrue(intents["is_colleagues_query"])

    def test_flow_no_entities_bills_query(self):
        self.mock_extractor.return_value = []
        self.mock_db.get_bancada_bills_context.return_value = "Contexto Projetos"
        self.mock_db.get_bancada_bills_subgraph.return_value = {"nodes": [], "edges": []}
        self.mock_generator.return_value = "Resposta sobre projetos"

        res = self.service.process_chat_query("Quais os principais projetos da bancada de MG?")

        self.mock_db.get_bancada_bills_context.assert_called_once_with(limit=25)
        self.mock_db.get_bancada_bills_subgraph.assert_called_once_with(max_nodes=25)
        self.assertEqual(res["entities"], ["Bancada MG", "Proposições"])
        self.assertEqual(res["answer"], "Resposta sobre projetos")

    def test_flow_no_entities_parties_query(self):
        self.mock_extractor.return_value = []
        self.mock_db.get_bancada_parties_context.return_value = "Contexto Bancada"
        self.mock_db.get_parties_subgraph.return_value = {"nodes": [], "edges": []}
        self.mock_generator.return_value = "Resposta sobre bancada"

        res = self.service.process_chat_query("Quais partidos compõem a bancada de MG?")

        self.mock_db.get_bancada_parties_context.assert_called_once()
        self.mock_db.get_parties_subgraph.assert_called_once_with(max_nodes=25)
        self.assertEqual(res["entities"], ["Bancada MG", "Partidos"])

    def test_flow_single_entity_colleagues_query(self):
        self.mock_extractor.return_value = ["Nikolas Ferreira"]
        self.mock_db.get_party_colleagues_subgraph.return_value = {"nodes": ["Nó PL"], "edges": []}
        self.mock_db.get_context_for_entities.return_value = "Contexto Colegas"
        self.mock_generator.return_value = "Resposta Colegas"
        self.mock_db.get_politician_details.return_value = {"name": "Nikolas Ferreira", "party": "PL"}

        res = self.service.process_chat_query("Quais os deputados do mesmo partido de Nikolas Ferreira?")

        self.mock_db.get_party_colleagues_subgraph.assert_called_once_with("Nikolas Ferreira", max_nodes=25)
        self.mock_db.get_context_for_entities.assert_called_once_with(["Nikolas Ferreira"], depth=2, include_colleagues=True)
        self.assertEqual(res["politician"]["name"], "Nikolas Ferreira")

    def test_flow_multi_entity_query(self):
        self.mock_extractor.return_value = ["Aécio Neves", "PSDB"]
        self.mock_db.get_context_for_entities.return_value = "Contexto Aécio e PSDB"
        self.mock_db.get_subgraph_data_for_entities.return_value = {"nodes": ["Aécio", "PSDB"], "edges": []}
        self.mock_generator.return_value = "Resposta Relação"
        self.mock_db.get_politician_details.side_effect = lambda name: {"name": name} if name == "Aécio Neves" else None

        res = self.service.process_chat_query("Qual a relação entre Aécio Neves e o PSDB?", depth=2, max_nodes=30)

        self.mock_db.get_context_for_entities.assert_called_once_with(["Aécio Neves", "PSDB"], depth=2, include_colleagues=False)
        self.mock_db.get_subgraph_data_for_entities.assert_called_once_with(["Aécio Neves", "PSDB"], max_nodes=30, depth=2)
        self.assertEqual(res["politician"]["name"], "Aécio Neves")

if __name__ == '__main__':
    unittest.main()
