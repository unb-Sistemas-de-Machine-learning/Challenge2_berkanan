"""Benchmark de extração de rótulos (semana 4, ADR-002).

Compara, campo a campo, os valores lidos por cada motor (Tesseract, PaddleOCR, Gemini...)
com o gabarito digitado a partir das fotos. Formatos em testset/protocolo_fotos.md.

Uso:
    python -m benchmark.extraction testset/gabarito_fotos.csv results/<exp>/leituras.csv
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
import unicodedata
from pathlib import Path

# Campos numéricos da tabela nutricional (RDC 429/2020, art. 5º), por 100 g ou 100 ml, e a porção.
FIELDS = [
    "valor_energetico_kcal",
    "carboidratos_g",
    "acucares_totais_g",
    "acucares_adicionados_g",
    "proteinas_g",
    "gorduras_totais_g",
    "gorduras_saturadas_g",
    "gorduras_trans_g",
    "fibra_alimentar_g",
    "sodio_mg",
    "porcao_g",
]
ALLERGEN_FIELDS = ["alergicos_contem", "alergicos_pode_conter"]
GOLD_COLUMNS = ["foto_id", "tipo", "condicao", "alergicos_visivel", *FIELDS, *ALLERGEN_FIELDS]
READ_COLUMNS = ["motor", "foto_id", "tempo_ms", *FIELDS, *ALLERGEN_FIELDS]

TARGET_ACCURACY_PCT = 85.0
TOLERANCE = 0.001  # o OCR lê o número impresso: só aceita o mesmo valor


def _read_csv(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8-sig")
    delimiter = ";" if ";" in text.splitlines()[0] else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delimiter))


def _num(value: str | None) -> float | None:
    """Aceita vírgula ou ponto como decimal; sem separador de milhar (1000, não 1.000)."""
    if value is None or str(value).strip() == "":
        return None
    return float(str(value).strip().replace(",", "."))


def _norm(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return " ".join(plain.lower().split())


def allergen_set(value: str | None) -> set[str]:
    """'Leite; Soja' -> {'leite', 'soja'}"""
    return {_norm(p) for p in (value or "").split(";") if p.strip()}


def _pct(hit: int, total: int) -> float | None:
    return round(100 * hit / total, 2) if total else None


def compare(gold_rows: list[dict], read_rows: list[dict]) -> dict:
    gold = {r["foto_id"].strip(): r for r in gold_rows}
    by_engine: dict[str, list[dict]] = {}
    for r in read_rows:
        by_engine.setdefault(r["motor"].strip(), []).append(r)

    report = {}
    for engine, reads in sorted(by_engine.items()):
        reads_by_photo = {r["foto_id"].strip(): r for r in reads}
        hits = total = 0
        per_field = {f: [0, 0] for f in FIELDS}
        per_condition: dict[str, list[int]] = {}
        errors = []
        allergen_expected = allergen_found = 0
        photos_with_false_negative = []
        times = []

        for photo_id, g in gold.items():
            r = reads_by_photo.get(photo_id)
            if r is None:
                errors.append({"foto_id": photo_id, "campo": "*", "esperado": "foto", "lido": "não processada"})
            elif (t := _num(r.get("tempo_ms"))) is not None:
                times.append(t)
            cond = (g.get("condicao") or "sem_condicao").strip()
            per_condition.setdefault(cond, [0, 0])

            for f in FIELDS:
                expected = _num(g.get(f))
                got = _num(r.get(f)) if r else None
                if expected is None and got is None:
                    continue  # campo não existe no rótulo e não foi inventado
                ok = expected is not None and got is not None and abs(expected - got) <= TOLERANCE
                total += 1
                hits += ok
                per_field[f][0] += ok
                per_field[f][1] += 1
                per_condition[cond][0] += ok
                per_condition[cond][1] += 1
                if not ok:
                    errors.append({"foto_id": photo_id, "campo": f, "esperado": g.get(f, ""), "lido": (r or {}).get(f, "")})

            # Alergênicos: o risco é o falso negativo (alergênico do rótulo que não foi lido).
            if (g.get("alergicos_visivel") or "").strip().lower() in {"sim", "s"}:
                missing = []
                for f in ALLERGEN_FIELDS:
                    exp, got = allergen_set(g.get(f)), allergen_set((r or {}).get(f))
                    allergen_expected += len(exp)
                    allergen_found += len(exp & got)
                    missing += [f"{f}:{a}" for a in sorted(exp - got)]
                if missing:
                    photos_with_false_negative.append({"foto_id": photo_id, "faltou": missing})

        accuracy = _pct(hits, total)
        report[engine] = {
            "n_fotos_gabarito": len(gold),
            "n_fotos_lidas": len([p for p in gold if p in reads_by_photo]),
            "acerto_campos_pct": accuracy,
            "atinge_meta": None if accuracy is None else accuracy >= TARGET_ACCURACY_PCT,
            "acerto_por_campo_pct": {f: _pct(*v) for f, v in per_field.items()},
            "acerto_por_condicao_pct": {c: _pct(*v) for c, v in sorted(per_condition.items())},
            "alergicos_recall_pct": _pct(allergen_found, allergen_expected),
            "fotos_com_falso_negativo_alergico": photos_with_false_negative,
            "tempo_mediano_ms": round(statistics.median(times)) if times else None,
            "erros": errors,
        }
    return {"meta_acerto_pct": TARGET_ACCURACY_PCT, "motores": report}


def validate_gold(rows: list[dict]) -> list[str]:
    errors = []
    if rows:
        missing = [c for c in GOLD_COLUMNS if c not in rows[0]]
        if missing:
            return [f"Colunas ausentes no gabarito: {missing}"]
    seen = set()
    for r in rows:
        pid = (r.get("foto_id") or "").strip()
        if not pid:
            errors.append("foto_id vazio.")
            continue
        if pid in seen:
            errors.append(f"{pid}: foto_id duplicado.")
        seen.add(pid)
        if (r.get("tipo") or "").strip().lower() not in {"solido", "liquido"}:
            errors.append(f"{pid}: tipo deve ser 'solido' ou 'liquido'.")
        try:
            sugars, carbs = _num(r.get("acucares_totais_g")), _num(r.get("carboidratos_g"))
        except ValueError as exc:
            errors.append(f"{pid}: número inválido ({exc}).")
            continue
        if sugars is not None and carbs is not None and sugars > carbs:
            errors.append(f"{pid}: açúcares totais > carboidratos (confira a digitação).")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("Uso: python -m benchmark.extraction <gabarito_fotos.csv> <leituras.csv>")
        return 2
    gold = _read_csv(argv[1])
    problems = validate_gold(gold)
    if problems:
        print("\n".join(f"[ERRO] {p}" for p in problems))
        return 1
    print(json.dumps(compare(gold, _read_csv(argv[2])), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
