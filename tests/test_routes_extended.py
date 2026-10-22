"""
Testes de rotas adicionais da API HTTP (Root, Suggestions, Politician e Bill endpoints).
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.api.main import app

class TestExtendedRoutes(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "online")
        self.assertIn("service", data)

    def test_suggestions_endpoint(self):
        response = self.client.get("/api/suggestions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("popular_politicians", data)
        self.assertIn("sample_questions", data)
        self.assertTrue(len(data["sample_questions"]) > 0)

    @patch("app.api.routes.db.get_politician_details")
    def test_get_politician_found(self, mock_get_details):
        mock_get_details.return_value = {
            "name": "Nikolas Ferreira",
            "party": "PL",
            "photo_url": "http://foto.jpg",
            "total_bills": 10
        }
        response = self.client.get("/api/politician/Nikolas Ferreira")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Nikolas Ferreira")
        self.assertEqual(data["party"], "PL")

    @patch("app.api.routes.db.get_politician_details")
    def test_get_politician_not_found(self, mock_get_details):
        mock_get_details.return_value = None
        response = self.client.get("/api/politician/Desconhecido")
        self.assertEqual(response.status_code, 404)

    def test_get_politician_invalid_name(self):
        response = self.client.get("/api/politician/%20")
        self.assertEqual(response.status_code, 400)

    @patch("app.api.routes.db.get_bill_details")
    def test_get_bill_found(self, mock_get_bill):
        mock_get_bill.return_value = {
            "name": "PL 1234/2023",
            "ementa": "Institui diretrizes para...",
            "tipo": "PL",
            "numero": "1234",
            "ano": "2023"
        }
        response = self.client.get("/api/bill/PL 1234/2023")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "PL 1234/2023")
        self.assertEqual(data["ementa"], "Institui diretrizes para...")

if __name__ == '__main__':
    unittest.main()
