import unittest

from benchmark import extraction as ex


def gold(photo, cond="boa", visible="sim", contem="Leite", pode="Soja", **values):
    row = {c: "" for c in ex.GOLD_COLUMNS}
    row.update(foto_id=photo, tipo="solido", condicao=cond, alergicos_visivel=visible,
               alergicos_contem=contem, alergicos_pode_conter=pode)
    row.update({k: str(v) for k, v in values.items()})
    return row


def read(engine, photo, tempo=1000, contem="Leite", pode="Soja", **values):
    row = {c: "" for c in ex.READ_COLUMNS}
    row.update(motor=engine, foto_id=photo, tempo_ms=str(tempo),
               alergicos_contem=contem, alergicos_pode_conter=pode)
    row.update({k: str(v) for k, v in values.items()})
    return row


class TestExtraction(unittest.TestCase):
    def test_field_accuracy_and_decimal_comma(self):
        g = [gold("F01", carboidratos_g="60,5", sodio_mg="250")]
        r = [read("tesseract", "F01", carboidratos_g="60.5", sodio_mg="25")]
        m = ex.compare(g, r)["motores"]["tesseract"]
        self.assertEqual(m["acerto_campos_pct"], 50.0)
        self.assertFalse(m["atinge_meta"])
        self.assertEqual(m["acerto_por_campo_pct"]["sodio_mg"], 0.0)
        self.assertEqual(m["erros"][0]["campo"], "sodio_mg")

    def test_blank_in_both_is_skipped_but_invented_value_is_error(self):
        g = [gold("F01", carboidratos_g="10")]
        r = [read("x", "F01", carboidratos_g="10", gorduras_trans_g="0,5")]
        m = ex.compare(g, r)["motores"]["x"]
        self.assertEqual(m["acerto_campos_pct"], 50.0)

    def test_missing_photo_counts_all_fields_as_wrong(self):
        g = [gold("F01", carboidratos_g="10"), gold("F02", carboidratos_g="20")]
        r = [read("x", "F01", carboidratos_g="10")]
        m = ex.compare(g, r)["motores"]["x"]
        self.assertEqual(m["n_fotos_lidas"], 1)
        self.assertEqual(m["acerto_campos_pct"], 50.0)

    def test_allergen_false_negative_ignores_accents_and_case(self):
        g = [gold("F01", contem="Leite; Trigo", pode="Soja")]
        r = [read("x", "F01", contem="LEITE", pode="soja")]
        m = ex.compare(g, r)["motores"]["x"]
        self.assertAlmostEqual(m["alergicos_recall_pct"], 66.67)
        self.assertEqual(m["fotos_com_falso_negativo_alergico"][0]["faltou"], ["alergicos_contem:trigo"])
        self.assertEqual(ex.allergen_set("Glúten; Amêndoa"), {"gluten", "amendoa"})

    def test_allergens_skipped_when_line_not_visible(self):
        g = [gold("F01", visible="não", contem="", pode="")]
        m = ex.compare(g, [read("x", "F01", contem="", pode="")])["motores"]["x"]
        self.assertIsNone(m["alergicos_recall_pct"])

    def test_engines_reported_separately_with_median_time(self):
        g = [gold("F01", sodio_mg="100"), gold("F02", sodio_mg="200", cond="reflexo")]
        r = [read("a", "F01", 500, sodio_mg="100"), read("a", "F02", 1500, sodio_mg="200"),
             read("b", "F01", sodio_mg="100"), read("b", "F02", sodio_mg="0")]
        m = ex.compare(g, r)["motores"]
        self.assertEqual(m["a"]["acerto_campos_pct"], 100.0)
        self.assertEqual(m["a"]["tempo_mediano_ms"], 1000)
        self.assertEqual(m["b"]["acerto_por_condicao_pct"], {"boa": 100.0, "reflexo": 0.0})

    def test_validate_gold(self):
        rows = [gold("F01", acucares_totais_g="15", carboidratos_g="10"), gold("F01")]
        rows[1]["tipo"] = "pó"
        errors = ex.validate_gold(rows)
        self.assertTrue(any("açúcares totais > carboidratos" in e for e in errors))
        self.assertTrue(any("duplicado" in e for e in errors))
        self.assertTrue(any("tipo" in e for e in errors))


class TestGabaritoPorPessoa(unittest.TestCase):
    def _pasta(self, arquivos):
        import tempfile, csv
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        for nome, linhas in arquivos.items():
            with open(d / nome, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=ex.GOLD_COLUMNS)
                w.writeheader()
                w.writerows(linhas)
        return d

    def test_le_todos_os_arquivos_da_pasta(self):
        d = self._pasta({"P01-P03.csv": [gold("P01_boa", sodio_mg="100")],
                         "P04-P06.csv": [gold("P04_boa", sodio_mg="200"), gold("P05_reflexo")]})
        rows = ex.load_gold(d)
        self.assertEqual([r["foto_id"] for r in rows], ["P01_boa", "P04_boa", "P05_reflexo"])
        self.assertEqual(ex.validate_gold(rows), [])

    def test_foto_fora_da_faixa_do_arquivo(self):
        d = self._pasta({"P04-P06.csv": [gold("P07_boa")]})
        erros = ex.validate_gold(ex.load_gold(d))
        self.assertTrue(any("fora da faixa" in e and "P04 a P06" in e for e in erros))

    def test_foto_duplicada_entre_arquivos(self):
        d = self._pasta({"P01-P03.csv": [gold("P02_boa")], "P01-P06.csv": [gold("P02_boa")]})
        erros = ex.validate_gold(ex.load_gold(d))
        self.assertTrue(any("duplicado" in e and "P01-P03.csv" in e for e in erros))

    def test_arquivo_sem_coluna_e_apontado(self):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp())
        (d / "P01-P03.csv").write_text("foto_id,tipo\nP01_boa,solido\n", encoding="utf-8")
        erros = ex.validate_gold(ex.load_gold(d))
        self.assertTrue(erros[0].startswith("P01-P03.csv: colunas ausentes"))

    def test_modo_validar(self):
        d = self._pasta({"P01-P03.csv": [gold("P01_boa")]})
        self.assertEqual(ex.main(["x", "--validar", str(d)]), 0)
        d2 = self._pasta({"P01-P03.csv": [gold("P09_boa")]})
        self.assertEqual(ex.main(["x", "--validar", str(d2)]), 1)


if __name__ == "__main__":
    unittest.main()
