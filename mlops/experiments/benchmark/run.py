"""Executa o benchmark do verificador (configs. A/B/C) contra a API `POST /api/analyze`.

Para cada configuração × repetição × pergunta, grava a resposta bruta e gera a planilha
de correção, que o corretor preenche e depois passa para `benchmark.metrics`.

Uso:
    python -m benchmark.run --testset testset/conjunto.csv --configs A B C --reps 3 \
        --api http://127.0.0.1:8000

Saída em results/<experiment_id>/:
    run.json         metadados (commit, manifesto, versões dos prompts, modelo, configs,
                     e motivo quando o resultado não vale como oficial)
    respostas.jsonl  uma linha por chamada, com a resposta completa da API
    correcao.csv     planilha para corrigir (correct, claims_total, claims_supported, refused)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from benchmark import testset

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "mlops" / "manifests" / "runtime-manifest.yaml"
PROMPTS_DIR = ROOT / "mlops" / "prompts"

# Como cada configuração é pedida à API. `verifier_mode` ainda não existe no contrato
# (backend/schemas.py ignora campos extras): proposta para R2/R5 distinguirem B de C.
CONFIG_PAYLOADS = {
    "A": {"enable_verifier": False},
    "B": {"enable_verifier": True, "verifier_mode": "rules"},
    "C": {"enable_verifier": True, "verifier_mode": "llm"},
}

# Prefixo da pergunta -> request_type da API
REQUEST_TYPES = {"D": "comparison"}

REFUSAL_TEXT = "não há evidência suficiente"

GRADING_COLUMNS = [
    "config", "rep", "question_id", "category", "latency_ms", "llm_calls",
    "correct", "claims_total", "claims_supported", "refused",
    "pergunta", "gabarito", "comportamento_esperado", "resposta", "fontes", "observacao",
]


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido"


def manifest_status() -> str:
    if not MANIFEST.exists():
        return "desconhecido"
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("status:"):
            return line.split(":", 1)[1].strip().strip('"')
    return "desconhecido"


def prompt_versions(prompts_dir: Path = PROMPTS_DIR) -> dict[str, dict[str, str]]:
    """Lê `prompt_id`, `version` e `status` de cada mlops/prompts/*.yaml (sem depender de PyYAML)."""
    versions: dict[str, dict[str, str]] = {}
    for path in sorted(prompts_dir.glob("*.yaml")):
        fields: dict[str, str] = {"arquivo": path.name}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition(":")
            if sep and key in ("prompt_id", "version", "status"):
                fields[key] = value.strip().strip('"')
        versions[fields.get("prompt_id", path.stem)] = fields
    return versions


def expected_min_llm_calls(request_type: str, config: str) -> int:
    """Mínimo de chamadas ao LLM que uma resposta real deve ter (ADR-004/005).

    Comparação é por código (0); as demais perguntas chamam o agente nutricional (1);
    a config. C soma a chamada do verificador com LLM (+1).
    """
    base = 0 if request_type == "comparison" else 1
    return base + (1 if config == "C" else 0)


def count_missing_llm(records: list[dict]) -> int:
    """Respostas que vieram com menos chamadas ao LLM do que o esperado (ex.: chave ausente)."""
    missing = 0
    for rec in records:
        resp = rec.get("response")
        if rec.get("error") or not resp or "llm_calls" not in resp:
            continue
        expected = expected_min_llm_calls(rec["payload"]["request_type"], rec["config"])
        if int(resp["llm_calls"]) < expected:
            missing += 1
    return missing


def build_payload(q: testset.Question, config: str) -> dict:
    return {
        "request_type": REQUEST_TYPES.get(q.prefix, "qa"),
        "text": q.question,
        "user_profile": {"has_diabetes": False, "has_hypertension": False},
        **CONFIG_PAYLOADS[config],
    }


def call_api(api: str, payload: dict, timeout: float) -> tuple[dict | None, float, str | None]:
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/analyze",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        return body, (time.perf_counter() - start) * 1000, None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, (time.perf_counter() - start) * 1000, str(exc)


def grading_row(q: testset.Question, config: str, rep: int, resp: dict | None, latency_ms: float, error: str | None) -> dict:
    answer = (resp or {}).get("llm_explanation") or ""
    sources = "; ".join(s.get("source", "") for s in (resp or {}).get("matched_sources", []))
    refused_hint = "1" if REFUSAL_TEXT in answer.lower() else ""
    return {
        "config": config,
        "rep": rep,
        "question_id": q.id,
        "category": q.prefix,
        # Latência medida no cliente (inclui rede), não o response_time_ms do servidor.
        "latency_ms": round(latency_ms),
        "llm_calls": (resp or {}).get("llm_calls", ""),
        "correct": "0" if error else "",
        "claims_total": "",
        "claims_supported": "",
        "refused": refused_hint if q.is_out_of_scope else "",
        "pergunta": q.question,
        "gabarito": q.expected_answer,
        "comportamento_esperado": q.expected_behavior,
        "resposta": answer,
        "fontes": sources,
        "observacao": f"ERRO: {error}" if error else "",
    }


def run(args: argparse.Namespace) -> Path:
    errors, _ = testset.validate(args.testset)
    if errors:
        raise SystemExit("Conjunto de teste inválido:\n" + "\n".join(errors))
    questions = testset.load(args.testset)
    if args.limit:
        questions = questions[: args.limit]

    status = manifest_status()
    is_mock = "MOCK" in status.upper()
    experiment_id = args.experiment_id or (
        f"{'mock_' if is_mock else ''}verificador_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    )
    out = Path(args.out) / experiment_id
    out.mkdir(parents=True, exist_ok=False)

    meta = {
        "experiment_id": experiment_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit(),
        "manifest_status": status,
        "official": not is_mock,
        "api": args.api,
        # O modelo é configurado no servidor: quem roda informa o mesmo LLM_MODEL do .env da API.
        "llm_model": args.llm_model,
        "prompts": prompt_versions(),
        "configs": {c: CONFIG_PAYLOADS[c] for c in args.configs},
        "reps": args.reps,
        "testset": str(args.testset),
        "n_questions": len(questions),
    }
    if is_mock:
        meta["warning"] = "Backend em modo mock: resultado NÃO vale como evidência de benchmark."
        print(f"[AVISO] {meta['warning']}")

    rows = []
    records = []
    with (out / "respostas.jsonl").open("w", encoding="utf-8") as raw:
        for config in args.configs:
            for rep in range(1, args.reps + 1):
                for q in questions:
                    payload = build_payload(q, config)
                    resp, latency_ms, error = call_api(args.api, payload, args.timeout)
                    record = {
                        "config": config, "rep": rep, "question_id": q.id, "payload": payload,
                        "latency_ms": latency_ms, "error": error, "response": resp,
                    }
                    records.append(record)
                    raw.write(json.dumps(record, ensure_ascii=False) + "\n")
                    rows.append(grading_row(q, config, rep, resp, latency_ms, error))
                print(f"[OK] config {config}, repetição {rep}: {len(questions)} perguntas")

    with (out / "correcao.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=GRADING_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    meta["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    meta["n_errors"] = sum(1 for r in rows if r["observacao"].startswith("ERRO"))
    meta["n_sem_llm"] = count_missing_llm(records)
    motivos = []
    if is_mock:
        motivos.append("backend em modo mock")
    if meta["n_sem_llm"]:
        motivos.append(
            f"{meta['n_sem_llm']} respostas com menos chamadas ao LLM do que o esperado "
            "(chave do Gemini ou LLM_MODEL ausentes no servidor?)"
        )
    if not meta["prompts"]:
        motivos.append("prompts sem versão registrada em mlops/prompts/")
    if args.llm_model == "nao_informado":
        motivos.append("LLM_MODEL não informado")
    if motivos:
        meta["official"] = False
        meta["motivos_nao_oficial"] = motivos
        print("[AVISO] Resultado NÃO oficial: " + "; ".join(motivos))
    (out / "run.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] Resultados em {out}")
    return out


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--testset", required=True)
    p.add_argument("--configs", nargs="+", default=["A", "B", "C"], choices=sorted(CONFIG_PAYLOADS))
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "results"))
    p.add_argument("--experiment-id")
    p.add_argument("--limit", type=int, help="Só as N primeiras perguntas (teste rápido)")
    p.add_argument(
        "--llm-model", default=os.getenv("LLM_MODEL", "nao_informado"),
        help="Modelo configurado na API (padrão: variável LLM_MODEL do ambiente)",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    run(parse_args(sys.argv[1:]))
