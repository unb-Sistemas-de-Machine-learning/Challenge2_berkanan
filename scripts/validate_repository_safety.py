#!/usr/bin/env python3
"""Validador de segurança, LGPD e integridade de migrações SQL (Issue #73).

Verifica automaticamente em CI e localmente:
1. Unicidade de prefixo numérico e imutabilidade das migrações `migrations/NNN_*.sql`
   já existentes na branch base (`AGENTS.md` §5).
2. Ausência de arquivos sensíveis rastreados (`.env`, `.env.prod`, chaves privadas).
3. Ausência de credenciais/tokens reais vazados no código rastreado (LGPD).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SQL_MIGRATION_FILENAME_RE = re.compile(r"^(\d{3})_.+\.sql$")
SQL_MIGRATION_PATH_RE = re.compile(r"^migrations/\d{3}_.+\.sql$")

ALLOWED_ENV_EXAMPLES = frozenset({".env.example", ".env.prod.example"})
FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
FORBIDDEN_BASENAMES = frozenset({"id_rsa", "id_ed25519", "id_ecdsa", "id_dsa"})

PLACEHOLDER_MARKERS = (
    "change_me",
    "replace_with",
    "placeholder",
    "dev_only",
    "example",
    "exemplo",
    "fake",
)

IGNORED_SCAN_PREFIXES = (
    "snapshots/",
    "docs/context/sources/",
)

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Chave Google/Gemini (AIza...)", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Token GitHub clássico (ghp_...)", re.compile(r"\bghp_[0-9A-Za-z]{36}\b")),
    ("Token GitHub fine-grained", re.compile(r"\bgithub_pat_[0-9A-Za-z_]{50,}\b")),
    ("Chave de API estilo OpenAI (sk-...)", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    (
        "Cabeçalho de chave privada PEM/SSH",
        re.compile(r"-----" + r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY" + r"-----"),
    ),
)


def _is_sql_migration_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/")
    return bool(SQL_MIGRATION_PATH_RE.match(normalized))


def validate_migration_prefixes(repo_root: Path) -> list[str]:
    """Garante que não existem prefixos numéricos duplicados em `migrations/NNN_*.sql`."""
    migrations_dir = repo_root / "migrations"
    if not migrations_dir.is_dir():
        return [f"Diretório de migrações não encontrado: {migrations_dir}"]

    by_prefix: dict[str, list[str]] = defaultdict(list)
    for path in sorted(migrations_dir.iterdir()):
        if not path.is_file():
            continue
        match = SQL_MIGRATION_FILENAME_RE.match(path.name)
        if match:
            by_prefix[match.group(1)].append(path.name)

    if not by_prefix:
        return [f"Nenhuma migração numerada (`NNN_*.sql`) encontrada em {migrations_dir}."]

    errors: list[str] = []
    for prefix, filenames in sorted(by_prefix.items()):
        if len(filenames) > 1:
            errors.append(
                f"Prefixo numérico duplicado '{prefix}' em migrations/: {', '.join(filenames)}. "
                "Cada migração deve possuir número sequencial exclusivo."
            )
    return errors


def check_sql_migrations_immutability_from_diff(diff_output: str) -> list[str]:
    """Bloqueia alteração (`M`), remoção (`D`/`T`) ou renomeação (`R*`) de migrações SQL existentes."""
    errors: list[str] = []
    for raw_line in diff_output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue

        status_code = parts[0].strip()
        status_kind = status_code[:1].upper()

        if status_kind in {"M", "D", "T"}:
            target_path = parts[1].strip()
            if _is_sql_migration_path(target_path):
                action = {"M": "modificada", "D": "removida", "T": "alterada"}[status_kind]
                errors.append(
                    f"Violação de imutabilidade SQL (AGENTS.md §5): a migração '{target_path}' "
                    f"foi {action} (status git '{status_code}'). Nunca edite migrações já "
                    "aplicadas; crie uma nova migração sequencial (ex.: 012_*.sql)."
                )
        elif status_kind == "R":
            old_path = parts[1].strip()
            new_path = parts[2].strip() if len(parts) >= 3 else ""
            if _is_sql_migration_path(old_path):
                errors.append(
                    f"Violação de imutabilidade SQL (AGENTS.md §5): a migração '{old_path}' "
                    f"foi renomeada para '{new_path}' (status git '{status_code}'). "
                    "Preserve o arquivo original e crie uma nova migração sequencial."
                )
    return errors


def validate_sql_migrations_immutability(repo_root: Path, base_ref: str) -> list[str]:
    """Executa `git diff --name-status <base_ref>...HEAD -- migrations/` e valida imutabilidade."""
    cmd = ["git", "diff", "--name-status", f"{base_ref}...HEAD", "--", "migrations/"]
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
    return check_sql_migrations_immutability_from_diff(proc.stdout)


def _git_ls_files(repo_root: Path) -> tuple[list[str], str | None]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        return [], f"Falha ao listar arquivos rastreados com `git ls-files`: {detail}"
    files = [line.strip().replace("\\", "/") for line in proc.stdout.splitlines() if line.strip()]
    return files, None


def is_forbidden_sensitive_path(rel_path: str) -> bool:
    """Identifica arquivos sensíveis (.env reais ou chaves privadas) que não devem ir ao Git."""
    normalized = rel_path.replace("\\", "/")
    name = Path(normalized).name
    if name in ALLOWED_ENV_EXAMPLES or name.endswith(".example"):
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    if name in FORBIDDEN_BASENAMES:
        return True
    return any(name.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES)


def validate_forbidden_tracked_files(repo_root: Path) -> list[str]:
    """Garante que nenhum arquivo `.env` real ou chave privada esteja rastreado pelo Git."""
    files, ls_error = _git_ls_files(repo_root)
    if ls_error is not None:
        return [ls_error]

    errors: list[str] = []
    for rel_path in files:
        if is_forbidden_sensitive_path(rel_path):
            errors.append(
                f"Arquivo sensível rastreado no Git (risco de exposição/LGPD): '{rel_path}'. "
                "Remova do índice (`git rm --cached`) e mantenha apenas arquivos `.example`."
            )
    return errors


def scan_text_for_secrets(text: str, rel_path: str) -> list[str]:
    """Procura padrões de credenciais/chaves reais em conteúdo textual, ignorando placeholders."""
    findings: list[str] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if any(marker in lowered for marker in PLACEHOLDER_MARKERS):
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    f"Possível credencial exposta ({label}) em '{rel_path}:{line_no}'."
                )
    return findings


def validate_no_secret_leaks(repo_root: Path) -> list[str]:
    """Escaneia todos os arquivos textuais rastreados em busca de segredos vazados."""
    files, ls_error = _git_ls_files(repo_root)
    if ls_error is not None:
        return [ls_error]

    errors: list[str] = []
    for rel_path in files:
        if any(rel_path.startswith(prefix) for prefix in IGNORED_SCAN_PREFIXES):
            continue
        file_path = repo_root / rel_path
        if not file_path.is_file():
            continue
        try:
            raw_bytes = file_path.read_bytes()
        except OSError as exc:
            errors.append(f"Falha ao ler '{rel_path}': {exc}")
            continue
        if b"\x00" in raw_bytes:
            continue
        text = raw_bytes.decode("utf-8", errors="replace")
        errors.extend(scan_text_for_secrets(text, rel_path))
    return errors


def _emit_error(message: str) -> None:
    print(f"  [ERRO] {message}", file=sys.stderr)
    if os.getenv("GITHUB_ACTIONS") == "true":
        print(f"::error::{message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Valida segurança, LGPD (ausência de segredos e .env) e integridade/imutabilidade "
            "das migrações SQL."
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
        help="Referência git base (ex.: origin/main) para validar imutabilidade das migrações SQL.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = args.repo_root.resolve()

    all_errors: list[str] = []

    print("=== 1. Verificando unicidade de prefixos em migrations/NNN_*.sql ===")
    prefix_errors = validate_migration_prefixes(repo_root)
    if prefix_errors:
        all_errors.extend(prefix_errors)
        for err in prefix_errors:
            _emit_error(err)
    else:
        print("  [OK] Prefixos numéricos das migrações SQL estão únicos e íntegros.")

    if args.base_ref:
        print(f"\n=== 2. Verificando imutabilidade das migrações SQL contra '{args.base_ref}' ===")
        sql_diff_errors = validate_sql_migrations_immutability(repo_root, args.base_ref)
        if sql_diff_errors:
            all_errors.extend(sql_diff_errors)
            for err in sql_diff_errors:
                _emit_error(err)
        else:
            print(
                f"  [OK] Nenhuma migração SQL existente foi modificada, removida ou renomeada "
                f"em relação a {args.base_ref}."
            )
    else:
        print("\n=== 2. Verificação de imutabilidade das migrações SQL ===")
        print("  [INFO] --base-ref não informado; checagem de diff SQL ignorada.")

    print("\n=== 3. Verificando arquivos sensíveis rastreados (.env / chaves privadas) ===")
    file_errors = validate_forbidden_tracked_files(repo_root)
    if file_errors:
        all_errors.extend(file_errors)
        for err in file_errors:
            _emit_error(err)
    else:
        print("  [OK] Nenhum arquivo sensível (.env real ou chave privada) rastreado pelo Git.")

    print("\n=== 4. Escaneando arquivos textuais em busca de credenciais vazadas ===")
    secret_errors = validate_no_secret_leaks(repo_root)
    if secret_errors:
        all_errors.extend(secret_errors)
        for err in secret_errors:
            _emit_error(err)
    else:
        print("  [OK] Nenhuma credencial ou chave privada detectada nos arquivos rastreados.")

    if all_errors:
        print(
            f"\n[FALHA] Validação de segurança/SQL reprovada com {len(all_errors)} erro(s).",
            file=sys.stderr,
        )
        return 1

    print("\n[SUCESSO] Todas as checagens de segurança, LGPD e migrações SQL passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
