#!/usr/bin/env python3
"""Validador de governança MLOps do Challenge 2 Berkanan (ADR-006 / Issue #65).

Verifica automaticamente em CI e localmente:
1. Schema e nomenclatura dos prompts versionados em `mlops/prompts/*.yaml`.
2. Imutabilidade de prompts versionados já existentes (quando `--base-ref` é informado),
   impedindo edição, remoção ou renomeação de versões publicadas (ADR-006).
3. Schema estrutural do manifesto de runtime (`mlops/manifests/runtime-manifest.yaml`).
4. Validação estrutural dos gabaritos CSV em `mlops/experiments/testset/gabarito_fotos/`
   quando houver arquivos `.csv` presentes (`--check-gold`, habilitado por padrão).
"""

from __future__ import annotations

import argparse
import datetime
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - tratado explicitamente em runtime
    yaml = None  # type: ignore[assignment]
    _YAML_IMPORT_ERROR = exc
else:
    _YAML_IMPORT_ERROR = None

REPO_ROOT = Path(__file__).resolve().parent.parent

PROMPT_FILENAME_RE = re.compile(r"^[a-z0-9_]+_v\d+\.\d+\.yaml$")
VERSIONED_PROMPT_PATH_RE = re.compile(r"^mlops/prompts/[^/]+_v[^/]+\.yaml$")

VALID_PROMPT_STATUSES = frozenset({"PROPOSTO", "EM_BENCHMARK", "APROVADO", "OBSOLETO"})

REQUIRED_PROMPT_KEYS = (
    "prompt_id",
    "version",
    "status",
    "owner_role",
    "created_at",
    "compatible_models",
    "system_constraints_enforced",
    "template",
)

REQUIRED_MANIFEST_SCALAR_KEYS = (
    "schema_version",
    "manifest_type",
    "project",
)

REQUIRED_MANIFEST_SECTION_KEYS = (
    "configuration",
    "llm",
    "prompts",
    "knowledge_base_rag",
    "structured_database",
    "ocr_pipeline",
    "verifier",
    "monitoring",
    "deployment",
)

REQUIRED_MANIFEST_KEYS = REQUIRED_MANIFEST_SCALAR_KEYS + REQUIRED_MANIFEST_SECTION_KEYS


def _require_yaml() -> Any:
    if yaml is None:
        raise RuntimeError(
            "Dependência 'PyYAML' não instalada. Instale com `python3 -m pip install pyyaml` "
            f"(erro original: {_YAML_IMPORT_ERROR})."
        )
    return yaml


def _load_yaml_dict(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    yaml_mod = _require_yaml()
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"{path}: falha ao ler arquivo ({exc})."

    try:
        parsed = yaml_mod.safe_load(raw_text)
    except yaml_mod.YAMLError as exc:
        return None, f"{path}: YAML inválido ({exc})."

    if not isinstance(parsed, dict):
        return None, f"{path}: o documento YAML deve ser um mapeamento (objeto chave-valor)."

    return parsed, None


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_non_empty_str_list(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) > 0
        and all(_is_non_empty_str(item) for item in value)
    )


def validate_prompt_file(path: Path) -> list[str]:
    """Valida convenção de nome e schema YAML de um único arquivo de prompt."""
    errors: list[str] = []
    label = path.name

    if not PROMPT_FILENAME_RE.match(path.name):
        errors.append(
            f"{label}: nome de arquivo inválido (esperado padrão '<prompt_id>_v<MAJOR>.<MINOR>.yaml', "
            f"regex `{PROMPT_FILENAME_RE.pattern}`)."
        )

    data, load_err = _load_yaml_dict(path)
    if load_err is not None or data is None:
        errors.append(load_err or f"{label}: conteúdo YAML inválido.")
        return errors

    missing_keys = [key for key in REQUIRED_PROMPT_KEYS if key not in data]
    if missing_keys:
        errors.append(f"{label}: chaves obrigatórias ausentes: {', '.join(missing_keys)}.")

    prompt_id = data.get("prompt_id")
    if "prompt_id" in data and not _is_non_empty_str(prompt_id):
        errors.append(f"{label}: 'prompt_id' deve ser uma string não vazia.")

    version = data.get("version")
    if "version" in data and not _is_non_empty_str(version):
        errors.append(f"{label}: 'version' deve ser uma string não vazia (ex.: 'v1.0').")

    status = data.get("status")
    if "status" in data and status not in VALID_PROMPT_STATUSES:
        valid_str = ", ".join(sorted(VALID_PROMPT_STATUSES))
        errors.append(
            f"{label}: 'status' inválido ({status!r}); valores permitidos: {valid_str}."
        )

    owner_role = data.get("owner_role")
    if "owner_role" in data and not _is_non_empty_str(owner_role):
        errors.append(f"{label}: 'owner_role' deve ser uma string não vazia (ex.: 'R5').")

    created_at = data.get("created_at")
    if "created_at" in data:
        valid_date = isinstance(created_at, datetime.date) or _is_non_empty_str(created_at)
        if not valid_date:
            errors.append(
                f"{label}: 'created_at' deve ser uma string ou data ISO não vazia (ex.: '2026-11-25')."
            )

    if "compatible_models" in data and not _is_non_empty_str_list(data.get("compatible_models")):
        errors.append(f"{label}: 'compatible_models' deve ser uma lista não vazia de strings.")

    if "system_constraints_enforced" in data and not _is_non_empty_str_list(
        data.get("system_constraints_enforced")
    ):
        errors.append(
            f"{label}: 'system_constraints_enforced' deve ser uma lista não vazia de strings."
        )

    if "template" in data and not _is_non_empty_str(data.get("template")):
        errors.append(f"{label}: 'template' deve ser uma string não vazia.")

    if _is_non_empty_str(prompt_id) and _is_non_empty_str(version):
        expected_stem = f"{prompt_id}_{version}"
        if path.stem != expected_stem:
            errors.append(
                f"{label}: nome do arquivo ('{path.stem}') diverge de '<prompt_id>_<version>' "
                f"('{expected_stem}')."
            )

    return errors


def validate_prompts_directory(repo_root: Path) -> tuple[list[str], list[Path]]:
    """Valida todos os arquivos `mlops/prompts/*.yaml` do repositório."""
    prompts_dir = repo_root / "mlops" / "prompts"
    if not prompts_dir.is_dir():
        return [f"Diretório de prompts não encontrado: {prompts_dir}"], []

    prompt_files = sorted(prompts_dir.glob("*.yaml"))
    if not prompt_files:
        return [f"Nenhum arquivo de prompt versionado (*.yaml) encontrado em {prompts_dir}."], []

    errors: list[str] = []
    for prompt_path in prompt_files:
        errors.extend(validate_prompt_file(prompt_path))

    return errors, prompt_files


def _is_versioned_prompt_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    return bool(VERSIONED_PROMPT_PATH_RE.match(normalized))


def is_status_only_prompt_change(base_yaml_text: str, head_yaml_text: str) -> bool:
    """Retorna True somente se a única diferença válida no YAML for o campo `status`."""
    yaml_mod = _require_yaml()
    try:
        base_data = yaml_mod.safe_load(base_yaml_text)
        head_data = yaml_mod.safe_load(head_yaml_text)
    except yaml_mod.YAMLError:
        return False

    if not isinstance(base_data, dict) or not isinstance(head_data, dict):
        return False
    if head_data.get("status") not in VALID_PROMPT_STATUSES:
        return False
    if set(base_data.keys()) != set(head_data.keys()):
        return False
    if base_data.get("status") == head_data.get("status"):
        return False

    base_without_status = {k: v for k, v in base_data.items() if k != "status"}
    head_without_status = {k: v for k, v in head_data.items() if k != "status"}
    return base_without_status == head_without_status


def _git_show_file(repo_root: Path, ref: str, rel_path: str) -> str | None:
    proc = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def check_prompt_immutability_from_diff(
    diff_output: str,
    repo_root: Path | None = None,
    base_ref: str | None = None,
) -> list[str]:
    """Avalia a saída de `git diff --name-status` sob a regra de imutabilidade (ADR-006).

    Rejeita qualquer edição (exceto transição exclusiva do campo `status`), deleção (`D`),
    mudança de tipo (`T`) ou renomeação (`R*`) em prompts versionados (`mlops/prompts/*_v*.yaml`).
    Permite adição (`A`), cópia (`C*`) e alterações em documentação (como `mlops/prompts/README.md`).
    """
    errors: list[str] = []
    for raw_line in diff_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split("\t")
        if len(parts) < 2:
            continue

        status_code = parts[0].strip()
        status_kind = status_code[0].upper() if status_code else ""

        if status_kind in {"M", "D", "T"}:
            target_path = parts[1].strip()
            if not _is_versioned_prompt_path(target_path):
                continue

            if status_kind == "M" and repo_root is not None and base_ref is not None:
                base_text = _git_show_file(repo_root, base_ref, target_path)
                head_file = repo_root / target_path
                if base_text is not None and head_file.is_file():
                    head_text = head_file.read_text(encoding="utf-8")
                    if is_status_only_prompt_change(base_text, head_text):
                        print(
                            f"  [INFO] Transição exclusiva de `status` permitida em '{target_path}'."
                        )
                        continue

            action = {"M": "modificado", "D": "removido", "T": "alterado"}[status_kind]
            errors.append(
                f"Violação de imutabilidade (ADR-006): o prompt versionado '{target_path}' "
                f"foi {action} (status git '{status_code}'). Crie uma nova versão "
                "(ex.: v1.1 ou v2.0) em vez de editar conteúdo ou remover uma versão existente."
            )
        elif status_kind == "R":
            old_path = parts[1].strip()
            new_path = parts[2].strip() if len(parts) >= 3 else ""
            if _is_versioned_prompt_path(old_path):
                errors.append(
                    f"Violação de imutabilidade (ADR-006): o prompt versionado '{old_path}' "
                    f"foi renomeado para '{new_path}' (status git '{status_code}'). Preserve o "
                    "arquivo original e adicione uma nova versão (ex.: v1.1 ou v2.0)."
                )

    return errors


def validate_prompt_immutability(repo_root: Path, base_ref: str) -> list[str]:
    """Executa `git diff --name-status <base_ref>...HEAD -- mlops/prompts/` e valida imutabilidade."""
    cmd = ["git", "diff", "--name-status", f"{base_ref}...HEAD", "--", "mlops/prompts/"]
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        return [
            f"Falha ao executar `{' '.join(cmd)}` (exit={proc.returncode}): {detail}. "
            "Verifique se o ref base existe e se o checkout possui histórico completo (fetch-depth: 0)."
        ]

    return check_prompt_immutability_from_diff(proc.stdout, repo_root=repo_root, base_ref=base_ref)


def validate_runtime_manifest(manifest_path: Path) -> list[str]:
    """Valida a estrutura obrigatória do manifesto `mlops/manifests/runtime-manifest.yaml`."""
    if not manifest_path.is_file():
        return [f"Manifesto de runtime não encontrado: {manifest_path}"]

    data, load_err = _load_yaml_dict(manifest_path)
    if load_err is not None or data is None:
        return [load_err or f"{manifest_path}: conteúdo YAML inválido."]

    errors: list[str] = []
    missing_keys = [key for key in REQUIRED_MANIFEST_KEYS if key not in data]
    if missing_keys:
        errors.append(
            f"{manifest_path.name}: chaves de topo obrigatórias ausentes: {', '.join(missing_keys)}."
        )

    for key in REQUIRED_MANIFEST_SCALAR_KEYS:
        if key in data and not _is_non_empty_str(data.get(key)):
            errors.append(f"{manifest_path.name}: '{key}' deve ser uma string não vazia.")

    for key in REQUIRED_MANIFEST_SECTION_KEYS:
        if key in data:
            section = data.get(key)
            if not isinstance(section, dict) or not section:
                errors.append(
                    f"{manifest_path.name}: seção '{key}' deve ser um mapeamento YAML não vazio."
                )

    return errors


def validate_gold_datasets(repo_root: Path) -> tuple[list[str], str]:
    """Valida CSVs em `mlops/experiments/testset/gabarito_fotos/` via `benchmark.extraction`."""
    experiments_dir = repo_root / "mlops" / "experiments"
    gold_dir = experiments_dir / "testset" / "gabarito_fotos"

    if not gold_dir.is_dir():
        return [], f"Diretório {gold_dir.relative_to(repo_root)} ausente; validação ignorada."

    csv_files = sorted(gold_dir.glob("*.csv"))
    if not csv_files:
        return (
            [],
            "Nenhum arquivo CSV em mlops/experiments/testset/gabarito_fotos/ no momento; "
            "validação ignorada.",
        )

    cmd = [sys.executable, "-m", "benchmark.extraction", "--validar", "testset/gabarito_fotos/"]
    proc = subprocess.run(
        cmd,
        cwd=experiments_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (proc.stdout.strip(), proc.stderr.strip()) if part)
    if proc.returncode != 0:
        return (
            [
                f"Validação de gabaritos em mlops/experiments/testset/gabarito_fotos/ falhou "
                f"(exit={proc.returncode}):\n{output}"
            ],
            output,
        )

    return [], output or f"{len(csv_files)} arquivo(s) CSV validado(s) sem erros."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Valida governança MLOps (schemas de prompts, imutabilidade ADR-006, "
            "runtime-manifest.yaml e gabaritos CSV)."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Raiz do repositório a validar (padrão: raiz do projeto).",
    )
    parser.add_argument(
        "--base-ref",
        type=str,
        default=None,
        help=(
            "Referência git base (ex.: origin/main) para verificar imutabilidade de prompts "
            "versionados via `git diff --name-status <base-ref>...HEAD -- mlops/prompts/`."
        ),
    )
    parser.add_argument(
        "--check-gold",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Executa validação estrutural dos CSVs em mlops/experiments/testset/gabarito_fotos/.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    try:
        _require_yaml()
    except RuntimeError as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 1

    all_errors: list[str] = []

    print("=== 1. Validando schemas de prompts em mlops/prompts/*.yaml ===")
    prompt_errors, prompt_files = validate_prompts_directory(repo_root)
    if prompt_errors:
        all_errors.extend(prompt_errors)
        for err in prompt_errors:
            print(f"  [ERRO] {err}", file=sys.stderr)
    else:
        for path in prompt_files:
            print(f"  [OK] {path.relative_to(repo_root)}")

    if args.base_ref:
        print(f"\n=== 2. Verificando imutabilidade de prompts contra '{args.base_ref}' ===")
        immutability_errors = validate_prompt_immutability(repo_root, args.base_ref)
        if immutability_errors:
            all_errors.extend(immutability_errors)
            for err in immutability_errors:
                print(f"  [ERRO] {err}", file=sys.stderr)
        else:
            print(
                f"  [OK] Nenhum prompt versionado foi modificado, removido ou renomeado "
                f"em relação a {args.base_ref}."
            )
    else:
        print("\n=== 2. Verificação de imutabilidade de prompts ===")
        print("  [INFO] --base-ref não informado; checagem de diff git ignorada.")

    print("\n=== 3. Validando manifesto de runtime (mlops/manifests/runtime-manifest.yaml) ===")
    manifest_path = repo_root / "mlops" / "manifests" / "runtime-manifest.yaml"
    manifest_errors = validate_runtime_manifest(manifest_path)
    if manifest_errors:
        all_errors.extend(manifest_errors)
        for err in manifest_errors:
            print(f"  [ERRO] {err}", file=sys.stderr)
    else:
        print(f"  [OK] {manifest_path.relative_to(repo_root)}")

    if args.check_gold:
        print("\n=== 4. Validando gabaritos CSV (mlops/experiments/testset/gabarito_fotos/) ===")
        gold_errors, gold_info = validate_gold_datasets(repo_root)
        if gold_errors:
            all_errors.extend(gold_errors)
            for err in gold_errors:
                print(f"  [ERRO] {err}", file=sys.stderr)
        else:
            print(f"  [OK] {gold_info}")
    else:
        print("\n=== 4. Validação de gabaritos CSV ===")
        print("  [INFO] --no-check-gold informado; validação de gabaritos ignorada.")

    if all_errors:
        print(
            f"\n[FALHA] Governança MLOps reprovada com {len(all_errors)} erro(s).",
            file=sys.stderr,
        )
        return 1

    print("\n[SUCESSO] Todas as validações de governança MLOps passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
