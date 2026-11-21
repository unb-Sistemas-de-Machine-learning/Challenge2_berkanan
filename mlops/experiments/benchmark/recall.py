"""Recall da recuperação (top k) do RAG — métrica 3 da seção 9 (meta ≥ 80% no top 3).

Para cada pergunta do conjunto de teste que depende de uma fonte indexada, consulta o ChromaDB
com a MESMA função do backend (`backend/chroma_client.query_knowledge_base`) e verifica se algum
dos k primeiros trechos é do documento esperado E contém um dos trechos-chave do gabarito
(`testset/recall_gabarito.csv`). O critério usa texto literal, e não a página, para continuar
valendo se o tamanho do trecho ou a unidade de citação mudarem.

Uso:
    python -m benchmark.recall --testset testset/conjunto_de_teste.csv --k 3 \
        --collection base_conhecimento_v1
    python -m benchmark.recall --validar    # só confere o gabarito contra data/fontes_rag
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from benchmark import testset

ROOT = Path(__file__).resolve().parents[3]
GABARITO = Path(__file__).resolve().parents[1] / "testset" / "recall_gabarito.csv"
FONTES = ROOT / "data" / "fontes_rag"
TARGET_PCT = 80.0

SearchFn = Callable[[str, int], list[dict]]


def norm(text: str) -> str:
    """Minúsculas, sem acento, aspas retas e espaços colapsados."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.replace("“", '"').replace("”", '"').replace("’", "'")
    return re.sub(r"\s+", " ", t).strip().lower()


def load_gabarito(path: str | Path = GABARITO) -> dict[str, list[dict]]:
    """ID -> lista de alternativas {documentos, trechos}. Basta uma alternativa bater."""
    gab: dict[str, list[dict]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            gab.setdefault(r["ID"].strip(), []).append({
                "documentos": [d.strip() for d in r["documento_esperado"].split(";") if d.strip()],
                "trechos": [t.strip() for t in r["trechos_chave"].split("||") if t.strip()],
                "pagina_referencia": r.get("pagina_referencia", ""),
                "observacao": r.get("observacao", ""),
            })
    return gab


def matches(result: dict, alt: dict) -> bool:
    doc = norm(result.get("source_title") or result.get("documento") or "")
    if doc not in {norm(d) for d in alt["documentos"]}:
        return False
    text = norm(result.get("text", ""))
    return any(norm(t) in text for t in alt["trechos"])


def evaluate(questions: list[testset.Question], gabarito: dict[str, list[dict]], search: SearchFn, k: int = 3) -> dict:
    rows = []
    for q in questions:
        if q.id not in gabarito:
            continue
        try:
            results = search(q.question, k)[:k]
            error = None
        except Exception as exc:  # erro de conexão não pode virar "não recuperou"
            results, error = [], str(exc)
        hit_rank = next((i for i, r in enumerate(results, 1) if any(matches(r, a) for a in gabarito[q.id])), None)
        rows.append({
            "id": q.id,
            "categoria": q.prefix,
            "acertou": hit_rank is not None,
            "posicao": hit_rank,
            "erro": error,
            "esperado": [{"documentos": a["documentos"], "trechos": a["trechos"]} for a in gabarito[q.id]],
            "recuperados": [
                {"posicao": i, "documento": r.get("source_title"), "pagina": r.get("page"),
                 "similaridade": r.get("similarity"), "trecho": r.get("text", "")}
                for i, r in enumerate(results, 1)
            ],
        })

    if any(r["erro"] for r in rows):
        raise RuntimeError("Falha ao consultar o ChromaDB: " + next(r["erro"] for r in rows if r["erro"]))

    def pct(items):
        return round(100 * sum(r["acertou"] for r in items) / len(items), 2) if items else None

    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["categoria"], []).append(r)
    total = pct(rows)
    return {
        "k": k,
        "n_perguntas": len(rows),
        "recall_pct": total,
        "meta_pct": TARGET_PCT,
        "atinge_meta": None if total is None else total >= TARGET_PCT,
        "recall_por_categoria_pct": {c: pct(v) for c, v in sorted(by_cat.items())},
        "perdidas": [r["id"] for r in rows if not r["acertou"]],
        "perguntas": rows,
    }


def validate_gabarito(gabarito: dict[str, list[dict]], fontes_dir: Path = FONTES) -> list[str]:
    """Avisos: documento fora da base ou trecho-chave inexistente no texto indexado."""
    textos: dict[str, str] = {}
    for f in sorted(Path(fontes_dir).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        textos[norm(d["documento"])] = norm(" ".join(p.get("texto", "") for p in d.get("paginas", [])))
    avisos = []
    for qid, alts in gabarito.items():
        ok_alguma = False
        for a in alts:
            presentes = [d for d in a["documentos"] if norm(d) in textos]
            if not presentes:
                avisos.append(f"{qid}: fonte fora da base ({'; '.join(a['documentos'])})")
                continue
            achados = [t for t in a["trechos"] if any(norm(t) in textos[norm(d)] for d in presentes)]
            if achados:
                ok_alguma = True
            else:
                avisos.append(f"{qid}: nenhum trecho-chave encontrado em {presentes[0]}")
        if not ok_alguma:
            avisos.append(f"{qid}: NÃO PODE SER RECUPERADA com a base atual")
    return avisos


def _backend_search(collection: str | None) -> SearchFn:
    sys.path.insert(0, str(ROOT / "backend"))
    from chroma_client import check_chroma_connection, query_knowledge_base  # noqa: E402

    status = check_chroma_connection()
    if not status.get("connected"):
        raise SystemExit(f"ChromaDB indisponível: {status}")
    return lambda q, k: query_knowledge_base(q, n_results=k, collection_name=collection)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--testset", default=str(Path(__file__).resolve().parents[1] / "testset" / "conjunto_de_teste.csv"))
    p.add_argument("--gabarito", default=str(GABARITO))
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--collection", default=None, help="Padrão: CHROMA_COLLECTION do ambiente")
    p.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "results"))
    p.add_argument("--validar", action="store_true", help="Só confere o gabarito contra data/fontes_rag")
    a = p.parse_args(argv)

    gab = load_gabarito(a.gabarito)
    avisos = validate_gabarito(gab)
    for av in avisos:
        print(f"[AVISO] {av}")
    if a.validar:
        print(f"[OK] Gabarito com {len(gab)} perguntas conferido contra {FONTES}.")
        return 0

    report = evaluate(testset.load(a.testset), gab, _backend_search(a.collection), a.k)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "desconhecido"
    report["execucao"] = {
        "data_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": commit,
        "colecao": a.collection or "CHROMA_COLLECTION do ambiente",
        "avisos_gabarito": avisos,
    }
    out = Path(a.out) / f"recall_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    out.mkdir(parents=True)
    (out / "recall.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Recall@{a.k}: {report['recall_pct']}% (meta {TARGET_PCT}%) em {report['n_perguntas']} perguntas")
    print(f"Por categoria: {report['recall_por_categoria_pct']}")
    print(f"Perdidas: {', '.join(report['perdidas']) or 'nenhuma'}")
    print(f"[OK] Detalhes em {out / 'recall.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
