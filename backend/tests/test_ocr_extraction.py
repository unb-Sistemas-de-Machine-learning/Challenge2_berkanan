"""Testes unitários para o pipeline de extração de OCR, alergênicos e leituras.csv (Issue #8 — R4)."""

from __future__ import annotations

import csv
import io
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
for p in (BACKEND_DIR, REPO_ROOT / "mlops" / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ocr_extraction import (  # noqa: E402
    LEITURAS_CSV_COLUMNS,
    build_leitura_csv_row,
    check_consistency,
    extract_allergens,
    extract_label_fields,
    normalizar_por_100g,
    write_leituras_csv,
)
from benchmark import extraction as bench_extraction  # noqa: E402


SAMPLE_LABEL_RDC429 = """
INFORMAÇÃO NUTRICIONAL
Porções por embalagem: 5
Porção: 30 g (3 biscoitos)
                          100 g     30 g     %VD*
Valor energético (kcal)   480       144      7%
Carboidratos (g)          65        19,5     7%
Açúcares totais (g)       32        9,6
Açúcares adicionados (g)  28        8,4      17%
Proteínas (g)             6,2       1,9      4%
Gorduras totais (g)       21        6,3      10%
Gorduras saturadas (g)    9,5       2,9      15%
Gorduras trans (g)        0         0
Fibras alimentares (g)    2,4       0,7      3%
Sódio (mg)                310       93       5%

ALÉRGICOS: CONTÉM DERIVADOS DE TRIGO, SOJA E LEITE. PODE CONTER AVEIA, CENTEIO, CEVADA E AMENDOIM.
CONTÉM LACTOSE. CONTÉM GLÚTEN.
"""


class TestOCRExtraction(unittest.TestCase):
    def test_extract_complete_rdc429_label(self) -> None:
        res = extract_label_fields(SAMPLE_LABEL_RDC429)

        self.assertEqual(res["porcao_g"], 30.0)
        self.assertEqual(res["valor_energetico_kcal"], 480.0)
        self.assertEqual(res["carboidratos_g"], 65.0)
        self.assertEqual(res["acucares_totais_g"], 32.0)
        self.assertEqual(res["acucares_adicionados_g"], 28.0)
        self.assertEqual(res["proteinas_g"], 6.2)
        self.assertEqual(res["gorduras_totais_g"], 21.0)
        self.assertEqual(res["gorduras_saturadas_g"], 9.5)
        self.assertEqual(res["gorduras_trans_g"], 0.0)
        self.assertEqual(res["fibra_alimentar_g"], 2.4)
        self.assertEqual(res["sodio_mg"], 310.0)
        self.assertEqual(res["alergicos_contem"], "trigo; soja; leite")
        self.assertEqual(res["alergicos_pode_conter"], "aveia; centeio; cevada; amendoim")
        self.assertTrue(res["consistency_passed"])
        self.assertTrue(res["requires_user_confirmation"])

    def test_missing_fields_stay_empty_never_zero(self) -> None:
        partial_text = """
        INFORMAÇÃO NUTRICIONAL
        Porção: 200 ml (1 copo)
        100 ml   200 ml   %VD
        Valor energético 42 kcal 84 kcal 4%
        Carboidratos 10,5 g 21 g 7%
        Açúcares totais 10,5 g 21 g
        Açúcares adicionados 10 g 20 g 40%
        Sódio 15 mg 30 mg 2%
        """
        res = extract_label_fields(partial_text)
        row = build_leitura_csv_row("tesseract", "P02_boa", 185, res)

        self.assertEqual(row["valor_energetico_kcal"], "42")
        self.assertEqual(row["carboidratos_g"], "10.5")
        self.assertEqual(row["acucares_adicionados_g"], "10")
        self.assertEqual(row["sodio_mg"], "15")
        self.assertEqual(row["porcao_g"], "200")
        # Campos ausentes na leitura ficam vazios (""), nunca "0"
        self.assertEqual(row["proteinas_g"], "")
        self.assertEqual(row["gorduras_totais_g"], "")
        self.assertEqual(row["gorduras_saturadas_g"], "")
        self.assertEqual(row["gorduras_trans_g"], "")
        self.assertEqual(row["fibra_alimentar_g"], "")
        self.assertEqual(row["alergicos_contem"], "")
        self.assertEqual(row["alergicos_pode_conter"], "")

    def test_zero_and_non_significant_phrases_become_zero(self) -> None:
        text = """
        INFORMAÇÃO NUTRICIONAL
        Porção: 50 g
        100 g  50 g
        Gorduras trans Não contém quantidade significativa
        Açúcares adicionados zero
        """
        res = extract_label_fields(text)
        self.assertEqual(res["gorduras_trans_g"], 0.0)
        self.assertEqual(res["acucares_adicionados_g"], 0.0)
        self.assertIsNone(res["sodio_mg"])

    def test_allergens_normalization(self) -> None:
        a = extract_allergens("ALÉRGICOS: CONTÉM LEITE E DERIVADOS. PODE CONTER SOJA.")
        self.assertEqual(a["alergicos_contem"], "leite")
        self.assertEqual(a["alergicos_pode_conter"], "soja")

    def test_consistency_check_flags_sugars_exceeding_carbs(self) -> None:
        bad = {
            "carboidratos_g": 12.0,
            "acucares_totais_g": 18.0,
            "acucares_adicionados_g": 15.0,
        }
        chk = check_consistency(bad)
        self.assertFalse(chk["consistency_passed"])
        self.assertTrue(any("açúcares totais" in e for e in chk["consistency_errors"]))

    def test_normalizar_por_100g(self) -> None:
        self.assertEqual(normalizar_por_100g(4.5, 30.0), 15.0)
        self.assertIsNone(normalizar_por_100g(None, 30.0))
        self.assertIsNone(normalizar_por_100g(4.5, 0.0))

    def test_leituras_csv_compatible_with_benchmark_extraction(self) -> None:
        res = extract_label_fields(SAMPLE_LABEL_RDC429)
        row_tess = build_leitura_csv_row("tesseract", "P01_boa", 210, res)
        row_padd = build_leitura_csv_row("paddleocr", "P01_boa", 340, res)

        csv_text = write_leituras_csv([row_tess, row_padd])
        parsed_reads = list(csv.DictReader(io.StringIO(csv_text)))
        self.assertEqual(list(parsed_reads[0].keys()), LEITURAS_CSV_COLUMNS)
        self.assertEqual(list(parsed_reads[0].keys()), bench_extraction.READ_COLUMNS)

        gold_rows = [
            {
                "foto_id": "P01_boa",
                "tipo": "solido",
                "condicao": "boa",
                "alergicos_visivel": "sim",
                **{k: row_tess[k] for k in bench_extraction.FIELDS},
                **{k: row_tess[k] for k in bench_extraction.ALLERGEN_FIELDS},
            }
        ]
        self.assertEqual(bench_extraction.validate_gold(gold_rows), [])
        report = bench_extraction.compare(gold_rows, parsed_reads)
        self.assertEqual(report["motores"]["tesseract"]["acerto_campos_pct"], 100.0)
        self.assertEqual(report["motores"]["tesseract"]["alergicos_recall_pct"], 100.0)
        self.assertEqual(report["motores"]["paddleocr"]["acerto_campos_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
