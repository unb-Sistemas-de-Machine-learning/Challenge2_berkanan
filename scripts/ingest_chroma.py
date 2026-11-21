#!/usr/bin/env python3
"""Script versionado de ingestão da Feature Store vetorial ChromaDB (R4).

Indexa as fontes oficiais em JSON extraído por página (`data/fontes_rag/*.json`)
na coleção versionada `base_conhecimento_v1` (ADR-001 e ADR-006):
1. Guia Alimentar para a População Brasileira (MS, 2ª ed., 2014)
2. RDC 429/2020 (ANVISA)
3. IN 75/2020 (ANVISA)
4. OMS – Guideline: Sugars intake for adults and children (OMS, 2015)
5. OMS – Guideline: Sodium intake for adults and children (OMS, 2012)
6. Diretrizes da Sociedade Brasileira de Diabetes (SBD)

Parâmetros de segmentação (CLAUDE.md Seção 6.2):
- Trechos de até 1000 caracteres com 150 caracteres de sobreposição.
- Metadados obrigatórios por trecho:
  `documento`, `fonte_id`, `arquivo`, `pagina`, `versao_indice` (além de `link`).
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

CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "base_conhecimento_v1")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150
BATCH_SIZE = 64

# Fallback determinístico caso o PostgreSQL não esteja acessível durante ingestão offline
FALLBACK_FONTE_IDS: dict[str, int] = {
    "Guia Alimentar para a População Brasileira": 1,
    "RDC 429/2020": 2,
    "IN 75/2020": 3,
    "OMS – Guideline: Sugars intake for adults and children": 5,
    "Diretrizes da Sociedade Brasileira de Diabetes (SBD)": 6,
    "OMS – Guideline: Sodium intake for adults and children": 7,
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


def chunk_document_pages(
    pages: list[dict[str, Any]],
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[tuple[int, str]]:
    """Segmenta páginas contínuas em trechos de `chunk_size` com `overlap` caracteres.

    Retorna lista de `(pagina_inicial, texto_trecho)` rastreando a página exata onde
    cada trecho se inicia.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap deve ser estritamente menor que chunk_size")

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

        # Evita cortar palavras ao meio quando não é o último trecho
        if raw_end < total_len:
            ws_pos = full_text.rfind(" ", pos + chunk_size - 120, raw_end)
            nl_pos = full_text.rfind("\n", pos + chunk_size - 120, raw_end)
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

        page_chunks = chunk_document_pages(
            data.get("paginas", []), chunk_size=chunk_size, overlap=overlap
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
                        "versao_indice": collection_name,
                        "link": link,
                    },
                )
            )
        logger.info(
            "Fonte %-48s | arquivo=%-42s | trechos=%d",
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
                    "description": "Feature Store Vetorial - Fontes Oficiais (1000 chars, overlap 150)",
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
        "Conectando ao ChromaDB em %s:%d (coleção: %s, total de trechos: %d)...",
        host,
        port,
        collection_name,
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
            col.upsert(
                ids=[r.chunk_id for r in batch],
                documents=[r.text for r in batch],
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
        help="Diretório com os JSONs de páginas extraídas das fontes",
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
