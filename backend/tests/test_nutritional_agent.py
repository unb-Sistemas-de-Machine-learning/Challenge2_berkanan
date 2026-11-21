import unittest
from unittest.mock import patch

from nutritional_agent import (
    _deterministic_classification,
    nutritional_agent_node,
)
from rotulagem import LIMITES_RESERVA, classificar_alto_em


class TestNutritionalAgentDeterministicTone(unittest.TestCase):
    def test_high_sugar_is_always_evitar(self):
        dados = {
            "acucares_adicionados_g": 20,
            "gorduras_saturadas_g": 7,
            "sodio_mg": 700,
        }
        classificacao = classificar_alto_em(
            {
                "acucares_adicionados": 20,
                "gorduras_saturadas": 7,
                "sodio": 700,
            },
            "solido",
            LIMITES_RESERVA,
        )

        self.assertEqual(
            _deterministic_classification(dados, classificacao),
            "EVITAR",
        )

    def test_missing_product_values_are_inconclusive(self):
        dados = {}
        classificacao = classificar_alto_em(
            {
                "acucares_adicionados": None,
                "gorduras_saturadas": None,
                "sodio": None,
            },
            "solido",
            LIMITES_RESERVA,
        )

        self.assertEqual(
            _deterministic_classification(dados, classificacao),
            "INCONCLUSIVO",
        )

    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch(
        "nutritional_agent.query_knowledge_base",
        return_value=[
            {
                "text": "Limite literal da IN 75.",
                "source": "in_75_2020_dou.html",
                "similarity": 0.9,
                "source_title": "IN 75/2020",
            }
        ],
    )
    def test_llm_failure_preserves_evitar(
        self,
        _query_knowledge_base,
        _get_gemini_model,
    ):
        state = {
            "text_query": "Analise o produto",
            "extracted_ocr_data": {
                "acucares_adicionados_g": 20,
                "gorduras_saturadas_g": 7,
                "sodio_mg": 700,
            },
            "user_profile": {
                "has_diabetes": True,
                "has_hypertension": True,
            },
            "llm_calls": 0,
        }

        result = nutritional_agent_node(state)

        self.assertEqual(result["classification_tone"], "EVITAR")
        self.assertEqual(result["llm_calls"], 0)


if __name__ == "__main__":
    unittest.main()
