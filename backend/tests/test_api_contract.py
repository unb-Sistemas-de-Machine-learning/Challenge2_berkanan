import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import api


class TestAnalysisRequestContract(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api)

    def _post_without_external_services(self, payload):
        with (
            patch("main.record_metric"),
            patch("nutritional_agent.database.get_limites_rotulagem", return_value=[]),
            patch("nutritional_agent.query_knowledge_base", return_value=[]),
            patch("nutritional_agent.socket.create_connection"),
            patch("nutritional_agent._get_gemini_model", return_value=None),
        ):
            return self.client.post("/api/analyze", json=payload)

    def test_confirmed_data_is_classified_deterministically(self):
        response = self._post_without_external_services({
            "request_type": "ocr_analysis",
            "enable_verifier": False,
            "confirmed_data": {
                "tipo_alimento": "liquido",
                "acucares_adicionados_g": 10,
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"], "EVITAR")

    def test_legacy_text_json_remains_compatible(self):
        response = self._post_without_external_services({
            "request_type": "ocr_analysis",
            "enable_verifier": False,
            "text": json.dumps({
                "tipo_alimento": "liquido",
                "categoria_produto": "bebida",
                "values_per_100g": {"acucares_adicionados_g": 10},
            }),
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"], "EVITAR")

    def test_confirmed_data_takes_priority_over_json_text(self):
        payload = {
            "request_type": "ocr_analysis",
            "enable_verifier": False,
            "text": json.dumps({
                "tipo_alimento": "liquido",
                "values_per_100g": {"acucares_adicionados_g": 10},
            }),
            "confirmed_data": {
                "tipo_alimento": "liquido",
                "values_per_100g": {"acucares_adicionados_g": 0},
            },
        }
        with (
            patch("main.record_metric"),
            patch("nutritional_agent.database.get_limites_rotulagem", return_value=[]),
            patch("nutritional_agent.query_knowledge_base", return_value=[]) as query,
            patch("nutritional_agent.socket.create_connection"),
            patch("nutritional_agent._get_gemini_model", return_value=None),
        ):
            response = self.client.post("/api/analyze", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["classification"], "EVITAR")
        self.assertEqual(
            query.call_args.args[0],
            "Rótulo nutricional açúcar gordura saturada sódio alergênicos IN 75 RDC 429",
        )

    def test_confirmed_data_without_tipo_is_inconclusive(self):
        response = self._post_without_external_services({
            "request_type": "ocr_analysis",
            "enable_verifier": False,
            "confirmed_data": {
                "values_per_100g": {"acucares_adicionados_g": 10},
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"], "INCONCLUSIVO")
        self.assertTrue(any(
            "Tipo do produto (sólido ou líquido) não informado" in warning
            for warning in response.json()["warnings"]
        ))

    def test_validated_comparison_data_reaches_comparison_agent(self):
        response = self._post_without_external_services({
            "request_type": "comparison",
            "enable_verifier": False,
            "comparison_data": {
                "basis": "100g",
                "products": [
                    {
                        "product_name": "Produto A",
                        "source": "Rótulo confirmado",
                        "validated": True,
                        "nutrients": {"sodium": {"value": 120, "unit": "mg"}},
                    },
                    {
                        "product_name": "Produto B",
                        "source": "Rótulo confirmado",
                        "validated": True,
                        "nutrients": {"sodium": {"value": 80, "unit": "mg"}},
                    },
                ],
            },
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("Comparação entre Produto A e Produto B", response.json()["llm_explanation"])
        self.assertNotIn(
            "São necessários dados nutricionais validados de exatamente dois produtos",
            response.json()["llm_explanation"],
        )

    def test_comparison_without_data_keeps_refusal(self):
        response = self._post_without_external_services({
            "request_type": "comparison",
            "enable_verifier": False,
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "São necessários dados nutricionais validados de exatamente dois produtos",
            response.json()["llm_explanation"],
        )


if __name__ == "__main__":
    unittest.main()
