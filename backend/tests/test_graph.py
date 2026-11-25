
import unittest
from unittest.mock import Mock, patch

from graph import app


class TestGraph(unittest.TestCase):

    def setUp(self):
        self.initial_state = {
            "request_type": "comparison",
            "enable_verifier": False,
            "verifier_mode": "rules",
            "llm_calls": 0,
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
        state["verifier_mode"] = "rules"

        result = app.invoke(state)

        self.assertTrue(result["verification_passed"])
        self.assertEqual(result["verification_errors"], [])

    def test_comparison_skips_verifier_when_disabled(self):
        result = app.invoke(self.initial_state)

        self.assertNotIn("verification_passed", result)

    def test_enable_verifier_rules_passes_through_rules_node(self):
        state = self.initial_state.copy()
        state["enable_verifier"] = True
        state["verifier_mode"] = "rules"

        result = app.invoke(state)

        self.assertIn("verification_passed", result)
        self.assertTrue(result["verification_passed"])

    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "test-api-key",
        "LLM_MODEL": "test-model",
        "MAX_LLM_CALLS_PER_RESPONSE": "2",
    })
    @patch("verifier_agent._gemini_client")
    def test_enable_verifier_llm_passes_through_llm_node(self, gemini_client):
        client = Mock()
        client.models.generate_content.return_value.text = "SIM"
        gemini_client.return_value = client
        state = self.initial_state.copy()
        state["enable_verifier"] = True
        state["verifier_mode"] = "llm"

        result = app.invoke(state)

        self.assertIn("verification_passed", result)
        self.assertTrue(result["verification_passed"])
        self.assertEqual(result["llm_calls"], 1)

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
