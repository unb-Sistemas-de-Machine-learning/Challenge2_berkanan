"""Compara o LLM principal (Gemini) com um modelo reserva hospedado (issue #22).

Os dois modelos recebem exatamente o mesmo contexto: os trechos que a busca do backend
(`query_knowledge_base`) recupera na base de conhecimento, e o mesmo prompt. Mede tempo de
resposta e gera a planilha de correção no formato de `benchmark.metrics` (acerto, fidelidade).

Use o CONJUNTO DE VALIDAÇÃO, nunca o de teste: escolher o modelo olhando para o teste seria
ajustar o sistema com a prova.

Configuração por variáveis de ambiente (as chaves nunca são impressas nem salvas):
    GEMINI_API_KEY, LLM_MODEL                       modelo principal (Gemini)
    FALLBACK_API_KEY, FALLBACK_BASE_URL, LLM_FALLBACK_MODEL
                                                    reserva com API compatível com OpenAI
                                                    (POST <FALLBACK_BASE_URL>/chat/completions)

Uso (ChromaDB no ar, de dentro de mlops/experiments):
    python -m benchmark.comparar_llm --collection base_conhecimento_v2
    python -m benchmark.metrics results/<experimento>/correcao.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from benchmark import testset
from benchmark.run import GRADING_COLUMNS, git_commit

ROOT = Path(__file__).resolve().parents[3]
EXPERIMENTOS = Path(__file__).resolve().parents[1]
VALIDACAO = EXPERIMENTOS / "testset" / "conjunto_validacao.csv"

# 10 perguntas da validação: Guia, rotulagem, alergênicos e OMS (incluindo texto em inglês).
PERGUNTAS_PADRAO = ["AV02", "AV05", "AV07", "BV01", "BV04", "BV07", "EV03", "FV01", "FV03", "FV04"]

SEM_EVIDENCIA = "Não há evidência suficiente nas fontes consultadas."

PROMPT = """Você é um assistente que ajuda consumidores brasileiros a entender rótulos e alimentação.
Responda em português, de forma clara e curta, usando SOMENTE os trechos oficiais abaixo.
Cite a fonte de cada afirmação entre colchetes, no formato [documento, página].
Não invente números nem informações que não estejam nos trechos.
Se os trechos não forem suficientes para responder, responda exatamente: "{sem_evidencia}"

Trechos oficiais:
{trechos}

Pergunta: {pergunta}
Resposta:"""

Busca = Callable[[str, int], list[dict]]
Modelo = Callable[[str], str]


def montar_prompt(pergunta: str, trechos: list[dict]) -> str:
    blocos = [
        f"[{i}] ({t.get('source_title') or t.get('source')}, página {t.get('page')}) {t.get('text', '').strip()}"
        for i, t in enumerate(trechos, 1)
    ]
    return PROMPT.format(sem_evidencia=SEM_EVIDENCIA, trechos="\n\n".join(blocos) or "(nenhum trecho)", pergunta=pergunta)


def _post_json(url: str, body: dict, headers: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def modelo_gemini(modelo: str, chave: str, timeout: float = 60.0) -> Modelo:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

    def chamar(prompt: str) -> str:
        r = _post_json(url, {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}},
                       {"x-goog-api-key": chave}, timeout)
        partes = r["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in partes).strip()
    return chamar


def modelo_compativel_openai(base_url: str, modelo: str, chave: str, timeout: float = 60.0) -> Modelo:
    url = base_url.rstrip("/") + "/chat/completions"

    def chamar(prompt: str) -> str:
        r = _post_json(url, {"model": modelo, "temperature": 0, "messages": [{"role": "user", "content": prompt}]},
                       {"Authorization": f"Bearer {chave}"}, timeout)
        return (r["choices"][0]["message"]["content"] or "").strip()
    return chamar


def comparar(perguntas: list[testset.Question], busca: Busca, modelos: dict[str, Modelo],
             k: int = 3, reps: int = 1) -> tuple[list[dict], list[dict]]:
    """Devolve (respostas brutas, linhas da planilha de correção)."""
    brutas, linhas = [], []
    for q in perguntas:
        trechos = busca(q.question, k)[:k]
        prompt = montar_prompt(q.question, trechos)
        fontes = "; ".join(f"{t.get('source_title') or t.get('source')} p.{t.get('page')}" for t in trechos)
        for nome, chamar in modelos.items():
            for rep in range(1, reps + 1):
                inicio = time.perf_counter()
                try:
                    resposta, erro = chamar(prompt), None
                except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError) as exc:
                    resposta, erro = "", f"{type(exc).__name__}: {exc}"
                ms = round((time.perf_counter() - inicio) * 1000)
                brutas.append({"modelo": nome, "rep": rep, "question_id": q.id, "latency_ms": ms,
                               "erro": erro, "resposta": resposta, "trechos": fontes})
                linhas.append({
                    "config": nome, "rep": rep, "question_id": q.id, "category": q.prefix, "latency_ms": ms,
                    "llm_calls": 1, "correct": "0" if erro else "", "claims_total": "", "claims_supported": "",
                    "refused": "1" if SEM_EVIDENCIA.lower()[:30] in resposta.lower() else "",
                    "pergunta": q.question, "gabarito": q.expected_answer,
                    "comportamento_esperado": q.expected_behavior, "resposta": resposta, "fontes": fontes,
                    "observacao": f"ERRO: {erro}" if erro else "",
                })
    return brutas, linhas


def _modelos_do_ambiente() -> dict[str, Modelo]:
    modelos: dict[str, Modelo] = {}
    if os.getenv("GEMINI_API_KEY") and os.getenv("LLM_MODEL", "not_configured") != "not_configured":
        modelos[f"gemini:{os.environ['LLM_MODEL']}"] = modelo_gemini(os.environ["LLM_MODEL"], os.environ["GEMINI_API_KEY"])
    if all(os.getenv(v) for v in ("FALLBACK_API_KEY", "FALLBACK_BASE_URL", "LLM_FALLBACK_MODEL")):
        modelos[f"reserva:{os.environ['LLM_FALLBACK_MODEL']}"] = modelo_compativel_openai(
            os.environ["FALLBACK_BASE_URL"], os.environ["LLM_FALLBACK_MODEL"], os.environ["FALLBACK_API_KEY"])
    if not modelos:
        raise SystemExit("Nenhum modelo configurado. Defina GEMINI_API_KEY e LLM_MODEL e/ou "
                         "FALLBACK_API_KEY, FALLBACK_BASE_URL e LLM_FALLBACK_MODEL.")
    return modelos


def _busca_do_backend(colecao: str | None) -> Busca:
    sys.path.insert(0, str(ROOT / "backend"))
    from chroma_client import check_chroma_connection, query_knowledge_base  # noqa: E402

    if not check_chroma_connection().get("connected"):
        raise SystemExit("ChromaDB indisponível: suba o serviço com `docker compose up -d chromadb`.")
    return lambda q, k: query_knowledge_base(q, n_results=k, collection_name=colecao)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--conjunto", default=str(VALIDACAO))
    p.add_argument("--ids", nargs="+", default=PERGUNTAS_PADRAO)
    p.add_argument("--collection", default=None, help="Padrão: CHROMA_COLLECTION do ambiente")
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--out", default=str(EXPERIMENTOS / "results"))
    a = p.parse_args(argv)

    if Path(a.conjunto).name == "conjunto_de_teste.csv":
        print("[AVISO] Você está usando o conjunto de TESTE para escolher modelo. Prefira o de validação.")
    todas = {q.id: q for q in testset.load(a.conjunto)}
    faltando = [i for i in a.ids if i not in todas]
    if faltando:
        raise SystemExit(f"IDs não encontrados em {a.conjunto}: {faltando}")
    modelos = _modelos_do_ambiente()
    brutas, linhas = comparar([todas[i] for i in a.ids], _busca_do_backend(a.collection), modelos, a.k, a.reps)

    out = Path(a.out) / f"comparar_llm_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    out.mkdir(parents=True)
    (out / "respostas.jsonl").write_text("\n".join(json.dumps(b, ensure_ascii=False) for b in brutas) + "\n", encoding="utf-8")
    with (out / "correcao.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=GRADING_COLUMNS)
        w.writeheader()
        w.writerows(linhas)
    (out / "run.json").write_text(json.dumps({
        "data_utc": datetime.now(timezone.utc).isoformat(), "git_commit": git_commit(),
        "conjunto": a.conjunto, "ids": a.ids, "colecao": a.collection or os.getenv("CHROMA_COLLECTION"),
        "k": a.k, "reps": a.reps, "modelos": list(modelos), "erros": sum(1 for b in brutas if b["erro"]),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {len(brutas)} respostas de {len(modelos)} modelo(s) em {out}")
    print("Próximo passo: corrigir correcao.csv (correct, claims_total, claims_supported) e rodar "
          f"python -m benchmark.metrics {out / 'correcao.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
