
import unittest

from verifier_agent import verifier_agent_node


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


if __name__ == "__main__":
    unittest.main()
