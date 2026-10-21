import unittest
from fastapi.testclient import TestClient
from api import app

class TestApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        # Se o banco estiver acessível ou mockado, retorna 200
        self.assertIn(response.status_code, [200, 503])
        data = response.json()
        self.assertIn("service", data)

    def test_invalid_chat_payload(self):
        # Pergunta com menos de 2 caracteres deve retornar 422 Unprocessable Entity
        response = self.client.post("/api/chat", json={"question": "a"})
        self.assertEqual(response.status_code, 422)

    def test_depth_out_of_bounds(self):
        response = self.client.post("/api/chat", json={"question": "Quem é o deputado?", "depth": 99})
        self.assertEqual(response.status_code, 422)

if __name__ == '__main__':
    unittest.main()
