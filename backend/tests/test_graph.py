
import unittest

from graph import app


class TestGraph(unittest.TestCase):

    def setUp(self):
        self.initial_state = {
            "request_type": "comparison",
            "enable_verifier": False,
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

    def test_comparison_request_reaches_comparison_agent(self):
        result = app.invoke(self.initial_state)

        self.assertEqual(
            result["classification_tone"],
            "INCONCLUSIVO"
        )

        self.assertIn(
            "Não foi possível realizar a comparação",
            result["draft_response"]
        )

    def test_comparison_runs_verifier_when_enabled(self):
        state = self.initial_state.copy()
        state["enable_verifier"] = True

        result = app.invoke(state)

        self.assertTrue(result["verification_passed"])
        self.assertEqual(result["verification_errors"], [])

    def test_comparison_skips_verifier_when_disabled(self):
        result = app.invoke(self.initial_state)

        self.assertTrue(result["verification_passed"])
        self.assertEqual(result["verification_errors"], [])

    def test_invalid_request_ends_with_error(self):
        state = self.initial_state.copy()
        state["request_type"] = "invalid_type"

        result = app.invoke(state)

        self.assertEqual(
            result["classification_tone"],
            "ERRO"
        )

        self.assertFalse(result["verification_passed"])
        self.assertTrue(result["draft_response"])


if __name__ == "__main__":
    unittest.main()
