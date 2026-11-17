"""Módulo de integração com a Feature Store vetorial ChromaDB (ADR-001 e ADR-006).

Gerencia a conexão com o servidor ChromaDB, criação e versionamento de coleções
(ex.: base_conhecimento_v1), indexação de trechos das 5 fontes oficiais com metadados
obrigatórios (documento, fonte_id, arquivo, pagina, versao_indice) e recuperação
semântica (RAG) para fundamentar as respostas dos agentes.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("berkanan.chroma")

CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "base_conhecimento_v1")
BASE_URL = f"http://{CHROMA_HOST}:{CHROMA_PORT}"


def _http_request(
    path: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 3.0
) -> dict[str, Any] | list[Any] | None:
    """Realiza requisições HTTP REST diretamente para a API do ChromaDB."""
    url = f"{BASE_URL}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.debug("Falha na chamada HTTP ao ChromaDB (%s %s): %s", method, url, exc)
        return None


def get_chroma_client() -> Any | None:
    """Tenta instanciar o cliente oficial chromadb.HttpClient se disponível."""
    try:
        import chromadb

        return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    except Exception as exc:
        logger.debug("Cliente nativo chromadb não instanciado: %s", exc)
        return None


def check_chroma_connection() -> dict[str, Any]:
    """Verifica a saúde do serviço ChromaDB e lista coleções disponíveis."""
    # 1. Tenta via cliente oficial se instalado
    client = get_chroma_client()
    if client is not None:
        try:
            client.heartbeat()
            collections = [col.name for col in client.list_collections()]
            return {
                "status": "connected",
                "client": "chromadb_native",
                "host": CHROMA_HOST,
                "port": CHROMA_PORT,
                "collections": collections,
                "active_collection": CHROMA_COLLECTION,
                "connected": True,
            }
        except Exception as exc:
            logger.debug("Erro com cliente nativo: %s", exc)

    # 2. Fallback via REST API do ChromaDB
    heartbeat_v2 = _http_request("/api/v2/heartbeat")
    heartbeat_v1 = _http_request("/api/v1/heartbeat") if heartbeat_v2 is None else heartbeat_v2

    if heartbeat_v1 is None:
        return {
            "status": "unreachable",
            "message": f"Serviço ChromaDB inacessível em {BASE_URL}",
            "connected": False,
        }

    cols = _http_request("/api/v1/collections")
    col_names: list[str] = []
    if isinstance(cols, list):
        col_names = [c.get("name") for c in cols if isinstance(c, dict) and "name" in c]

    return {
        "status": "connected",
        "client": "chroma_rest_fallback",
        "host": CHROMA_HOST,
        "port": CHROMA_PORT,
        "heartbeat": heartbeat_v1,
        "collections": col_names,
        "active_collection": CHROMA_COLLECTION,
        "connected": True,
    }


def _get_or_create_collection_safe(client: Any, col_name: str) -> Any:
    try:
        return client.get_collection(name=col_name)
    except Exception:
        _http_request(
            "/api/v1/collections",
            method="POST",
            payload={"name": col_name, "metadata": {"description": "Feature Store Vetorial"}},
        )
        return client.get_collection(name=col_name)


def query_knowledge_base(
    query: str,
    n_results: int = 3,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta trechos textuais semanticamente relevantes na coleção do ChromaDB (RAG).

    Retorna trechos com citações obrigatórias:
    (documento, fonte_id, arquivo, pagina, versao_indice).
    """
    col_name = collection_name or CHROMA_COLLECTION
    client = get_chroma_client()

    if client is not None:
        try:
            col = _get_or_create_collection_safe(client, col_name)
            res = col.query(query_texts=[query], n_results=n_results)
            documents = res.get("documents", [[]])[0]
            metadatas = res.get("metadatas", [[]])[0]
            distances = res.get("distances", [[]])[0]

            results = []
            for i, doc in enumerate(documents):
                meta = metadatas[i] if i < len(metadatas) else {}
                dist = distances[i] if i < len(distances) else 0.0
                similarity = round(max(0.0, 1.0 - float(dist)), 3)
                results.append(
                    {
                        "text": doc,
                        "source": meta.get("arquivo", meta.get("documento", "documento_oficial")),
                        "similarity": similarity,
                        "source_title": meta.get("documento", "Norma Oficial"),
                        "source_url": meta.get("link", "https://www.gov.br/anvisa"),
                        "page": meta.get("pagina"),
                        "fonte_id": meta.get("fonte_id"),
                        "versao_indice": meta.get("versao_indice", "base_conhecimento_v1"),
                    }
                )
            return results
        except Exception as exc:
            logger.warning("Falha ao consultar coleção vetorial nativa: %s", exc)

    return []


def index_documents(
    documents: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str],
    collection_name: str | None = None,
) -> bool:
    """Indexa lotes de documentos com metadados obrigatórios no ChromaDB."""
    col_name = collection_name or CHROMA_COLLECTION
    client = get_chroma_client()

    if client is not None:
        try:
            col = _get_or_create_collection_safe(client, col_name)
            col.upsert(documents=documents, metadatas=metadatas, ids=ids)
            logger.info("Indexados %d documentos na coleção %s", len(documents), col_name)
            return True
        except Exception as exc:
            logger.error("Erro ao indexar no ChromaDB nativo: %s", exc)

    return False

