import json
import tempfile
import unittest
from pathlib import Path

from benchmark import recall, testset


def q(qid, text="pergunta?"):
    return testset.Question(qid, "cat", text, "", "", "", "", False)


def res(doc, text, page=1):
    return {"source_title": doc, "text": text, "page": page, "similarity": 0.7}


GAB = {
    "A06": [{"documentos": ["Guia"], "trechos": ["frequentemente cinco ou mais"], "pagina_referencia": "", "observacao": ""}],
    "F03": [
        {"documentos": ["IN 75/2020"], "trechos": ["15 g de açúcares"], "pagina_referencia": "", "observacao": ""},
        {"documentos": ["SBD"], "trechos": ["com nutricionista"], "pagina_referencia": "", "observacao": ""},
    ],
}


class TestRecall(unittest.TestCase):
    def test_hit_requires_document_and_literal_text(self):
        alt = GAB["A06"][0]
        self.assertTrue(recall.matches(res("Guia", "Um número elevado (Frequentemente  CINCO ou mais)"), alt))
        self.assertFalse(recall.matches(res("Outro doc", "frequentemente cinco ou mais"), alt))
        self.assertFalse(recall.matches(res("Guia", "ingredientes pouco familiares"), alt))

    def test_accents_and_curly_quotes_are_normalized(self):
        alt = {"documentos": ["Guia Alimentar"], "trechos": ['como biscoitos recheados, "salgadinhos']}
        self.assertTrue(recall.matches(res("guia alimentar", "como biscoitos recheados, “salgadinhos de pacote”"), alt))
        self.assertEqual(recall.norm("Açúcares  Ádicionados"), "acucares adicionados")

    def test_evaluate_rank_alternatives_and_skips_questions_without_gabarito(self):
        def search(text, k):
            return {
                "A06?": [res("Guia", "nada"), res("Guia", "nada"), res("Guia", "frequentemente cinco ou mais")],
                "F03?": [res("SBD", "procure acompanhamento com nutricionista")],
            }[text]

        rep = recall.evaluate([q("A06", "A06?"), q("F03", "F03?"), q("G01", "G01?")], GAB, search, k=3)
        self.assertEqual(rep["n_perguntas"], 2)
        self.assertEqual(rep["recall_pct"], 100.0)
        self.assertEqual({r["id"]: r["posicao"] for r in rep["perguntas"]}, {"A06": 3, "F03": 1})

    def test_hit_outside_top_k_is_a_miss(self):
        search = lambda t, k: [res("Guia", "x"), res("Guia", "frequentemente cinco ou mais")]
        rep = recall.evaluate([q("A06")], GAB, search, k=1)
        self.assertEqual(rep["recall_pct"], 0.0)
        self.assertFalse(rep["atinge_meta"])
        self.assertEqual(rep["perdidas"], ["A06"])

    def test_connection_error_is_not_reported_as_a_miss(self):
        def search(t, k):
            raise ConnectionError("chromadb fora do ar")
        with self.assertRaises(RuntimeError):
            recall.evaluate([q("A06")], GAB, search)

    def test_validate_against_sources(self):
        d = Path(tempfile.mkdtemp())
        (d / "guia.json").write_text(json.dumps({"documento": "Guia", "paginas": [{"pagina": 1, "texto": "frequentemente cinco ou mais"}]}), encoding="utf-8")
        avisos = recall.validate_gabarito(GAB, d)
        self.assertFalse(any(a.startswith("A06") for a in avisos))
        self.assertIn("F03: NÃO PODE SER RECUPERADA com a base atual", avisos)

    def test_real_gabarito_file_loads_and_ids_exist_in_testset(self):
        gab = recall.load_gabarito()
        ids = {x.id for x in testset.load(Path(recall.GABARITO).with_name("conjunto_de_teste.csv"))}
        self.assertTrue(set(gab) <= ids)
        self.assertEqual(len(gab["F03"]), 2)


if __name__ == "__main__":
    unittest.main()
