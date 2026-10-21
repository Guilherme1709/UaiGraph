import unittest
from database import normalize_party_name
from api import ChatRequest, GraphRequest
from pydantic import ValidationError

class TestGraphPolitics(unittest.TestCase):

    def test_normalize_party_name(self):
        self.assertEqual(normalize_party_name("PT"), "PT")
        self.assertEqual(normalize_party_name("pt-mg"), "PT")
        self.assertEqual(normalize_party_name("Partido dos Trabalhadores"), "PT")
        self.assertEqual(normalize_party_name("PL"), "PL")
        self.assertEqual(normalize_party_name("Podemos"), "PODE")
        self.assertEqual(normalize_party_name("União Brasil"), "UNIÃO")
        self.assertEqual(normalize_party_name(""), "S.PART.")

    def test_chat_request_validation(self):
        # Pergunta válida
        req = ChatRequest(question="Quem é Nikolas Ferreira?")
        self.assertEqual(req.question, "Quem é Nikolas Ferreira?")
        self.assertEqual(req.depth, 1)
        self.assertEqual(req.max_nodes, 25)

        # Pergunta muito curta deve falhar
        with self.assertRaises(ValidationError):
            ChatRequest(question="a")

        # Depth fora do range (máximo 3) deve falhar
        with self.assertRaises(ValidationError):
            ChatRequest(question="Pergunta válida", depth=10)

        # max_nodes=300 (opção Grafo Completo do frontend) deve passar com sucesso
        req_full = ChatRequest(question="Pergunta válida", max_nodes=300)
        self.assertEqual(req_full.max_nodes, 300)

        # max_nodes fora do range (máximo 500) deve falhar
        with self.assertRaises(ValidationError):
            ChatRequest(question="Pergunta válida", max_nodes=600)

    def test_graph_request_validation(self):
        req = GraphRequest(entities=["Nikolas Ferreira", "PL"], depth=2, max_nodes=30)
        self.assertEqual(len(req.entities), 2)
        self.assertEqual(req.depth, 2)

        # Mais de 10 entidades deve falhar
        with self.assertRaises(ValidationError):
            GraphRequest(entities=[f"Entidade {i}" for i in range(15)])

if __name__ == '__main__':
    unittest.main()
