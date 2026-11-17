
import unittest

from comparison_agent import comparison_agent_node


class TestComparisonAgent(unittest.TestCase):

    def setUp(self):
        self.valid_data = {
            "basis": "100g",
            "products": [
                {
                    "product_id": "produto_1",
                    "product_name": "Produto A",
                    "validated": True,
                    "source": "Rótulo confirmado",
                    "nutrients": {
                        "sodium": {"value": 120, "unit": "mg"},
                        "sugars": {"value": 5, "unit": "g"}
                    }
                },
                {
                    "product_id": "produto_2",
                    "product_name": "Produto B",
                    "validated": True,
                    "source": "Rótulo confirmado",
                    "nutrients": {
                        "sodium": {"value": 80, "unit": "mg"},
                        "sugars": {"value": 8, "unit": "g"}
                    }
                }
            ]
        }

        self.initial_state = {
            "request_type": "comparison",
            "enable_verifier": True,
            "text_query": None,
            "image_base64": None,
            "product_ids": ["produto_1", "produto_2"],
            "user_profile": {
                "has_diabetes": False,
                "has_hypertension": False
            },
            "extracted_ocr_data": None,
            "comparison_data": None,
            "rag_context": [],
            "draft_response": None,
            "matched_sources": [],
            "warnings": [],
            "classification_tone": "INCONCLUSIVO",
            "verification_passed": True,
            "verification_errors": []
        }

    def test_missing_data_returns_inconclusive(self):
        result = comparison_agent_node(self.initial_state)

        self.assertEqual(
            result["classification_tone"],
            "INCONCLUSIVO"
        )
        self.assertIn(
            "não foi possível realizar a comparação",
            result["draft_response"].lower()
        )

    def test_unvalidated_products_are_rejected(self):
        state = self.initial_state.copy()
        state["comparison_data"] = self.valid_data.copy()

        state["comparison_data"]["products"] = [
            product.copy()
            for product in self.valid_data["products"]
        ]

        state["comparison_data"]["products"][0]["validated"] = False

        result = comparison_agent_node(state)

        self.assertEqual(
            result["classification_tone"],
            "INCONCLUSIVO"
        )

    def test_valid_products_are_compared(self):
        state = self.initial_state.copy()
        state["comparison_data"] = self.valid_data

        result = comparison_agent_node(state)

        self.assertIn("Produto A", result["draft_response"])
        self.assertIn("Produto B", result["draft_response"])
        self.assertIn("120 mg", result["draft_response"])
        self.assertIn("80 mg", result["draft_response"])

    def test_comparison_does_not_recommend_healthier_product(self):
        state = self.initial_state.copy()
        state["comparison_data"] = self.valid_data

        result = comparison_agent_node(state)

        self.assertEqual(
            result["classification_tone"],
            "INCONCLUSIVO"
        )

        self.assertIn(
            "não determina, por si só",
            result["draft_response"]
        )

    def test_different_units_are_not_compared(self):
        data = {
            "basis": "100g",
            "products": [
                {
                    "product_name": "Produto A",
                    "validated": True,
                    "source": "Rótulo confirmado",
                    "nutrients": {
                        "sodium": {"value": 120, "unit": "mg"}
                    }
                },
                {
                    "product_name": "Produto B",
                    "validated": True,
                    "source": "Rótulo confirmado",
                    "nutrients": {
                        "sodium": {"value": 80, "unit": "g"}
                    }
                }
            ]
        }

        state = self.initial_state.copy()
        state["comparison_data"] = data

        result = comparison_agent_node(state)

        self.assertEqual(
            result["classification_tone"],
            "INCONCLUSIVO"
        )

        self.assertIn(
            "não existem nutrientes em comum",
            result["draft_response"]
        )


if __name__ == "__main__":
    unittest.main()
