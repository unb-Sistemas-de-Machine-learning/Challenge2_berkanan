import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SAFETY_PATH = REPO_ROOT / "scripts" / "validate_repository_safety.py"


def _load_safety_module():
    spec = importlib.util.spec_from_file_location("validate_repository_safety", SAFETY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível carregar {SAFETY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


safety = _load_safety_module()


def _cleanup_dir(path: Path) -> None:
    shutil.rmtree(path, ignore_errors=True)


class TestMigrationSafety(unittest.TestCase):
    def test_real_repository_migrations_pass_prefix_uniqueness(self):
        self.assertEqual(safety.validate_migration_prefixes(REPO_ROOT), [])

    def test_duplicate_numeric_prefix_fails(self):
        tmp_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: _cleanup_dir(tmp_root))
        mig_dir = tmp_root / "migrations"
        mig_dir.mkdir()
        (mig_dir / "011_fontes_alergenicos.sql").write_text("SELECT 1;\n", encoding="utf-8")
        (mig_dir / "011_duplicada.sql").write_text("SELECT 1;\n", encoding="utf-8")

        errors = safety.validate_migration_prefixes(tmp_root)
        self.assertEqual(len(errors), 1)
        self.assertIn("Prefixo numérico duplicado '011'", errors[0])

    def test_rejects_modifying_deleting_or_renaming_existing_sql_migration(self):
        for diff_line in (
            "M\tmigrations/004_metricas.sql\n",
            "D\tmigrations/004_metricas.sql\n",
            "R100\tmigrations/004_metricas.sql\tmigrations/004_renomeada.sql\n",
        ):
            errors = safety.check_sql_migrations_immutability_from_diff(diff_line)
            self.assertEqual(len(errors), 1)
            self.assertIn("004_metricas.sql", errors[0])

    def test_accepts_adding_new_sequential_sql_migration(self):
        diff = "A\tmigrations/012_nova_metrica.sql\n"
        self.assertEqual(safety.check_sql_migrations_immutability_from_diff(diff), [])


class TestSecretAndFileSafety(unittest.TestCase):
    def test_detects_real_looking_secrets_constructed_dynamically(self):
        fake_google_key = "AIza" + "A" * 35
        fake_gh_token = "ghp_" + "a" * 36
        fake_sk_key = "sk-" + "b" * 24
        fake_pem = "-----" + "BEGIN OPENSSH PRIVATE KEY" + "-----"

        for sample in (
            f"GEMINI_API_KEY={fake_google_key}",
            f"TOKEN={fake_gh_token}",
            f"API_KEY={fake_sk_key}",
            fake_pem,
        ):
            findings = safety.scan_text_for_secrets(sample, "backend/config.py")
            self.assertEqual(len(findings), 1, msg=f"Esperava detecção para: {sample}")

    def test_ignores_example_placeholders(self):
        sample = "GEMINI_API_KEY=" + "CHANGE_ME_" + "AIza" + "A" * 35
        self.assertEqual(safety.scan_text_for_secrets(sample, "infra/azure/.env.prod.example"), [])

    def test_forbidden_sensitive_paths_vs_allowed_examples(self):
        for forbidden in (".env", ".env.local", "infra/azure/.env.prod", "keys/cert.pem", "ssh/id_ed25519"):
            self.assertTrue(safety.is_forbidden_sensitive_path(forbidden), msg=forbidden)

        for allowed in (".env.example", "infra/azure/.env.prod.example", "backend/main.py"):
            self.assertFalse(safety.is_forbidden_sensitive_path(allowed), msg=allowed)

    def test_cli_passes_on_real_repository(self):
        self.assertEqual(safety.main(["--repo-root", str(REPO_ROOT)]), 0)


if __name__ == "__main__":
    unittest.main()
