import unittest

from benchmark import metrics


def row(config, qid, latency_ms, correct="1", total="4", supported="4", refused="", calls="1", rep="1"):
    return {
        "config": config, "rep": rep, "question_id": qid, "category": qid[0],
        "latency_ms": str(latency_ms), "llm_calls": calls, "correct": correct,
        "claims_total": total, "claims_supported": supported, "refused": refused,
    }


class TestCompute(unittest.TestCase):
    def test_basic_aggregation(self):
        rows = [
            row("A", "A1", 1000, correct="1", total="4", supported="3"),
            row("A", "A2", 3000, correct="0", total="6", supported="6"),
            row("A", "G1", 2000, correct="1", total="", supported="", refused="1"),
            row("A", "G2", 2000, correct="0", total="", supported="", refused="0"),
        ]
        m = metrics.compute(rows)["A"]
        self.assertEqual(m.n_responses, 4)
        self.assertEqual(m.accuracy_pct, 50.0)
        self.assertEqual(m.fidelity_pct, 90.0)  # 9 de 10 afirmações (micro-média)
        self.assertEqual(m.refusal_pct, 50.0)
        self.assertEqual(m.median_latency_s, 2.0)
        self.assertEqual(m.avg_llm_calls, 1.0)

    def test_blank_cells_are_not_zero(self):
        m = metrics.compute([row("B", "A1", 1000, correct=""), row("B", "A2", 1000, correct="1")])["B"]
        self.assertEqual(m.accuracy_pct, 100.0)
        self.assertEqual(m.n_graded_accuracy, 1)

    def test_supported_greater_than_total_is_error(self):
        with self.assertRaises(ValueError):
            metrics.compute([row("B", "A1", 1000, total="2", supported="3")])

    def test_decimal_comma(self):
        m = metrics.compute([row("C", "A1", "1500,5")])["C"]
        self.assertEqual(m.median_latency_s, 1.5)


class TestDecision(unittest.TestCase):
    def _m(self, config, fid, lat):
        return metrics.ConfigMetrics(config, 1, None, fid, None, lat, None, 0, 1, 0)

    def test_adopt_c_on_exact_thresholds(self):
        d = metrics.decide_verifier(self._m("B", 85.0, 4.0), self._m("C", 90.0, 7.0))
        self.assertEqual(d["decision"], "ADOTAR_C")

    def test_keep_b_when_gain_too_small(self):
        d = metrics.decide_verifier(self._m("B", 85.0, 4.0), self._m("C", 89.99, 4.0))
        self.assertEqual(d["decision"], "MANTER_B")

    def test_keep_b_when_too_slow(self):
        d = metrics.decide_verifier(self._m("B", 80.0, 4.0), self._m("C", 95.0, 7.01))
        self.assertEqual(d["decision"], "MANTER_B")

    def test_no_data(self):
        self.assertEqual(metrics.decide_verifier(None, self._m("C", 90.0, 1.0))["decision"], "SEM_DADOS")
        self.assertEqual(metrics.decide_verifier(self._m("B", None, 1.0), self._m("C", 90.0, 1.0))["decision"], "SEM_DADOS")


if __name__ == "__main__":
    unittest.main()
