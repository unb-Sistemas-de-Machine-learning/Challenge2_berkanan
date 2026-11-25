
import unittest
from unittest.mock import Mock, patch

from verifier_agent import verifier_agent_llm_node, verifier_agent_node


class TestVerifierAgent(unittest.TestCase):

    def setUp(self):
        self.state = {
            "request_type": "qa",
            "enable_verifier": True,
            "text_query": "Pergunta de teste",
            "image_base64": None,
            "product_ids": None,
            "user_profile": {},
            "extracted_ocr_data": None,
            "comparison_data": None,
            "rag_context": [],
            "draft_response": "Resposta fundamentada em documento oficial.",
            "matched_sources": [
                {
                    "text": "Trecho de documento oficial.",
                    "source": "documento_oficial.pdf",
                    "similarity": 0.92,
                    "source_url": "https://www.gov.br",
                    "source_title": "Documento oficial"
                }
            ],
            "warnings": [],
            "classification_tone": "ATENCAO",
            "verification_passed": True,
            "verification_errors": []
        }

    def test_valid_response_with_source_passes(self):
        result = verifier_agent_node(self.state)

        self.assertTrue(result["verification_passed"])
        self.assertEqual(result["verification_errors"], [])

    def test_empty_response_fails(self):
        state = self.state.copy()
        state["draft_response"] = ""

        result = verifier_agent_node(state)

        self.assertFalse(result["verification_passed"])
        self.assertTrue(result["verification_errors"])

    def test_response_without_sources_fails(self):
        state = self.state.copy()
        state["matched_sources"] = []

        result = verifier_agent_node(state)

        self.assertFalse(result["verification_passed"])
        self.assertIn(
            "V02: Resposta sem fontes documentais.",
            result["verification_errors"]
        )

    def test_inconclusive_response_without_sources_passes(self):
        state = self.state.copy()
        state["classification_tone"] = "INCONCLUSIVO"
        state["draft_response"] = (
            "Não há evidência suficiente para responder."
        )
        state["matched_sources"] = []

        result = verifier_agent_node(state)

        self.assertTrue(result["verification_passed"])
        self.assertEqual(result["verification_errors"], [])

    def test_inconclusive_without_explicit_explanation_fails(self):
        state = self.state.copy()
        state["classification_tone"] = "INCONCLUSIVO"
        state["draft_response"] = "Produto A apresenta 10 mg."
        state["matched_sources"] = []

        result = verifier_agent_node(state)

        self.assertFalse(result["verification_passed"])

    def test_source_without_text_fails(self):
        state = self.state.copy()
        state["matched_sources"] = [
            {
                "text": "",
                "source": "documento.pdf",
                "similarity": 0.90
            }
        ]

        result = verifier_agent_node(state)

        self.assertFalse(result["verification_passed"])
        self.assertTrue(
            any("texto válido" in error
                for error in result["verification_errors"])
        )

    def test_invalid_similarity_fails(self):
        state = self.state.copy()
        state["matched_sources"][0]["similarity"] = 1.5

        result = verifier_agent_node(state)

        self.assertFalse(result["verification_passed"])
        self.assertTrue(
            any("Similaridade" in error
                for error in result["verification_errors"])
        )

    def test_source_without_identifier_fails(self):
        state = self.state.copy()
        state["matched_sources"][0]["source"] = ""

        result = verifier_agent_node(state)

        self.assertFalse(result["verification_passed"])
        self.assertTrue(
            any("identificação" in error
                for error in result["verification_errors"])
        )

    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "test-api-key",
        "LLM_MODEL": "test-model",
        "MAX_LLM_CALLS_PER_RESPONSE": "2",
    })
    @patch("verifier_agent._gemini_client")
    def test_llm_verifier_accepts_only_exact_sim(self, gemini_client):
        cases = [
            ("SIM", True),
            ("NAO", False),
            ("SIM, mas...", False),
            ("NÃO SIM", False),
        ]
        for text, passed in cases:
            with self.subTest(text=text):
                client = Mock()
                client.models.generate_content.return_value.text = text
                gemini_client.return_value = client
                state = dict(self.state)
                state["llm_calls"] = 0

                result = verifier_agent_llm_node(state)

                self.assertEqual(result["verification_passed"], passed)
                self.assertEqual(result["llm_calls"], 1)

    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "test-api-key",
        "LLM_MODEL": "test-model",
        "MAX_LLM_CALLS_PER_RESPONSE": "2",
    })
    @patch("verifier_agent._gemini_client")
    def test_llm_verifier_exception_increments_attempt(self, gemini_client):
        client = Mock()
        client.models.generate_content.side_effect = RuntimeError("timeout")
        gemini_client.return_value = client
        state = dict(self.state)
        state["llm_calls"] = 0

        result = verifier_agent_llm_node(state)

        self.assertFalse(result["verification_passed"])
        self.assertEqual(result["llm_calls"], 1)
        self.assertTrue(
            any("Falha ao executar" in error for error in result["verification_errors"])
        )

    @patch.dict("os.environ", {
        "GEMINI_API_KEY": "test-api-key",
        "LLM_MODEL": "test-model",
        "MAX_LLM_CALLS_PER_RESPONSE": "1",
    })
    @patch("verifier_agent._gemini_client")
    def test_llm_verifier_respects_call_limit(self, gemini_client):
        state = dict(self.state)
        state["llm_calls"] = 1

        result = verifier_agent_llm_node(state)

        gemini_client.assert_not_called()
        self.assertFalse(result["verification_passed"])
        self.assertEqual(result["llm_calls"], 1)


if __name__ == "__main__":
    unittest.main()
