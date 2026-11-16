"""Carrega e valida o conjunto de teste (CSV) do Desafio 2.

Formato aprovado (contextoCLAUDEV2.md, seção 9.1): 50 perguntas nas categorias A a G.
Uso:  python -m benchmark.testset caminho/do/conjunto.csv
"""
from __future__ import annotations

import csv
import sys
from dataclasses import dataclass
from pathlib import Path

COLUMNS = [
    "ID",
    "Categoria",
    "Pergunta",
    "Resposta esperada (gabarito)",
    "Fonte esperada",
    "Comportamento esperado",
    "Métrica",
    "Conferir na fonte",
]

# Prefixo do ID -> (categoria, quantidade prevista no plano)
CATEGORIES = {
    "A": ("Guia Alimentar", 10),
    "B": ("Rotulagem ANVISA", 10),
    "C": ("Cálculo ALTO EM", 8),
    "D": ("Comparação de dois produtos", 6),
    "E": ("Alergênicos", 5),
    "F": ("Saúde e OMS", 5),
    "G": ("Fora do escopo", 6),
}


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    question: str
    expected_answer: str
    expected_source: str
    expected_behavior: str
    metric: str
    needs_source_check: bool

    @property
    def prefix(self) -> str:
        return self.id[:1].upper()

    @property
    def is_out_of_scope(self) -> bool:
        return self.prefix == "G"


def _delimiter(text: str) -> str:
    """Planilhas em pt-BR costumam exportar CSV com ponto e vírgula."""
    return ";" if ";" in text.splitlines()[0] else ","


def load(path: str | Path) -> list[Question]:
    """Lê o CSV (UTF-8, com ou sem BOM; separador vírgula ou ponto e vírgula)."""
    text = Path(path).read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(text.splitlines(), delimiter=_delimiter(text)))
    return [
        Question(
            id=(r.get("ID") or "").strip(),
            category=(r.get("Categoria") or "").strip(),
            question=(r.get("Pergunta") or "").strip(),
            expected_answer=(r.get("Resposta esperada (gabarito)") or "").strip(),
            expected_source=(r.get("Fonte esperada") or "").strip(),
            expected_behavior=(r.get("Comportamento esperado") or "").strip(),
            metric=(r.get("Métrica") or "").strip(),
            needs_source_check=(r.get("Conferir na fonte") or "").strip().lower() in {"sim", "s", "yes"},
        )
        for r in rows
    ]


def validate(path: str | Path, strict_counts: bool = False) -> tuple[list[str], list[str]]:
    """Retorna (erros, avisos). Erros impedem o uso; avisos só informam."""
    errors: list[str] = []
    warnings: list[str] = []

    text = Path(path).read_text(encoding="utf-8-sig")
    if not text.strip():
        return ["Arquivo vazio."], []
    header = next(csv.reader([text.splitlines()[0]], delimiter=_delimiter(text)))
    missing = [c for c in COLUMNS if c not in [h.strip() for h in header]]
    if missing:
        errors.append(f"Colunas ausentes: {missing}")
        return errors, warnings

    questions = load(path)
    seen: set[str] = set()
    counts = {p: 0 for p in CATEGORIES}
    for i, q in enumerate(questions, start=2):
        if not q.id:
            errors.append(f"Linha {i}: ID vazio.")
            continue
        if q.id in seen:
            errors.append(f"Linha {i}: ID duplicado {q.id}.")
        seen.add(q.id)
        if q.prefix not in CATEGORIES:
            errors.append(f"Linha {i}: prefixo de ID desconhecido em {q.id}.")
            continue
        counts[q.prefix] += 1
        if not q.question:
            errors.append(f"{q.id}: pergunta vazia.")
        if not q.expected_answer and not q.expected_behavior:
            errors.append(f"{q.id}: sem gabarito nem comportamento esperado.")
        if not q.is_out_of_scope and not q.expected_source:
            warnings.append(f"{q.id}: sem fonte esperada (necessária para medir recall e fidelidade).")

    for prefix, (name, expected) in CATEGORIES.items():
        if counts[prefix] != expected:
            msg = f"Categoria {prefix} ({name}): {counts[prefix]} perguntas, plano prevê {expected}."
            (errors if strict_counts else warnings).append(msg)

    pending = sum(q.needs_source_check for q in questions)
    if pending:
        warnings.append(f"{pending} pergunta(s) com 'Conferir na fonte = Sim': gabarito ainda não vale como referência.")
    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Uso: python -m benchmark.testset <conjunto.csv> [--strict]")
        return 2
    errors, warnings = validate(argv[1], strict_counts="--strict" in argv)
    for w in warnings:
        print(f"[AVISO] {w}")
    for e in errors:
        print(f"[ERRO] {e}")
    print("[OK] Conjunto de teste válido." if not errors else f"[FALHA] {len(errors)} erro(s).")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
