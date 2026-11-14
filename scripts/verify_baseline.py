#!/usr/bin/env python3
"""Verifica a integridade do snapshot backend-whatsapp-v0.1.0 e dos documentos de contexto.

Comprova que:
1. Todos os 7 arquivos arquivados em snapshots/backend/whatsapp-v0.1.0/original/
   existem e correspondem exatamente aos hashes SHA-256 registrados em SHA256SUMS.
2. Os arquivos executáveis canônicos em backend/ preservam os mesmos bytes do baseline
   inicial (ou reporta divergência caso o backend tenha evoluído posteriormente).
3. Os 3 documentos de contexto em docs/context/sources/ existem e não estão vazios.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_DIR = REPO_ROOT / "snapshots" / "backend" / "whatsapp-v0.1.0"
ORIGINAL_DIR = SNAPSHOT_DIR / "original"
SHA256SUMS_PATH = SNAPSHOT_DIR / "SHA256SUMS"
BACKEND_DIR = REPO_ROOT / "backend"
CONTEXT_SOURCES_DIR = REPO_ROOT / "docs" / "context" / "sources"

CANONICAL_MAPPING = {
    "README(1).md": "README.md",
    "graph.py": "graph.py",
    "main.py": "main.py",
    "requirements.txt": "requirements.txt",
    "schemas.py": "schemas.py",
    "state.py": "state.py",
    "test_api.sh": "test_api.sh",
}

EXPECTED_CONTEXT_FILES = {
    "contextoCLAUDEV2.md": "0c24269a73f6a3ad8983ac701fa76a3195c3ee2205f0de1c7184e3ad372a48d1",
    "adr.pdf": "293449cf5a9c0d9a930409ca96f318b75de08a6c558ab2d56bf4457c2bb3f317",
    "5_perguntas_escopo_essential_question.pdf": "cdd8a1e551bbe1f46a80105a80105a84e8bc548e0ea5e1e776a8cd714d3a8ca1d6699b",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_sha256sums(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"Linha inválida em SHA256SUMS: {raw_line!r}")
        expected_hash, filename = parts[0], parts[1].lstrip("* ")
        entries[filename] = expected_hash
    return entries


def main() -> int:
    errors: list[str] = []

    if not SHA256SUMS_PATH.is_file():
        print(f"[ERRO] Arquivo SHA256SUMS não encontrado: {SHA256SUMS_PATH}", file=sys.stderr)
        return 1

    checksums = parse_sha256sums(SHA256SUMS_PATH)
    if set(checksums.keys()) != set(CANONICAL_MAPPING.keys()):
        errors.append(
            f"Conjunto de arquivos em SHA256SUMS ({sorted(checksums.keys())}) "
            f"difere do esperado ({sorted(CANONICAL_MAPPING.keys())})."
        )

    print("=== 1. Verificando snapshot original (backend-whatsapp-v0.1.0) ===")
    for orig_name, canonical_name in CANONICAL_MAPPING.items():
        orig_path = ORIGINAL_DIR / orig_name
        expected_hash = checksums.get(orig_name)
        if not orig_path.is_file():
            errors.append(f"Arquivo ausente no snapshot: {orig_path}")
            continue
        actual_hash = sha256_file(orig_path)
        if actual_hash != expected_hash:
            errors.append(
                f"Hash divergente no snapshot para {orig_name}: "
                f"esperado={expected_hash}, obtido={actual_hash}"
            )
        else:
            print(f"  [OK] snapshot/{orig_name} ({actual_hash[:12]}...)")

        canonical_path = BACKEND_DIR / canonical_name
        if not canonical_path.is_file():
            errors.append(f"Arquivo canônico ausente em backend/: {canonical_path}")
        else:
            canonical_hash = sha256_file(canonical_path)
            if canonical_hash == actual_hash:
                print(f"  [OK] backend/{canonical_name} idêntico ao baseline v0.1.0")
            else:
                print(
                    f"  [INFO] backend/{canonical_name} modificado em relação ao baseline "
                    f"(hash atual={canonical_hash[:12]}...)"
                )

    print("\n=== 2. Verificando fontes documentais em docs/context/sources/ ===")
    expected_sources = {
        "contextoCLAUDEV2.md": "0c24269a73f6a3ad8983ac701fa76a3195c3ee2205f0de1c7184e3ad372a48d1",
        "adr.pdf": "293449cf5a9c0d9a930409ca96f318b75de08a6c558ab2d56bf4457c2bb3f317",
        "5_perguntas_escopo_essential_question.pdf": "cdd8a1e551bbe1f46a80105a84e8bc548e0ea5e1e776a8cd714d3a8ca1d6699b",
    }
    for doc_name, expected_doc_hash in expected_sources.items():
        doc_path = CONTEXT_SOURCES_DIR / doc_name
        if not doc_path.is_file():
            errors.append(f"Documento de contexto ausente: {doc_path}")
            continue
        actual_doc_hash = sha256_file(doc_path)
        if actual_doc_hash != expected_doc_hash:
            errors.append(
                f"Hash divergente para documento de contexto {doc_name}: "
                f"esperado={expected_doc_hash}, obtido={actual_doc_hash}"
            )
        else:
            print(f"  [OK] docs/context/sources/{doc_name} ({actual_doc_hash[:12]}...)")

    if errors:
        print("\n[FALHA] Erros de verificação encontrados:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print("\n[SUCESSO] Integridade do baseline e das fontes documentais comprovada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
