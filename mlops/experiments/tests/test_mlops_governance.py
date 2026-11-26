import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_mlops_governance.py"


def _load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_mlops_governance", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Não foi possível carregar o módulo em {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gov = _load_validator_module()


VALID_PROMPT_YAML = """\
prompt_id: "sample_agent"
version: "v1.0"
status: "PROPOSTO"
owner_role: "R5"
created_at: "2026-11-25"
compatible_models:
  - "gemini-*"
system_constraints_enforced:
  - "Nao inventar valores nutricionais"
template: |
  Responda com base apenas nas fontes oficiais.
"""


VALID_MANIFEST_YAML = """\
schema_version: "1.0"
manifest_type: "mlops_runtime_configuration"
project: "Challenge 2 Berkanan"
configuration:
  config_id: "cfg-test"
llm:
  primary_provider: "gemini"
prompts:
  registry_path: "mlops/prompts/"
knowledge_base_rag:
  vector_store: "chromadb"
structured_database:
  engine: "postgresql"
ocr_pipeline:
  mandatory_user_confirmation: true
verifier:
  default_enabled: true
monitoring:
  prometheus_enabled: false
deployment:
  cloud_provider: "azure"
"""


class TestRepositoryArtifacts(unittest.TestCase):
    def test_real_repository_prompts_pass(self):
        errors, prompt_files = gov.validate_prompts_directory(REPO_ROOT)
        self.assertEqual(errors, [])
        self.assertGreaterEqual(len(prompt_files), 2)

    def test_real_repository_runtime_manifest_passes(self):
        manifest_path = REPO_ROOT / "mlops" / "manifests" / "runtime-manifest.yaml"
        errors = gov.validate_runtime_manifest(manifest_path)
        self.assertEqual(errors, [])

    def test_cli_passes_on_real_repository(self):
        exit_code = gov.main(["--repo-root", str(REPO_ROOT)])
        self.assertEqual(exit_code, 0)


class TestPromptSchemaValidation(unittest.TestCase):
    def _write_prompt(self, filename: str, content: str) -> Path:
        tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: _cleanup_dir(tmp_dir))
        prompt_file = tmp_dir / filename
        prompt_file.write_text(content, encoding="utf-8")
        return prompt_file

    def test_valid_prompt_passes(self):
        path = self._write_prompt("sample_agent_v1.0.yaml", VALID_PROMPT_YAML)
        self.assertEqual(gov.validate_prompt_file(path), [])

    def test_missing_required_field_fails(self):
        broken = VALID_PROMPT_YAML.replace("template: |\n  Responda com base apenas nas fontes oficiais.\n", "")
        path = self._write_prompt("sample_agent_v1.0.yaml", broken)
        errors = gov.validate_prompt_file(path)
        self.assertTrue(any("chaves obrigatórias ausentes" in e and "template" in e for e in errors))

    def test_bad_filename_pattern_fails(self):
        path = self._write_prompt("Sample-Agent-v1.yaml", VALID_PROMPT_YAML)
        errors = gov.validate_prompt_file(path)
        self.assertTrue(any("nome de arquivo inválido" in e for e in errors))

    def test_filename_version_mismatch_fails(self):
        mismatched = VALID_PROMPT_YAML.replace('version: "v1.0"', 'version: "v1.1"')
        path = self._write_prompt("sample_agent_v1.0.yaml", mismatched)
        errors = gov.validate_prompt_file(path)
        self.assertTrue(any("diverge de '<prompt_id>_<version>'" in e for e in errors))

    def test_invalid_status_fails(self):
        bad_status = VALID_PROMPT_YAML.replace('status: "PROPOSTO"', 'status: "PRODUCAO"')
        path = self._write_prompt("sample_agent_v1.0.yaml", bad_status)
        errors = gov.validate_prompt_file(path)
        self.assertTrue(any("'status' inválido" in e for e in errors))

    def test_empty_lists_and_blank_template_fail(self):
        bad_content = """\
prompt_id: "sample_agent"
version: "v1.0"
status: "PROPOSTO"
owner_role: "R5"
created_at: "2026-11-25"
compatible_models: []
system_constraints_enforced: []
template: "   "
"""
        path = self._write_prompt("sample_agent_v1.0.yaml", bad_content)
        errors = gov.validate_prompt_file(path)
        self.assertTrue(any("compatible_models" in e for e in errors))
        self.assertTrue(any("system_constraints_enforced" in e for e in errors))
        self.assertTrue(any("template" in e for e in errors))


class TestPromptImmutability(unittest.TestCase):
    def test_rejects_modification_on_existing_versioned_prompt(self):
        diff = "M\tmlops/prompts/nutritional_agent_v1.0.yaml\n"
        errors = gov.check_prompt_immutability_from_diff(diff)
        self.assertEqual(len(errors), 1)
        self.assertIn("nutritional_agent_v1.0.yaml", errors[0])
        self.assertIn("ADR-006", errors[0])

    def test_rejects_deletion_on_existing_versioned_prompt(self):
        diff = "D\tmlops/prompts/nutritional_agent_v1.0.yaml\n"
        errors = gov.check_prompt_immutability_from_diff(diff)
        self.assertEqual(len(errors), 1)
        self.assertIn("removido", errors[0])

    def test_rejects_rename_of_existing_versioned_prompt(self):
        diff = "R100\tmlops/prompts/nutritional_agent_v1.0.yaml\tmlops/prompts/nutritional_agent_v1.1.yaml\n"
        errors = gov.check_prompt_immutability_from_diff(diff)
        self.assertEqual(len(errors), 1)
        self.assertIn("renomeado", errors[0])

    def test_accepts_new_prompt_version_and_readme_edit(self):
        diff = (
            "A\tmlops/prompts/nutritional_agent_v1.1.yaml\n"
            "M\tmlops/prompts/README.md\n"
        )
        errors = gov.check_prompt_immutability_from_diff(diff)
        self.assertEqual(errors, [])

    def test_git_diff_invocation_reports_git_error(self):
        fake_proc = mock.Mock(returncode=128, stdout="", stderr="fatal: bad revision 'origin/missing...HEAD'")
        with mock.patch.object(gov.subprocess, "run", return_value=fake_proc) as run_mock:
            errors = gov.validate_prompt_immutability(REPO_ROOT, "origin/missing")
        run_mock.assert_called_once()
        self.assertEqual(len(errors), 1)
        self.assertIn("fetch-depth: 0", errors[0])


class TestRuntimeManifestValidation(unittest.TestCase):
    def _write_manifest(self, content: str) -> Path:
        tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: _cleanup_dir(tmp_dir))
        manifest = tmp_dir / "runtime-manifest.yaml"
        manifest.write_text(content, encoding="utf-8")
        return manifest

    def test_valid_manifest_passes(self):
        manifest = self._write_manifest(VALID_MANIFEST_YAML)
        self.assertEqual(gov.validate_runtime_manifest(manifest), [])

    def test_manifest_missing_required_sections_fails(self):
        incomplete = """\
schema_version: "1.0"
manifest_type: "mlops_runtime_configuration"
project: "Challenge 2 Berkanan"
configuration:
  config_id: "cfg-test"
"""
        manifest = self._write_manifest(incomplete)
        errors = gov.validate_runtime_manifest(manifest)
        self.assertTrue(any("chaves de topo obrigatórias ausentes" in e for e in errors))
        for expected_missing in ("llm", "knowledge_base_rag", "monitoring", "deployment"):
            self.assertTrue(any(expected_missing in e for e in errors))

    def test_manifest_with_empty_section_fails(self):
        broken = VALID_MANIFEST_YAML.replace("  prometheus_enabled: false", "")
        manifest = self._write_manifest(broken)
        errors = gov.validate_runtime_manifest(manifest)
        self.assertTrue(any("seção 'monitoring'" in e for e in errors))


class TestGoldDatasetValidation(unittest.TestCase):
    def _make_fake_repo_with_gold(self, csv_filename: str, rows: list[dict[str, str]]) -> Path:
        from benchmark import extraction as ex

        tmp_root = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: _cleanup_dir(tmp_root))

        exp_dir = tmp_root / "mlops" / "experiments"
        gold_dir = exp_dir / "testset" / "gabarito_fotos"
        gold_dir.mkdir(parents=True)

        # Link real benchmark package so `python -m benchmark.extraction` runs inside tmp_root
        (exp_dir / "benchmark").symlink_to(REPO_ROOT / "mlops" / "experiments" / "benchmark")

        csv_path = gold_dir / csv_filename
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ex.GOLD_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        return tmp_root

    def test_valid_gold_csv_passes(self):
        from benchmark import extraction as ex

        row = {c: "" for c in ex.GOLD_COLUMNS}
        row.update(foto_id="P01_boa", tipo="solido", condicao="boa", alergicos_visivel="sim", sodio_mg="120")
        tmp_root = self._make_fake_repo_with_gold("P01-P03.csv", [row])
        errors, info = gov.validate_gold_datasets(tmp_root)
        self.assertEqual(errors, [])
        self.assertIn("[OK]", info)

    def test_invalid_gold_csv_fails(self):
        from benchmark import extraction as ex

        row = {c: "" for c in ex.GOLD_COLUMNS}
        row.update(foto_id="P09_boa", tipo="solido", condicao="boa", alergicos_visivel="sim")
        tmp_root = self._make_fake_repo_with_gold("P01-P03.csv", [row])
        errors, _ = gov.validate_gold_datasets(tmp_root)
        self.assertEqual(len(errors), 1)
        self.assertIn("fora da faixa", errors[0])


def _cleanup_dir(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
