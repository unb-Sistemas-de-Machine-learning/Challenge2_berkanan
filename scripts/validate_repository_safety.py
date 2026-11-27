#!/usr/bin/env python3
"""Validador de segurança, LGPD e integridade de migrações SQL (Issue #73).

Verifica automaticamente em CI e localmente:
1. Unicidade de prefixo numérico e imutabilidade das migrações `migrations/NNN_*.sql`
   já existentes na branch base (`AGENTS.md` §5).
2. Ausência de arquivos sensíveis rastreados (`.env`, `.env.prod`, chaves privadas).
3. Ausência de credenciais/tokens reais vazados no código rastreado (LGPD).
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SQL_MIGRATION_FILENAME_RE = re.compile(r"^(\d{3})_.+\.sql$")
SQL_MIGRATION_PATH_RE = re.compile(r"^migrations/\d{3}_.+\.sql$")


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
