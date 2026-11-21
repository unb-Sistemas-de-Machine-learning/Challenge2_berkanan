"""Testes do cálculo do ALTO EM com os casos do conjunto de teste (categorias C e D).

Gabarito conferido na IN 75/2020, Anexo XV (mlops/experiments/testset/conferencia_gabarito.md).
"""
import unittest

from rotulagem import (LIMITES_RESERVA, carregar_limites, checar_consistencia, classificar_alto_em,
                       normalizar_por_100)

L = LIMITES_RESERVA  # testes não dependem do PostgreSQL


def alto(valores, tipo="solido"):
    return set(classificar_alto_em(valores, tipo, L)["alto_em"])


class TestGabaritoCategoriaC(unittest.TestCase):
    def test_c01_biscoito_alto_em_acucar(self):
        self.assertEqual(alto({"acucares_adicionados": 22, "gorduras_saturadas": 3, "sodio": 250}), {"acucares_adicionados"})

    def test_c02_batata_chips_alto_em_sodio(self):
        self.assertEqual(alto({"acucares_adicionados": 0, "gorduras_saturadas": 4, "sodio": 650}), {"sodio"})

    def test_c03_refrigerante_liquido_alto_em_acucar(self):
        self.assertEqual(alto({"acucares_adicionados": 10}, "liquido"), {"acucares_adicionados"})

    def test_c04_bebida_lactea_abaixo_dos_limites_de_liquido(self):
        self.assertEqual(alto({"acucares_adicionados": 6, "gorduras_saturadas": 1.5, "sodio": 80}, "liquido"), set())

    @unittest.skip("Exceção do Anexo XVI (queijos) depende da decisão da issue #21")
    def test_c05_queijo_sem_lupa_pelo_anexo_xvi(self):
        self.assertEqual(alto({"acucares_adicionados": 0, "gorduras_saturadas": 14, "sodio": 700}), set())

    def test_c05_valores_passam_dos_limites_antes_da_excecao(self):
        # Sem a exceção do Anexo XVI, os valores do queijo passam dos dois limites.
        self.assertEqual(alto({"acucares_adicionados": 0, "gorduras_saturadas": 14, "sodio": 700}),
                         {"gorduras_saturadas", "sodio"})

    def test_c06_pao_de_forma_abaixo_dos_limites(self):
        self.assertEqual(alto({"acucares_adicionados": 5, "gorduras_saturadas": 1, "sodio": 450}), set())

    def test_c07_normaliza_porcao_de_30g(self):
        por_100 = normalizar_por_100(6, 30)
        self.assertAlmostEqual(por_100, 20)
        self.assertEqual(alto({"acucares_adicionados": por_100}), {"acucares_adicionados"})

    def test_c08_leitura_inconsistente_pede_confirmacao(self):
        r = classificar_alto_em({"carboidratos": 10, "acucares_totais": 15, "acucares_adicionados": 15}, "solido", L)
        self.assertEqual(r["status"], "confirmar_valores")
        self.assertEqual(r["alto_em"], [])
        self.assertIn("Confira os valores", r["inconsistencias"][0])


class TestGabaritoCategoriaD(unittest.TestCase):
    def test_d01_cereais(self):
        self.assertEqual(alto({"acucares_adicionados": 25}), {"acucares_adicionados"})
        self.assertEqual(alto({"acucares_adicionados": 8}), set())

    def test_d02_nectar_liquido_alto_em_acucar(self):
        self.assertEqual(alto({"acucares_adicionados": 9}, "liquido"), {"acucares_adicionados"})
        self.assertEqual(alto({"acucares_adicionados": 0}, "liquido"), set())

    def test_d03_salgadinhos(self):
        self.assertEqual(alto({"sodio": 800}), {"sodio"})
        self.assertEqual(alto({"sodio": 400}), set())

    def test_d05_e_d06_ambos_alto_em_sodio(self):
        for sodio in (900, 700, 1000, 650):
            self.assertEqual(alto({"sodio": sodio}), {"sodio"}, sodio)


class TestRegras(unittest.TestCase):
    def test_limite_e_maior_ou_igual(self):
        self.assertEqual(alto({"acucares_adicionados": 15, "gorduras_saturadas": 6, "sodio": 600}),
                         {"acucares_adicionados", "gorduras_saturadas", "sodio"})
        self.assertEqual(alto({"acucares_adicionados": 14.99, "gorduras_saturadas": 5.99, "sodio": 599.9}), set())
        self.assertEqual(alto({"acucares_adicionados": 7.5, "gorduras_saturadas": 3, "sodio": 300}, "liquido"),
                         {"acucares_adicionados", "gorduras_saturadas", "sodio"})

    def test_valor_ausente_nao_e_zero(self):
        r = classificar_alto_em({"sodio": 700}, "solido", L)
        self.assertEqual(r["alto_em"], ["sodio"])
        self.assertEqual(r["nao_avaliados"], ["acucares_adicionados", "gorduras_saturadas"])
        self.assertIsNone(r["avaliacao"]["acucares_adicionados"]["alto"])

    def test_resultado_traz_trecho_literal_para_citar(self):
        r = classificar_alto_em({"gorduras_saturadas": 3}, "liquido", L)
        a = r["avaliacao"]["gorduras_saturadas"]
        self.assertTrue(a["alto"])
        self.assertIn("3 g de gorduras saturadas por 100 ml", a["trecho_norma"])
        self.assertEqual(r["fonte"], "IN 75/2020, Anexo XV")

    def test_entradas_invalidas(self):
        with self.assertRaises(ValueError):
            classificar_alto_em({"sodio": 100}, "po", L)
        with self.assertRaises(ValueError):
            classificar_alto_em({"sodio": -1}, "solido", L)
        with self.assertRaises(ValueError):
            normalizar_por_100(5, 0)

    def test_consistencia_aceita_igualdade_e_valores_ausentes(self):
        self.assertEqual(checar_consistencia({"carboidratos": 10, "acucares_totais": 10}), [])
        self.assertEqual(checar_consistencia({"acucares_totais": 15}), [])


class TestCarregarLimites(unittest.TestCase):
    def test_le_do_banco_no_formato_da_migracao_008(self):
        linhas = [{"categoria": "sólido", "nutriente": "sódio", "limite_100g": 600.00, "unidade": "mg",
                   "trecho_norma": "IN 75/2020, Anexo XV (Alimentos sólidos ou semissólidos): \"...600 mg...\""}]
        limites = carregar_limites(lambda: linhas)
        self.assertEqual(limites[("solido", "sodio")].origem, "postgresql")
        self.assertEqual(limites[("solido", "sodio")].valor, 600)
        self.assertEqual(limites[("liquido", "sodio")].origem, "reserva")  # faltou no banco
        self.assertEqual(len(limites), 6)

    def test_banco_vazio_usa_reserva(self):
        limites = carregar_limites(lambda: [])
        self.assertTrue(all(l.origem == "reserva" for l in limites.values()))

    def test_reserva_igual_ao_anexo_xv(self):
        valores = {k: (l.valor, l.unidade) for k, l in LIMITES_RESERVA.items()}
        self.assertEqual(valores, {
            ("solido", "acucares_adicionados"): (15, "g"), ("liquido", "acucares_adicionados"): (7.5, "g"),
            ("solido", "gorduras_saturadas"): (6, "g"), ("liquido", "gorduras_saturadas"): (3, "g"),
            ("solido", "sodio"): (600, "mg"), ("liquido", "sodio"): (300, "mg"),
        })


if __name__ == "__main__":
    unittest.main()
