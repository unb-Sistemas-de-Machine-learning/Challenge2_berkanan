"""Métricas do benchmark e regra de decisão do verificador (ADR-005).

Entrada: planilha de correção (CSV) com uma linha por resposta (config × repetição × pergunta),
preenchida pelo corretor a partir de `results/<experimento>/correcao.csv`:

    config, rep, question_id, category, latency_ms, llm_calls,
    correct (1/0), claims_total, claims_supported, refused (1/0)

Células vazias = não corrigido (ficam fora da média, nunca contam como 0).
Uso:  python -m benchmark.metrics results/<experimento>/correcao.csv
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

# Regra aprovada em 11/11 (contextoCLAUDEV2.md, seção 5.4)
MIN_FIDELITY_GAIN_PP = 5.0
MAX_EXTRA_LATENCY_S = 3.0

# Metas da seção 9 (proposta inicial)
TARGETS = {"fidelity_pct": 90.0, "refusal_pct": 90.0, "median_latency_s": 10.0, "avg_llm_calls": 2.0}


@dataclass
class ConfigMetrics:
    config: str
    n_responses: int
    accuracy_pct: float | None
    fidelity_pct: float | None
    refusal_pct: float | None
    median_latency_s: float | None
    avg_llm_calls: float | None
    n_graded_accuracy: int
    n_graded_fidelity: int
    n_graded_refusal: int


def _num(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(str(value).strip().replace(",", "."))


def _pct(values: list[float]) -> float | None:
    return round(100 * sum(values) / len(values), 2) if values else None


def load_rows(path: str | Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8-sig")
    delimiter = ";" if ";" in text.splitlines()[0] else ","
    return list(csv.DictReader(text.splitlines(), delimiter=delimiter))


def compute(rows: list[dict]) -> dict[str, ConfigMetrics]:
    by_config: dict[str, list[dict]] = {}
    for r in rows:
        by_config.setdefault(r["config"].strip().upper(), []).append(r)

    result = {}
    for config, items in sorted(by_config.items()):
        correct = [v for r in items if (v := _num(r.get("correct"))) is not None]
        refused = [
            v for r in items
            if r.get("question_id", "").strip().upper().startswith("G") and (v := _num(r.get("refused"))) is not None
        ]
        # Fidelidade = afirmações sustentadas / afirmações totais (micro-média), fora a categoria G.
        total = supported = 0.0
        n_fid = 0
        for r in items:
            t, s = _num(r.get("claims_total")), _num(r.get("claims_supported"))
            if t is None or s is None or t <= 0:
                continue
            if s > t:
                raise ValueError(f"{config}/{r.get('question_id')}: claims_supported > claims_total")
            total, supported, n_fid = total + t, supported + s, n_fid + 1
        latencies = [v / 1000 for r in items if (v := _num(r.get("latency_ms"))) is not None]
        calls = [v for r in items if (v := _num(r.get("llm_calls"))) is not None]

        result[config] = ConfigMetrics(
            config=config,
            n_responses=len(items),
            accuracy_pct=_pct(correct),
            fidelity_pct=round(100 * supported / total, 2) if total else None,
            refusal_pct=_pct(refused),
            median_latency_s=round(statistics.median(latencies), 3) if latencies else None,
            avg_llm_calls=round(statistics.mean(calls), 2) if calls else None,
            n_graded_accuracy=len(correct),
            n_graded_fidelity=n_fid,
            n_graded_refusal=len(refused),
        )
    return result


def decide_verifier(b: ConfigMetrics | None, c: ConfigMetrics | None) -> dict:
    """Config. C só fica se ganhar >= 5 pp de fidelidade sobre B com <= 3 s a mais de latência mediana."""
    if not b or not c or None in (b.fidelity_pct, c.fidelity_pct, b.median_latency_s, c.median_latency_s):
        return {"decision": "SEM_DADOS", "reason": "Faltam fidelidade ou latência de B ou C."}
    gain = round(c.fidelity_pct - b.fidelity_pct, 2)
    extra = round(c.median_latency_s - b.median_latency_s, 3)
    adopt = gain >= MIN_FIDELITY_GAIN_PP and extra <= MAX_EXTRA_LATENCY_S
    return {
        "decision": "ADOTAR_C" if adopt else "MANTER_B",
        "fidelity_gain_pp": gain,
        "extra_latency_s": extra,
        "reason": (
            f"Ganho de fidelidade {gain} pp (mín. {MIN_FIDELITY_GAIN_PP}) e "
            f"latência extra {extra} s (máx. {MAX_EXTRA_LATENCY_S})."
        ),
    }


def report(rows: list[dict]) -> dict:
    metrics = compute(rows)
    return {
        "configs": {k: asdict(v) for k, v in metrics.items()},
        "verifier_decision": decide_verifier(metrics.get("B"), metrics.get("C")),
        "targets": TARGETS,
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Uso: python -m benchmark.metrics <correcao.csv>")
        return 2
    print(json.dumps(report(load_rows(argv[1])), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
