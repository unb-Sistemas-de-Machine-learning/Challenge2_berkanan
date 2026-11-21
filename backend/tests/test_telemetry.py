import unittest
from unittest.mock import patch

from main import _build_telemetry_payload
from schemas import AnalysisRequest


class TestTelemetryPayload(unittest.TestCase):
    """Valida alinhamento das colunas gravadas em metricas_requisicao (ADR-008 / 004_metricas.sql)."""

    def test_config_a_ocr_defaults(self):
        with patch.dict("os.environ", {"OCR_ENGINE": "nao_configurado"}):
            req = AnalysisRequest(request_type="ocr_analysis", enable_verifier=False)
            state = {"classification_tone": "SAUDAVEL", "verification_passed": True, "verification_errors": []}
            payload = _build_telemetry_payload(req, state, 145)

        self.assertEqual(payload["tipo_operacao"], "extracao_ocr")
        self.assertEqual(payload["latencia_ms"], 145)
        self.assertEqual(payload["configuracao_verificador"], "A")
        self.assertEqual(payload["versao_ocr"], "nao_configurado")
        self.assertEqual(payload["chamadas_llm"], 1)
        self.assertFalse(payload["falha_leitura"])
        self.assertIsNone(payload["tipo_falha"])

    def test_config_b_rules_comparison_zero_llm_calls(self):
        req = AnalysisRequest(
            request_type="comparison",
            enable_verifier=True,
            verifier_mode="rules",
            id_questao_teste="D02",
        )
        state = {"classification_tone": "ATENCAO", "verification_passed": True, "verification_errors": []}
        payload = _build_telemetry_payload(req, state, 82)

        self.assertEqual(payload["tipo_operacao"], "comparacao_produtos")
        self.assertEqual(payload["configuracao_verificador"], "B")
        self.assertEqual(payload["chamadas_llm"], 0)
        self.assertEqual(payload["modelo_usado"], "regras")
        self.assertEqual(payload["versao_ocr"], "nenhum")
        self.assertEqual(payload["categoria_teste"], "D_comparacao_produtos")
        self.assertEqual(payload["id_questao_teste"], "D02")

    def test_config_c_llm_verifier_and_failure_tracking(self):
        req = AnalysisRequest(
            request_type="qa",
            enable_verifier=True,
            verifier_mode="llm",
            modo_execucao="llm_puro",
            id_questao_teste="F01",
            versao_ocr="tesseract",
        )
        state = {
            "classification_tone": "ERRO",
            "verification_passed": False,
            "verification_errors": ["V02: Resposta sem fontes documentais."],
        }
        payload = _build_telemetry_payload(req, state, 1230)

        self.assertEqual(payload["tipo_operacao"], "chat_nutricional")
        self.assertEqual(payload["configuracao_verificador"], "C")
        self.assertEqual(payload["chamadas_llm"], 2)
        self.assertEqual(payload["modo_execucao"], "llm_puro")
        self.assertEqual(payload["versao_ocr"], "tesseract")
        self.assertEqual(payload["categoria_teste"], "F_saude_oms")
        self.assertTrue(payload["falha_leitura"])
        self.assertEqual(payload["tipo_falha"], "V02: Resposta sem fontes documentais.")


if __name__ == "__main__":
    unittest.main()
