
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
            "valores_nutricionais_100": None,
            "tipo_alimento": None,
            "categoria_produto": "outro",
            "rotulagem_resultado": None,
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

def test_ocr_analysis_classifies_nutritional_values(self):
        state = self.initial_state.copy()

        state.update({
            "request_type": "ocr_analysis",
            "valores_nutricionais_100": {
                "acucares_adicionados": 16,
                "gorduras_saturadas": 2,
                "sodio": 500,
                "acucares_totais": 18,
                "carboidratos": 25,
            },
            "tipo_alimento": "solido",
            "categoria_produto": "outro",
        })

        result = app.invoke(state)

        self.assertEqual(
            result["rotulagem_resultado"]["status"],
            "ok"
        )

        self.assertIn(
            "acucares_adicionados",
            result["rotulagem_resultado"]["alto_em"]
        )

        self.assertEqual(
            result["classification_tone"],
            "INCONCLUSIVO"
        )

        self.assertTrue(result["verification_passed"])

def test_ocr_analysis_respects_anexo_xvi_conditional_category(self):
        state = self.initial_state.copy()

        state.update({
            "request_type": "ocr_analysis",
            "valores_nutricionais_100": {
                "acucares_adicionados": 20,
                "gorduras_saturadas": 8,
                "sodio": 800,
                "acucares_totais": 22,
                "carboidratos": 30,
            },
            "tipo_alimento": "solido",
            "categoria_produto": "queijo",
        })

        result = app.invoke(state)

        self.assertEqual(
            result["rotulagem_resultado"]["regra_anexo_xvi"],
            "condicional"
        )

        self.assertEqual(
            result["rotulagem_resultado"]["alto_em"],
            []
        )

        self.assertTrue(
            any("Anexo XVI" in aviso for aviso in result["warnings"])
        )

        self.assertTrue(result["verification_passed"])

def test_ocr_analysis_respects_anexo_xvi_prohibition(self):
        state = self.initial_state.copy()

        state.update({
            "request_type": "ocr_analysis",
            "valores_nutricionais_100": {
                "acucares_adicionados": 20,
                "gorduras_saturadas": 8,
                "sodio": 800,
                "acucares_totais": 22,
                "carboidratos": 30,
            },
            "tipo_alimento": "solido",
            "categoria_produto": "leite",
        })

        result = app.invoke(state)

        self.assertEqual(
            result["rotulagem_resultado"]["regra_anexo_xvi"],
            "vedacao"
        )

        self.assertEqual(
            result["rotulagem_resultado"]["alto_em"],
            []
        )

        self.assertTrue(result["verification_passed"])

def test_ocr_analysis_rejects_inconsistent_values(self):
        state = self.initial_state.copy()

        state.update({
            "request_type": "ocr_analysis",
            "valores_nutricionais_100": {
                "acucares_adicionados": 10,
                "gorduras_saturadas": 2,
                "sodio": 200,
                "acucares_totais": 30,
                "carboidratos": 20,
            },
            "tipo_alimento": "solido",
            "categoria_produto": "outro",
        })

        result = app.invoke(state)

        self.assertEqual(
            result["rotulagem_resultado"]["status"],
            "confirmar_valores"
        )

        self.assertEqual(
            result["rotulagem_resultado"]["alto_em"],
            []
        )

        self.assertTrue(
            result["rotulagem_resultado"]["inconsistencias"]
        )

        self.assertTrue(result["verification_passed"])

if __name__ == "__main__":
    unittest.main()
