import tempfile
import unittest
from pathlib import Path

from benchmark import testset

HEADER = ",".join(f'"{c}"' for c in testset.COLUMNS)


def write_csv(rows: list[str]) -> Path:
    tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    tmp.write("\n".join([HEADER, *rows]) + "\n")
    tmp.close()
    return Path(tmp.name)


def full_set() -> list[str]:
    rows = []
    for prefix, (name, n) in testset.CATEGORIES.items():
        for i in range(1, n + 1):
            fonte = "" if prefix == "G" else "Guia Alimentar"
            rows.append(f"{prefix}{i},{name},Pergunta {i}?,Resposta,{fonte},Responder,Acerto,Não")
    return rows


class TestTestset(unittest.TestCase):
    def test_full_set_is_valid_in_strict_mode(self):
        errors, warnings = testset.validate(write_csv(full_set()), strict_counts=True)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_column_is_error(self):
        path = write_csv([])
        path.write_text("ID,Pergunta\nA1,x\n", encoding="utf-8")
        errors, _ = testset.validate(path)
        self.assertTrue(any("Colunas ausentes" in e for e in errors))

    def test_duplicate_and_unknown_prefix(self):
        rows = full_set() + ["A1,Guia,Outra?,R,Guia,,Acerto,Não", "Z1,X,Q?,R,F,,Acerto,Não"]
        errors, _ = testset.validate(write_csv(rows))
        self.assertTrue(any("duplicado A1" in e for e in errors))
        self.assertTrue(any("Z1" in e for e in errors))

    def test_count_mismatch_is_warning_unless_strict(self):
        rows = full_set()[1:]
        errors, warnings = testset.validate(write_csv(rows))
        self.assertEqual(errors, [])
        self.assertTrue(any("Categoria A" in w for w in warnings))
        errors, _ = testset.validate(write_csv(rows), strict_counts=True)
        self.assertTrue(any("Categoria A" in e for e in errors))

    def test_pending_source_check_is_reported(self):
        rows = full_set()
        rows[0] = rows[0].replace(",Não", ",Sim")
        _, warnings = testset.validate(write_csv(rows))
        self.assertTrue(any("Conferir na fonte" in w for w in warnings))
        self.assertTrue(testset.load(write_csv(rows))[0].needs_source_check)

    def test_semicolon_separator(self):
        rows = [r.replace(",", ";") for r in full_set()]
        tmp = write_csv([])
        tmp.write_text("\n".join([HEADER.replace(",", ";"), *rows]) + "\n", encoding="utf-8-sig")
        errors, _ = testset.validate(tmp, strict_counts=True)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
