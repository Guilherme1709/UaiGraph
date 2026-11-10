import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api import app

class TestApiEndpoints(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch("app.api.routes.db.verify_health", return_value=True)
    def test_health_check(self, mock_health):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("service", data)
        self.assertEqual(data["database"], "connected")
        mock_health.assert_called_once()

    @patch("app.api.routes.db.verify_health", return_value=False)
    def test_health_check_unavailable(self, mock_health):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"]["database"], "unavailable")
        self.assertEqual(response.json()["detail"]["status"], "degraded")
        mock_health.assert_called_once()

    def test_invalid_chat_payload(self):
        # Pergunta com menos de 2 caracteres deve retornar 422 Unprocessable Entity
        response = self.client.post("/api/chat", json={"question": "a"})
        self.assertEqual(response.status_code, 422)

    def test_depth_out_of_bounds(self):
        response = self.client.post("/api/chat", json={"question": "Quem é o deputado?", "depth": 99})
        self.assertEqual(response.status_code, 422)

if __name__ == '__main__':
    unittest.main()
