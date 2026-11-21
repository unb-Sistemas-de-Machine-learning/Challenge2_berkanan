#!/usr/bin/env python3
"""Script versionado de ingestão da Feature Store vetorial ChromaDB (R4).

Indexa as fontes oficiais (`data/fontes_rag/*.json`) na coleção versionada
`base_conhecimento_v2` (ADR-001, ADR-006 e issues #6, #20 e #27):
1. Guia Alimentar para a População Brasileira (MS, 2ª ed., 2014)
2. RDC 429/2020 (ANVISA — extraída do HTML oficial do DOU)
3. IN 75/2020 (ANVISA — extraída do HTML oficial do DOU, com tabela do Anexo XV íntegra)
4. OMS – Guideline: Sugars intake for adults and children (OMS, 2015)
5. OMS – Guideline: Sodium intake for adults and children (OMS, 2012)
6. Diretrizes da Sociedade Brasileira de Diabetes (SBD)
7. RDC 727/2022 (ANVISA — rotulagem de alergênicos e lactose, HTML do DOU)
8. Lei 10.674/2003 (Planalto — rotulagem obrigatória de glúten)

Parâmetros de segmentação e embeddings (base_conhecimento_v2):
- Modelo de embeddings explícito: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (mesmo modelo usado na busca em `backend/chroma_client.py`).
- Trechos de até 500 caracteres com 100 caracteres de sobreposição (compatível com a
  janela de 128 tokens do modelo multilíngue).
- Metadados obrigatórios por trecho:
  `documento`, `fonte_id`, `arquivo`, `pagina`, `versao_indice` (além de `link` e `unidade_citacao`).
"""

from __future__ import annotations

import argparse
import bisect
import json
import logging
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("berkanan.ingest_chroma")

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES_DIR = REPO_ROOT / "data" / "fontes_rag"

for candidate_path in (REPO_ROOT / "backend", Path("/app")):
    if candidate_path.exists() and str(candidate_path) not in sys.path:
        sys.path.insert(0, str(candidate_path))

from chroma_client import (  # noqa: E402
    CHROMA_COLLECTION,
    CHROMA_HOST,
    CHROMA_PORT,
    EMBEDDING_MODEL,
    embed_texts,
)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
BATCH_SIZE = 64

# Fallback determinístico caso o PostgreSQL não esteja acessível durante ingestão offline
FALLBACK_FONTE_IDS: dict[str, int] = {
    "Guia Alimentar para a População Brasileira": 1,
    "RDC 429/2020": 2,
    "IN 75/2020": 3,
    "Diretrizes sobre açúcares e sódio": 5,
    "OMS – Guideline: Sugars intake for adults and children": 5,
    "Diretrizes da Sociedade Brasileira de Diabetes (SBD)": 6,
    "OMS – Guideline: Sodium intake for adults and children": 7,
    "RDC 727/2022": 8,
    "Lei 10.674/2003": 9,
}


@dataclass(frozen=True)
class ChunkRecord:
    """Trecho segmentado pronto para indexação no ChromaDB."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


def resolve_fonte_ids_from_db() -> dict[str, int]:
    """Busca o mapeamento documento -> id em fontes_documentos, com fallback seguro."""
    mapping = dict(FALLBACK_FONTE_IDS)
    try:
        import psycopg2  # type: ignore

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "berkanan_dev"),
            user=os.getenv("POSTGRES_USER", "berkanan_user"),
            password=os.getenv("POSTGRES_PASSWORD", "dev_only_change_me"),
            connect_timeout=3,
        )
        with conn, conn.cursor() as cur:
            cur.execute("SELECT id, documento FROM fontes_documentos;")
            for row_id, doc_name in cur.fetchall():
                mapping[str(doc_name)] = int(row_id)
        conn.close()
        logger.info("Mapeamento fonte_id sincronizado com PostgreSQL (%d fontes).", len(mapping))
    except Exception as exc:
        logger.info("PostgreSQL indisponível (%s); usando fallback canônico de fonte_id.", exc)
    return mapping


def _split_text_window(text: str, chunk_size: int, overlap: int, prefix: str = "") -> list[str]:
    """Segmenta uma string em janelas de `chunk_size` com `overlap`, sem cortar palavras."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    snippets: list[str] = []
    pos = 0
    total_len = len(text)
    while pos < total_len:
        raw_end = min(pos + chunk_size, total_len)
        end = raw_end
        if raw_end < total_len:
            nl_pos = text.rfind("\n", pos + max(overlap + 1, chunk_size - 160), raw_end)
            ws_pos = text.rfind(" ", pos + max(overlap + 1, chunk_size - 120), raw_end)
            split_at = nl_pos if nl_pos > pos + overlap else ws_pos
            if split_at > pos + overlap:
                end = split_at

        snippet = text[pos:end].strip()
        if snippet:
            if prefix and not snippet.startswith("["):
                snippet = f"{prefix} {snippet}"
            snippets.append(snippet)

        if end >= total_len:
            break
        next_pos = max(pos + 1, end - overlap)
        nl_start = text.find("\n", next_pos, end)
        ws_start = text.find(" ", next_pos, end)
        if nl_start != -1 and nl_start + 1 < end:
            pos = nl_start + 1
        elif ws_start != -1 and ws_start + 1 < end:
            pos = ws_start + 1
        else:
            pos = next_pos
    return snippets


def chunk_document_pages(
    pages: list[dict[str, Any]],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    documento: str = "",
) -> list[tuple[int, str]]:
    """Segmenta páginas ou unidades normativas em trechos de `chunk_size` com `overlap`.

    - Se as entradas possuírem `unidade_citacao` (normas extraídas de HTML por artigo/anexo),
      segmenta dentro de cada unidade normativa para nunca misturar artigos ou anexos distintos,
      preservando o cabeçalho `[Documento - Art./Anexo]` nos trechos de continuação.
    - Para documentos paginados contínuos (PDFs), mantém janela deslizante contínua entre páginas.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap deve ser estritamente menor que chunk_size")

    has_normative_units = any("unidade_citacao" in entry for entry in pages)
    if has_normative_units:
        norm_chunks: list[tuple[int, str]] = []
        for entry in pages:
            txt = str(entry.get("texto", "")).strip()
            if not txt:
                continue
            pagina = int(entry["pagina"])
            unidade = str(entry.get("unidade_citacao", f"p.{pagina}"))
            prefix = f"[{documento} - {unidade}]" if documento else f"[{unidade}]"
            for snippet in _split_text_window(txt, chunk_size=chunk_size, overlap=overlap, prefix=prefix):
                norm_chunks.append((pagina, snippet))
        return norm_chunks

    full_parts: list[str] = []
    page_starts: list[int] = []
    page_nums: list[int] = []
    cursor = 0

    for entry in pages:
        txt = str(entry.get("texto", "")).strip()
        if not txt:
            continue
        if full_parts:
            full_parts.append("\n\n")
            cursor += 2
        page_starts.append(cursor)
        page_nums.append(int(entry["pagina"]))
        full_parts.append(txt)
        cursor += len(txt)

    full_text = "".join(full_parts)
    total_len = len(full_text)
    if total_len == 0:
        return []

    chunks: list[tuple[int, str]] = []
    pos = 0
    while pos < total_len:
        raw_end = min(pos + chunk_size, total_len)
        end = raw_end

        if raw_end < total_len:
            ws_pos = full_text.rfind(" ", pos + max(overlap + 1, chunk_size - 120), raw_end)
            nl_pos = full_text.rfind("\n", pos + max(overlap + 1, chunk_size - 120), raw_end)
            split_at = max(ws_pos, nl_pos)
            if split_at > pos + overlap:
                end = split_at

        snippet = full_text[pos:end].strip()
        if snippet:
            p_idx = bisect.bisect_right(page_starts, pos) - 1
            pagina = page_nums[max(0, p_idx)]
            chunks.append((pagina, snippet))

        if end >= total_len:
            break
        pos = max(pos + 1, end - overlap)

    return chunks


def load_chunks_from_sources(
    sources_dir: Path,
    collection_name: str,
    fonte_ids: dict[str, int],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[ChunkRecord]:
    """Lê todos os arquivos JSON de `sources_dir` e produz os ChunkRecords."""
    json_files = sorted(sources_dir.glob("*.json"))
    if not json_files:
        raise FileNotFoundError(f"Nenhum arquivo .json encontrado em {sources_dir}")

    all_records: list[ChunkRecord] = []
    for jf in json_files:
        data = json.loads(jf.read_text(encoding="utf-8"))
        doc_name = str(data["documento"])
        arquivo = str(data["arquivo"])
        link = str(data["link"])
        if doc_name not in fonte_ids:
            raise KeyError(f"fonte_id não encontrado para documento={doc_name!r}")
        fonte_id = fonte_ids[doc_name]

        paginas_raw = data.get("paginas", [])
        unidade_by_page = {
            int(p["pagina"]): str(p.get("unidade_citacao", f"p.{p['pagina']}"))
            for p in paginas_raw
            if "pagina" in p
        }

        page_chunks = chunk_document_pages(
            paginas_raw, chunk_size=chunk_size, overlap=overlap, documento=doc_name
        )
        slug = jf.stem
        for idx, (pagina, text) in enumerate(page_chunks, 1):
            all_records.append(
                ChunkRecord(
                    chunk_id=f"{slug}_p{pagina:03d}_c{idx:04d}",
                    text=text,
                    metadata={
                        "documento": doc_name,
                        "fonte_id": fonte_id,
                        "arquivo": arquivo,
                        "pagina": pagina,
                        "unidade_citacao": unidade_by_page.get(pagina, f"p.{pagina}"),
                        "versao_indice": collection_name,
                        "link": link,
                    },
                )
            )
        logger.info(
            "Fonte %-55s | arquivo=%-42s | trechos=%d",
            doc_name,
            arquivo,
            len(page_chunks),
        )

    return all_records


def _get_or_create_collection(
    client: Any, collection_name: str, host: str, port: int, recreate: bool
) -> Any:
    if recreate:
        try:
            client.delete_collection(name=collection_name)
            logger.info("Coleção anterior '%s' removida para reindexação limpa.", collection_name)
        except Exception:
            pass

    try:
        return client.get_collection(name=collection_name)
    except Exception:
        try:
            return client.create_collection(
                name=collection_name,
                metadata={
                    "hnsw:space": "cosine",
                    "embedding_model": EMBEDDING_MODEL,
                    "description": "Feature Store Vetorial - Fontes Oficiais (500 chars, overlap 100)",
                },
            )
        except Exception:
            url = f"http://{host}:{port}/api/v1/collections"
            req = urllib.request.Request(
                url,
                data=json.dumps(
                    {
                        "name": collection_name,
                        "metadata": {
                            "hnsw:space": "cosine",
                            "embedding_model": EMBEDDING_MODEL,
                            "description": "Feature Store Vetorial",
                        },
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=5)
            return client.get_collection(name=collection_name)


def ingest(
    collection_name: str = CHROMA_COLLECTION,
    host: str = CHROMA_HOST,
    port: int = CHROMA_PORT,
    sources_dir: Path = DEFAULT_SOURCES_DIR,
    recreate: bool = False,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> int:
    """Executa a segmentação e indexação das fontes oficiais no ChromaDB."""
    fonte_ids = resolve_fonte_ids_from_db()
    records = load_chunks_from_sources(
        sources_dir=sources_dir,
        collection_name=collection_name,
        fonte_ids=fonte_ids,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    logger.info(
        "Conectando ao ChromaDB em %s:%d (coleção: %s, modelo: %s, total de trechos: %d)...",
        host,
        port,
        collection_name,
        EMBEDDING_MODEL,
        len(records),
    )

    try:
        import chromadb

        client = chromadb.HttpClient(host=host, port=port)
    except Exception as exc:
        logger.error("Não foi possível conectar via cliente ChromaDB nativo: %s", exc)
        return 1

    try:
        col = _get_or_create_collection(client, collection_name, host, port, recreate=recreate)
        for i in range(0, len(records), BATCH_SIZE):
            batch = records[i : i + BATCH_SIZE]
            docs = [r.text for r in batch]
            vecs = embed_texts(docs, is_query=False)
            if vecs:
                col.upsert(
                    ids=[r.chunk_id for r in batch],
                    documents=docs,
                    embeddings=vecs,
                    metadatas=[r.metadata for r in batch],
                )
            else:
                col.upsert(
                    ids=[r.chunk_id for r in batch],
                    documents=docs,
                    metadatas=[r.metadata for r in batch],
                )
        total_in_col = col.count()
        logger.info(
            "✓ Sucesso: %d trechos indexados (total na coleção '%s': %d).",
            len(records),
            collection_name,
            total_in_col,
        )
        return 0
    except Exception as exc:
        logger.error("Falha durante indexação no ChromaDB: %s", exc)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão de fontes oficiais no ChromaDB (R4)")
    parser.add_argument("--host", default=CHROMA_HOST, help="Host do ChromaDB")
    parser.add_argument("--port", type=int, default=CHROMA_PORT, help="Porta do ChromaDB")
    parser.add_argument("--collection", default=CHROMA_COLLECTION, help="Nome da coleção versionada")
    parser.add_argument(
        "--sources-dir",
        type=Path,
        default=DEFAULT_SOURCES_DIR,
        help="Diretório com os JSONs de páginas/unidades extraídas das fontes",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recria a coleção antes da ingestão (remove trechos antigos/mockados)",
    )
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="Tamanho máximo do trecho")
    parser.add_argument("--overlap", type=int, default=CHUNK_OVERLAP, help="Sobreposição entre trechos")
    args = parser.parse_args()

    sys.exit(
        ingest(
            collection_name=args.collection,
            host=args.host,
            port=args.port,
            sources_dir=args.sources_dir,
            recreate=args.recreate,
            chunk_size=args.chunk_size,
            overlap=args.overlap,
        )
    )
