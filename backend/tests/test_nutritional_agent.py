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

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem")
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_database_available_uses_postgres_limits(
        self,
        _query,
        _model,
        get_limits,
        get_taco,
    ):
        get_limits.return_value = [
            {
                "categoria": "sólido",
                "nutriente": "açúcares adicionados",
                "limite_100g": 15,
                "unidade": "g",
                "trecho_norma": "Limite sólido.",
            },
            {
                "categoria": "líquido",
                "nutriente": "açúcares adicionados",
                "limite_100g": 7.5,
                "unidade": "g",
                "trecho_norma": "Limite líquido.",
            },
            {
                "categoria": "sólido",
                "nutriente": "gorduras saturadas",
                "limite_100g": 6,
                "unidade": "g",
                "trecho_norma": "Limite gorduras.",
            },
            {
                "categoria": "líquido",
                "nutriente": "gorduras saturadas",
                "limite_100g": 3,
                "unidade": "g",
                "trecho_norma": "Limite gorduras líquido.",
            },
            {
                "categoria": "sólido",
                "nutriente": "sódio",
                "limite_100g": 600,
                "unidade": "mg",
                "trecho_norma": "Limite sódio.",
            },
            {
                "categoria": "líquido",
                "nutriente": "sódio",
                "limite_100g": 300,
                "unidade": "mg",
                "trecho_norma": "Limite sódio líquido.",
            },
        ]
        state = {
            "text_query": "Analise",
            "extracted_ocr_data": {"tipo_alimento": "solido", "sodio_mg": 700},
            "llm_calls": 0,
        }

        result = nutritional_agent_node(state)

        get_limits.assert_called_once_with()
        get_taco.assert_not_called()
        self.assertEqual(result["classification_tone"], "EVITAR")

    @patch("nutritional_agent.database.get_taco_alimento")
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_database_unavailable_uses_reserve_and_warning(
        self,
        _query,
        _model,
        get_limits,
        get_taco,
    ):
        state = {
            "text_query": "Analise",
            "extracted_ocr_data": {
                "acucares_adicionados_g": 20,
                "gorduras_saturadas_g": 7,
                "sodio_mg": 700,
                "tipo_alimento": "solido",
            },
            "llm_calls": 0,
        }

        with patch("nutritional_agent.logger.warning") as warning:
            result = nutritional_agent_node(state)

        get_limits.assert_called_once_with()
        get_taco.assert_not_called()
        self.assertEqual(result["classification_tone"], "EVITAR")
        warning.assert_any_call(
            "limites da reserva em código, banco indisponível"
        )

    @patch("nutritional_agent.database.get_taco_alimento")
    @patch(
        "nutritional_agent.database.get_limites_rotulagem",
        side_effect=Exception("db fora"),
    )
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_database_exception_uses_reserve_and_warning(
        self,
        _query,
        _model,
        get_limits,
        get_taco,
    ):
        state = {
            "text_query": "Analise",
            "extracted_ocr_data": {
                "acucares_adicionados_g": 20,
                "gorduras_saturadas_g": 7,
                "sodio_mg": 700,
                "tipo_alimento": "solido",
            },
            "llm_calls": 0,
        }

        result = nutritional_agent_node(state)

        get_limits.assert_called_once_with()
        get_taco.assert_not_called()
        self.assertEqual(result["classification_tone"], "EVITAR")
        self.assertTrue(any(
            "reserva" in warning.lower() and "banco" in warning.lower()
            for warning in result["warnings"]
        ))

    @patch("nutritional_agent.database.get_taco_alimento")
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_taco_is_not_queried_by_product_name(
        self,
        _query,
        _model,
        _get_limits,
        get_taco,
    ):
        state = {
            "text_query": "Analise",
            "extracted_ocr_data": {
                "product_name": "Produto qualquer",
            },
            "llm_calls": 0,
        }

        nutritional_agent_node(state)

        get_taco.assert_not_called()


if __name__ == "__main__":
    unittest.main()
