import unittest
import urllib.error

from benchmark import comparar_llm as cl
from benchmark import metrics, testset


def q(qid, texto="Pergunta?"):
    return testset.Question(qid, "cat", texto, "Gabarito.", "Fonte", "Responder com citação", "Recall", False)


TRECHOS = [{"source_title": "Guia Alimentar", "page": 41, "text": "frequentemente cinco ou mais"},
           {"source_title": "IN 75/2020", "page": 19, "text": "maior ou igual a 15 g"}]


class TestCompararLLM(unittest.TestCase):
    def test_prompt_traz_trechos_fontes_e_regra_de_sem_evidencia(self):
        p = cl.montar_prompt("Como reconheço um ultraprocessado?", TRECHOS)
        self.assertIn("[1] (Guia Alimentar, página 41) frequentemente cinco ou mais", p)
        self.assertIn("[2] (IN 75/2020, página 19)", p)
        self.assertIn(cl.SEM_EVIDENCIA, p)
        self.assertIn("Pergunta: Como reconheço um ultraprocessado?", p)

    def test_os_dois_modelos_recebem_o_mesmo_prompt(self):
        recebidos = {}

        def modelo(nome):
            def chamar(prompt):
                recebidos.setdefault(nome, []).append(prompt)
                return f"resposta de {nome} [Guia Alimentar, 41]"
            return chamar

        buscas = []
        brutas, linhas = cl.comparar([q("AV01"), q("BV01")],
                                     lambda texto, k: buscas.append(texto) or TRECHOS,
                                     {"gemini:x": modelo("a"), "reserva:y": modelo("b")})
        self.assertEqual(recebidos["a"], recebidos["b"])
        self.assertEqual(len(buscas), 2)  # uma busca por pergunta, compartilhada pelos modelos
        self.assertEqual({l["config"] for l in linhas}, {"gemini:x", "reserva:y"})
        self.assertEqual(len(linhas), 4)

    def test_erro_do_modelo_vira_observacao_e_acerto_zero(self):
        def falha(prompt):
            raise urllib.error.URLError("cota esgotada")
        _, linhas = cl.comparar([q("AV01")], lambda t, k: TRECHOS, {"reserva:y": falha})
        self.assertEqual(linhas[0]["correct"], "0")
        self.assertIn("ERRO: URLError", linhas[0]["observacao"])

    def test_resposta_sem_evidencia_e_pre_marcada_como_recusa(self):
        _, linhas = cl.comparar([q("GV01")], lambda t, k: [], {"m": lambda p: cl.SEM_EVIDENCIA})
        self.assertEqual(linhas[0]["refused"], "1")

    def test_planilha_funciona_com_benchmark_metrics(self):
        _, linhas = cl.comparar([q("AV01")], lambda t, k: TRECHOS, {"gemini:x": lambda p: "ok", "reserva:y": lambda p: "ok"})
        for l in linhas:
            l.update(correct="1", claims_total="2", claims_supported="2")
        rel = metrics.compute([{k: str(v) for k, v in l.items()} for l in linhas])
        self.assertEqual(set(rel), {"GEMINI:X", "RESERVA:Y"})
        self.assertEqual(rel["GEMINI:X"].accuracy_pct, 100.0)

    def test_sem_modelo_configurado_para_com_mensagem(self):
        import os
        antes = {v: os.environ.pop(v, None) for v in ("GEMINI_API_KEY", "LLM_MODEL", "FALLBACK_API_KEY",
                                                       "FALLBACK_BASE_URL", "LLM_FALLBACK_MODEL")}
        try:
            with self.assertRaises(SystemExit):
                cl._modelos_do_ambiente()
        finally:
            os.environ.update({k: v for k, v in antes.items() if v is not None})


class TestChamadasHTTP(unittest.TestCase):
    """Servidor falso local imitando o Gemini e uma API compatível com OpenAI."""

    def setUp(self):
        import json, threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        self.recebido = {}
        teste = self

        class Falso(BaseHTTPRequestHandler):
            def do_POST(self):
                corpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                teste.recebido = {"path": self.path, "corpo": corpo, "headers": dict(self.headers)}
                if "generateContent" in self.path:
                    r = {"candidates": [{"content": {"parts": [{"text": "resposta "}, {"text": "do gemini"}]}}]}
                else:
                    r = {"choices": [{"message": {"content": "resposta da reserva"}}]}
                dados = json.dumps(r).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(dados)

            def log_message(self, *a):
                pass

        self.srv = HTTPServer(("127.0.0.1", 0), Falso)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.srv.server_port}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_formato_compativel_openai(self):
        r = cl.modelo_compativel_openai(self.base + "/v1", "modelo-x", "chave-secreta")("oi")
        self.assertEqual(r, "resposta da reserva")
        self.assertEqual(self.recebido["path"], "/v1/chat/completions")
        self.assertEqual(self.recebido["corpo"]["temperature"], 0)
        self.assertEqual(self.recebido["headers"]["Authorization"], "Bearer chave-secreta")

    def test_formato_gemini(self):
        from unittest import mock
        real = cl._post_json
        with mock.patch.object(cl, "_post_json", lambda url, body, headers, timeout: real(
                url.replace("https://generativelanguage.googleapis.com", self.base), body, headers, timeout)):
            r = cl.modelo_gemini("gemini-teste", "chave-secreta")("oi")
        self.assertEqual(r, "resposta do gemini")
        self.assertEqual(self.recebido["path"], "/v1beta/models/gemini-teste:generateContent")
        self.assertEqual(self.recebido["corpo"]["generationConfig"]["temperature"], 0)
        self.assertEqual(self.recebido["headers"]["X-Goog-Api-Key"], "chave-secreta")


if __name__ == "__main__":
    unittest.main()
