import unittest
from types import SimpleNamespace
from unittest.mock import patch

from nutritional_agent import (
    AVISO_SAUDAVEL,
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
                "tipo_alimento": "solido",
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

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_saudavel_includes_fixed_warning(
        self,
        _query,
        _model,
        _get_limits,
        _get_taco,
    ):
        result = nutritional_agent_node({
            "extracted_ocr_data": {
                "tipo_alimento": "solido",
                "acucares_adicionados_g": 0,
                "gorduras_saturadas_g": 0,
                "sodio_mg": 0,
                "alergicos_contem": "",
                "alergicos_pode_conter": "",
            },
            "llm_calls": 0,
        })

        self.assertEqual(result["classification_tone"], "SAUDAVEL")
        self.assertIn(AVISO_SAUDAVEL, result["warnings"])

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_non_saudavel_has_no_fixed_warning(
        self,
        _query,
        _model,
        _get_limits,
        _get_taco,
    ):
        result = nutritional_agent_node({
            "extracted_ocr_data": {
                "tipo_alimento": "solido",
                "acucares_adicionados_g": 20,
                "gorduras_saturadas_g": 0,
                "sodio_mg": 0,
                "alergicos_contem": "",
                "alergicos_pode_conter": "",
            },
            "llm_calls": 0,
        })

        self.assertEqual(result["classification_tone"], "EVITAR")
        self.assertNotIn(AVISO_SAUDAVEL, result["warnings"])

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[])
    def test_missing_tipo_is_inconclusive(
        self,
        _query,
        _model,
        _get_limits,
        _get_taco,
    ):
        result = nutritional_agent_node({
            "extracted_ocr_data": {
                "acucares_adicionados_g": 10,
            },
            "llm_calls": 0,
        })

        self.assertEqual(result["classification_tone"], "INCONCLUSIVO")
        self.assertIn(
            "Tipo do produto (sólido ou líquido) não informado; "
            "confirme o tipo antes da análise.",
            result["warnings"],
        )
        self.assertIn("confirmação", result["draft_response"].lower())

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[])
    def test_missing_tipo_declares_insufficient_evidence(
        self,
        _query,
        _model,
        _get_limits,
        _get_taco,
    ):
        result = nutritional_agent_node({
            "extracted_ocr_data": {"acucares_adicionados_g": 10},
            "llm_calls": 0,
        })

        self.assertIn(
            "não há evidência suficiente",
            result["draft_response"].lower(),
        )

    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch(
        "nutritional_agent.query_knowledge_base",
        return_value=[
            {
                "text": "Orientação oficial.",
                "source": "guia_alimentar.pdf",
                "similarity": 0.9,
            }
        ],
    )
    @patch("nutritional_agent.socket.create_connection")
    def test_qa_without_product_queries_rag(
        self,
        _create_connection,
        query_knowledge_base,
        _get_gemini_model,
        _get_limits,
    ):
        result = nutritional_agent_node({
            "request_type": "qa",
            "text_query": "O que recomenda o Guia Alimentar?",
            "extracted_ocr_data": {},
            "llm_calls": 0,
        })

        query_knowledge_base.assert_called_once()
        self.assertTrue(result["matched_sources"])

    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch(
        "nutritional_agent.query_knowledge_base",
        return_value=[
            {
                "text": "Orientação oficial.",
                "source": "guia_alimentar.pdf",
                "similarity": 0.9,
            }
        ],
    )
    @patch("nutritional_agent.socket.create_connection")
    def test_qa_without_product_has_no_allergen_warning(
        self,
        _create_connection,
        _query_knowledge_base,
        _get_gemini_model,
        _get_limits,
    ):
        result = nutritional_agent_node({
            "request_type": "qa",
            "text_query": "O que recomenda o Guia Alimentar?",
            "llm_calls": 0,
        })

        self.assertFalse(any("ALÉRGICOS" in warning for warning in result["warnings"]))

    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[])
    @patch("nutritional_agent.socket.create_connection")
    def test_qa_without_product_and_sources_declares_insufficient_evidence(
        self,
        _create_connection,
        _query_knowledge_base,
        _get_gemini_model,
        _get_limits,
    ):
        result = nutritional_agent_node({
            "request_type": "qa",
            "text_query": "Pergunta sem cobertura.",
            "extracted_ocr_data": None,
            "llm_calls": 0,
        })

        self.assertEqual(result["classification_tone"], "INCONCLUSIVO")
        self.assertIn(
            "não há evidência suficiente",
            result["draft_response"].lower(),
        )

    @patch("nutritional_agent.query_knowledge_base")
    def test_ocr_analysis_without_tipo_still_requires_tipo(
        self,
        query_knowledge_base,
    ):
        result = nutritional_agent_node({
            "request_type": "ocr_analysis",
            "extracted_ocr_data": {"acucares_adicionados_g": 10},
            "llm_calls": 0,
        })

        query_knowledge_base.assert_not_called()
        self.assertEqual(result["classification_tone"], "INCONCLUSIVO")
        self.assertIn(
            "Tipo do produto (sólido ou líquido) não informado; "
            "confirme o tipo antes da análise.",
            result["warnings"],
        )

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_liquid_type_high_sugar_is_evitar(
        self,
        _query,
        _model,
        _get_limits,
        _get_taco,
    ):
        result = nutritional_agent_node({
            "extracted_ocr_data": {
                "tipo_alimento": "liquido",
                "acucares_adicionados_g": 10,
            },
            "llm_calls": 0,
        })

        self.assertEqual(result["classification_tone"], "EVITAR")

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model")
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_inconclusive_tone_wins_over_gemini(
        self,
        _query,
        get_model,
        _get_limits,
        _get_taco,
    ):
        get_model.return_value = SimpleNamespace(
            models=SimpleNamespace(
                generate_content=lambda **kwargs: SimpleNamespace(
                    text=(
                        '{"draft_response":"Sugestao",'
                        '"classification_tone":"EVITAR","warnings":[]}'
                    )
                )
            )
        )

        result = nutritional_agent_node({
            "extracted_ocr_data": {
                "tipo_alimento": "solido",
            },
            "llm_calls": 0,
        })

        self.assertEqual(result["classification_tone"], "INCONCLUSIVO")

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_missing_allergens_add_warning(
        self,
        _query,
        _model,
        _get_limits,
        _get_taco,
    ):
        result = nutritional_agent_node({
            "extracted_ocr_data": {
                "tipo_alimento": "solido",
                "acucares_adicionados_g": 5,
            },
            "llm_calls": 0,
        })

        self.assertIn(
            "Não foi possível ler a linha ALÉRGICOS; confira a embalagem.",
            result["warnings"],
        )

    @patch("nutritional_agent.database.get_taco_alimento", return_value=[])
    @patch("nutritional_agent.database.get_limites_rotulagem", return_value=[])
    @patch("nutritional_agent._get_gemini_model", return_value=None)
    @patch("nutritional_agent.query_knowledge_base", return_value=[
        {"text": "Fonte oficial.", "source": "in_75.pdf", "similarity": 0.9}
    ])
    def test_allergen_warning_is_for_user_and_no_internal_instruction(
        self,
        _query,
        _model,
        _get_limits,
        _get_taco,
    ):
        result = nutritional_agent_node({
            "extracted_ocr_data": {
                "tipo_alimento": "solido",
                "acucares_adicionados_g": 5,
                "alergicos_contem": "leite",
                "alergicos_pode_conter": "soja",
            },
            "llm_calls": 0,
        })

        self.assertTrue(any(
            "Pode conter: soja. Confira sempre a embalagem." == warning
            for warning in result["warnings"]
        ))
        self.assertFalse(any(
            "Não afirmar" in warning
            for warning in result["warnings"]
        ))


if __name__ == "__main__":
    unittest.main()
