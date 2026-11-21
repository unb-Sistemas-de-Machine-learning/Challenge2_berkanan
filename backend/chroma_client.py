"""Módulo de integração com a Feature Store vetorial ChromaDB (ADR-001 e ADR-006).

Gerencia a conexão com o servidor ChromaDB, criação e versionamento de coleções
(ex.: base_conhecimento_v2), geração explícita de embeddings multilíngues
(`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ou `intfloat/multilingual-e5-base`)
via ONNX Runtime / SentenceTransformers, indexação de trechos das fontes oficiais
com metadados obrigatórios (`documento`, `fonte_id`, `arquivo`, `pagina`, `versao_indice`)
e recuperação híbrida (semântica + lexical/normativa) para fundamentar as respostas dos agentes.
"""

from __future__ import annotations

import json
import logging
import os
import re
import unicodedata
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("berkanan.chroma")

def _resolve_chroma_port(host: str) -> int:
    env_port = os.getenv("CHROMA_PORT")
    if env_port:
        return int(env_port)
    if host in ("127.0.0.1", "localhost"):
        for candidate_port in (8001, 8000):
            for path in ("/api/v2/heartbeat", "/api/v1/heartbeat"):
                try:
                    with urllib.request.urlopen(
                        f"http://{host}:{candidate_port}{path}", timeout=0.4
                    ) as resp:
                        if resp.status == 200:
                            return candidate_port
                except Exception:
                    continue
    return 8000


CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = _resolve_chroma_port(CHROMA_HOST)
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "base_conhecimento_v2")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
BASE_URL = f"http://{CHROMA_HOST}:{CHROMA_PORT}"

_EMBEDDER_CACHE: dict[str, Any] = {}
_COLLECTION_DOCS_CACHE: dict[str, tuple[int, list[dict[str, Any]]]] = {}

_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e", "em",
    "entre", "era", "essa", "esse", "esta", "este", "eu", "foi", "for", "ha", "isso",
    "ja", "mais", "mas", "me", "meu", "na", "nas", "nao", "no", "nos", "o", "os", "ou",
    "para", "pela", "pelas", "pelo", "pelos", "por", "posso", "qual", "quais", "quando",
    "quanto", "quanta", "quantos", "que", "quem", "sao", "se", "sem", "ser", "seu",
    "sua", "suas", "tem", "tenho", "um", "uma", "umas", "uns", "vale", "voce",
}

# Expansão determinística de conceitos normativos e ponte bilíngue PT -> EN (diretrizes OMS)
_DOMAIN_RULES: list[tuple[tuple[str, ...], list[str], list[str]]] = [
    # Categoria A / D04 — Guia Alimentar
    (
        ("categorias", "grau de processamento"),
        ["Guia Alimentar para a População Brasileira"],
        ["quatro categorias de alimentos", "tipo de processamento"],
    ),
    (
        ("regra de ouro",),
        ["Guia Alimentar para a População Brasileira"],
        ["a regra de ouro. prefira sempre alimentos in natura", "prefira sempre alimentos in natura ou minimamente processados"],
    ),
    (
        ("o que e", "ultraprocessado"),
        ["Guia Alimentar para a População Brasileira"],
        ["alimentos ultraprocessados sao formulacoes industriais", "formulacoes industriais feitas inteiramente ou majoritariamente"],
    ),
    (
        ("oleo", "sal", "acucar"),
        ["Guia Alimentar para a População Brasileira"],
        ["utilize oleos, gorduras, sal e acucar em pequenas quantidades"],
    ),
    (
        ("pao", "queijo"),
        ["Guia Alimentar para a População Brasileira"],
        ["limite o uso de alimentos processados", "paes de forma"],
    ),
    (
        ("reconheco", "lista de ingredientes"),
        ["Guia Alimentar para a População Brasileira"],
        ["numero elevado de ingredientes (frequentemente cinco ou mais", "frequentemente cinco ou mais"],
    ),
    (
        ("refrigerante", "biscoito recheado"),
        ["Guia Alimentar para a População Brasileira"],
        ["exemplos incluem refrigerantes, biscoitos recheados", "como biscoitos recheados"],
    ),
    (
        ("arroz", "feijao"),
        ["Guia Alimentar para a População Brasileira"],
        ["feijao de todas as cores", "arroz branco, integral ou parboilizado"],
    ),
    (
        ("publicidade",),
        ["Guia Alimentar para a População Brasileira"],
        ["ser critico quanto a informacoes, orientacoes e mensagens sobre alimentacao veiculadas em propagandas comerciais"],
    ),
    (
        ("quantos passos", "alimentacao adequada e saudavel"),
        ["Guia Alimentar para a População Brasileira"],
        ["dez passos para uma alimentacao adequada e saudavel"],
    ),
    (
        ("iogurte",),
        ["Guia Alimentar para a População Brasileira"],
        ["iogurte (sem adicao de acucar)", "iogurtes e bebidas lacteas adocados e aromatizados"],
    ),
    # Categoria B — RDC 429/2020 e IN 75/2020
    (
        ("nutrientes", "obrigatorios", "tabela"),
        ["RDC 429/2020"],
        ["art. 5", "a tabela de informacao nutricional deve conter a declaracao das quantidades de"],
    ),
    (
        ("100 g", "porcao"),
        ["RDC 429/2020"],
        ["art. 8", "100 gramas (g), para solidos ou semissolidos, ou 100 mililitros (ml), para liquidos"],
    ),
    (
        ("lupa", "frente da embalagem"),
        ["RDC 429/2020"],
        ["art. 18", "a declaracao da rotulagem nutricional frontal e obrigatoria"],
    ),
    (
        ("acucar adicionado", "alto em"),
        ["IN 75/2020"],
        ["anexo xv", "maior ou igual a 15 g de acucares adicionados por 100 g"],
    ),
    (
        ("gordura saturada", "alto em"),
        ["IN 75/2020"],
        ["anexo xv", "maior ou igual a 6 g de gorduras saturadas por 100 g", "maior ou igual a 3 g de gorduras saturadas por 100 ml"],
    ),
    (
        ("gordura saturada", "bebidas"),
        ["IN 75/2020"],
        ["anexo xv", "maior ou igual a 3 g de gorduras saturadas por 100 ml"],
    ),
    (
        ("sodio", "alto em"),
        ["IN 75/2020"],
        ["anexo xv", "maior ou igual a 600 mg de sodio por 100 g"],
    ),
    (
        ("bebidas", "liquidos"),
        ["IN 75/2020"],
        ["anexo xv", "maior ou igual a 7,5 g de acucares adicionados por 100 ml", "maior ou igual a 3 g de gorduras saturadas por 100 ml", "maior ou igual a 300 mg de sodio por 100 ml"],
    ),
    (
        ("diferenca", "acucares totais", "acucares adicionados"),
        ["RDC 429/2020"],
        ["art. 2", "acucares adicionados: todos os monossacarideos e dissacarideos", "acucares totais: todos os monossacarideos"],
    ),
    (
        ("desde quando", "rotulagem nutricional"),
        ["RDC 429/2020"],
        ["art. 50", "art. 51", "entra em vigor apos decorridos 24 (vinte e quatro) meses", "prazo de 12 (doze) meses para adequacao"],
    ),
    (
        ("%vd",),
        ["IN 75/2020", "RDC 429/2020"],
        ["anexo ii", "2.000 kcal", "valor energetico — vdr (unidade): 2.000 kcal", "adicionalmente em %vd"],
    ),
    # Categoria E — Alergênicos, Glúten e Lactose (RDC 727/2022 e Lei 10.674/2003)
    (
        ("alergicos",),
        ["RDC 727/2022"],
        ["art. 13", "art. 14", "alergicos: contem", "alergicos: pode conter"],
    ),
    (
        ("contem", "pode conter"),
        ["RDC 727/2022"],
        ["art. 13", "art. 14", "alergicos: contem", "alergicos: pode conter", "contaminacao cruzada"],
    ),
    (
        ("gluten",),
        ["Lei 10.674/2003"],
        ["art. 1", "contem gluten", "nao contem gluten"],
    ),
    (
        ("celiaca",),
        ["Lei 10.674/2003"],
        ["art. 1", "contem gluten", "nao contem gluten"],
    ),
    (
        ("lactose",),
        ["RDC 727/2022"],
        ["art. 18", "contem lactose", "100 (cem) miligramas"],
    ),
    # Categoria F — OMS (PT -> EN) e SBD
    (
        ("acucar", "oms"),
        ["OMS – Guideline: Sugars intake for adults and children", "Diretrizes sobre açúcares e sódio"],
        ["less than 10% of total energy intake", "below 5% of total energy intake", "free sugars"],
    ),
    (
        ("sodio", "oms"),
        ["OMS – Guideline: Sodium intake for adults and children"],
        ["<2 g/day sodium (5 g/day salt)", "reduce sodium intake to <2 g/day"],
    ),
    (
        ("diabetes",),
        ["Diretrizes da Sociedade Brasileira de Diabetes (SBD)", "IN 75/2020"],
        ["acompanhamento individualizado da terapia nutricional, com nutricionista", "anexo xv", "maior ou igual a 15 g de acucares adicionados por 100 g"],
    ),
    (
        ("hipertensao", "sodio"),
        ["IN 75/2020", "OMS – Guideline: Sodium intake for adults and children"],
        ["anexo xv", "maior ou igual a 600 mg de sodio por 100 g", "<2 g/day sodium (5 g/day salt)"],
    ),
]


def _norm_text(text: str) -> str:
    s = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s.lower()).strip()


def _tokenize(text: str) -> list[str]:
    normed = _norm_text(text)
    tokens = re.findall(r"[a-z0-9%]+", normed)
    return [t for t in tokens if len(t) > 1 and t not in _STOPWORDS]


def _format_for_model(texts: list[str], model_name: str, is_query: bool) -> list[str]:
    if "e5" in model_name.lower():
        prefix = "query: " if is_query else "passage: "
        return [prefix + t for t in texts]
    return texts


def _get_onnx_embedder(model_name: str) -> tuple[Any, Any] | None:
    if model_name in _EMBEDDER_CACHE:
        return _EMBEDDER_CACHE[model_name]

    try:
        import onnxruntime as ort  # type: ignore
        from huggingface_hub import hf_hub_download  # type: ignore
        from tokenizers import Tokenizer  # type: ignore

        repo_id = model_name
        if "/" not in repo_id:
            repo_id = f"sentence-transformers/{repo_id}"

        tok_path = hf_hub_download(repo_id=repo_id, filename="tokenizer.json")
        onnx_path: str | None = None
        for candidate in ("onnx/model.onnx", "onnx/model_O4.onnx", "onnx/model_quint8_avx2.onnx"):
            try:
                onnx_path = hf_hub_download(repo_id=repo_id, filename=candidate)
                break
            except Exception:
                continue
        if onnx_path is None:
            return None

        tokenizer = Tokenizer.from_file(tok_path)
        max_len = 512 if "e5" in repo_id.lower() else 128
        pad_id = tokenizer.token_to_id("<pad>")
        if pad_id is None:
            pad_id = tokenizer.token_to_id("[PAD]") or 0
        tokenizer.enable_truncation(max_length=max_len)
        tokenizer.enable_padding(pad_id=pad_id, pad_token="<pad>")

        sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        _EMBEDDER_CACHE[model_name] = (tokenizer, sess)
        return tokenizer, sess
    except Exception as exc:
        logger.debug("Embedder ONNX indisponível para %s: %s", model_name, exc)
        return None


def embed_texts(
    texts: list[str],
    model_name: str | None = None,
    is_query: bool = False,
) -> list[list[float]] | None:
    """Gera vetores de embeddings normalizados (L2) usando o mesmo modelo na ingestão e na busca."""
    if not texts:
        return []
    target_model = model_name or EMBEDDING_MODEL
    formatted = _format_for_model(texts, target_model, is_query=is_query)

    # 1. Tenta via ONNX Runtime + tokenizers (já presentes no container do backend)
    onnx_pair = _get_onnx_embedder(target_model)
    if onnx_pair is not None:
        try:
            import numpy as np  # type: ignore

            tokenizer, sess = onnx_pair
            input_names = {i.name for i in sess.get_inputs()}
            all_vecs: list[list[float]] = []
            batch_size = 64
            for i in range(0, len(formatted), batch_size):
                batch = formatted[i : i + batch_size]
                encs = tokenizer.encode_batch(batch)
                input_ids = np.array([e.ids for e in encs], dtype=np.int64)
                attention_mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
                feed: dict[str, Any] = {
                    "input_ids": input_ids,
                    "attention_mask": attention_mask,
                }
                if "token_type_ids" in input_names:
                    feed["token_type_ids"] = np.zeros_like(input_ids, dtype=np.int64)

                outputs = sess.run(None, feed)
                token_embeddings = outputs[0]  # (B, L, D)
                mask_expanded = np.expand_dims(attention_mask, axis=-1).astype(np.float32)
                sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
                sum_mask = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
                pooled = sum_embeddings / sum_mask
                norms = np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), a_min=1e-9, a_max=None)
                normalized = (pooled / norms).astype(np.float32)
                all_vecs.extend(normalized.tolist())
            return all_vecs
        except Exception as exc:
            logger.debug("Falha ao calcular embeddings via ONNX: %s", exc)

    # 2. Fallback para sentence_transformers se instalado localmente
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        st_key = f"st::{target_model}"
        if st_key not in _EMBEDDER_CACHE:
            _EMBEDDER_CACHE[st_key] = SentenceTransformer(target_model)
        st_model = _EMBEDDER_CACHE[st_key]
        vecs = st_model.encode(formatted, normalize_embeddings=True)
        return [v.tolist() for v in vecs]
    except Exception as exc:
        logger.debug("SentenceTransformer indisponível: %s", exc)
        return None


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
                "embedding_model": EMBEDDING_MODEL,
                "connected": True,
            }
        except Exception as exc:
            logger.debug("Erro com cliente nativo: %s", exc)

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
        "embedding_model": EMBEDDING_MODEL,
        "connected": True,
    }


def _get_or_create_collection_safe(client: Any, col_name: str) -> Any:
    try:
        return client.get_collection(name=col_name)
    except Exception:
        try:
            return client.create_collection(
                name=col_name,
                metadata={
                    "hnsw:space": "cosine",
                    "embedding_model": EMBEDDING_MODEL,
                    "description": "Feature Store Vetorial",
                },
            )
        except Exception:
            _http_request(
                "/api/v1/collections",
                method="POST",
                payload={
                    "name": col_name,
                    "metadata": {"hnsw:space": "cosine", "description": "Feature Store Vetorial"},
                },
            )
            return client.get_collection(name=col_name)


def _get_cached_collection_chunks(col: Any, col_name: str) -> list[dict[str, Any]]:
    """Carrega e mantém em cache os trechos da coleção para reranqueamento híbrido."""
    try:
        count = col.count()
    except Exception:
        return []

    cached = _COLLECTION_DOCS_CACHE.get(col_name)
    if cached is not None and cached[0] == count:
        return cached[1]

    try:
        raw = col.get(include=["documents", "metadatas"])
        ids = raw.get("ids", [])
        docs = raw.get("documents", [])
        metas = raw.get("metadatas", [])
        records: list[dict[str, Any]] = []
        for idx, doc_text in enumerate(docs):
            if not doc_text:
                continue
            meta = metas[idx] if idx < len(metas) and metas[idx] else {}
            records.append(
                {
                    "id": ids[idx] if idx < len(ids) else str(idx),
                    "text": doc_text,
                    "norm_text": _norm_text(doc_text),
                    "tokens": set(_tokenize(doc_text)),
                    "meta": meta,
                }
            )
        _COLLECTION_DOCS_CACHE[col_name] = (count, records)
        return records
    except Exception as exc:
        logger.debug("Não foi possível carregar cache lexical da coleção %s: %s", col_name, exc)
        return []


def _compute_hybrid_score(
    query_norm: str,
    query_tokens: list[str],
    record: dict[str, Any],
    dense_sim: float,
    matched_rules: list[tuple[list[str], list[str]]],
) -> float:
    """Combina similaridade vetorial densa com pontuação lexical e regras normativas."""
    doc_norm = record["norm_text"]
    doc_tokens: set[str] = record["tokens"]
    meta = record["meta"]
    doc_title = str(meta.get("documento", ""))
    doc_title_norm = _norm_text(doc_title)

    # 1. Sobreposição lexical de tokens e bigramas da consulta
    if query_tokens:
        hits = sum(1 for t in query_tokens if t in doc_tokens or t in doc_norm)
        lexical_score = hits / len(query_tokens)
    else:
        lexical_score = 0.0

    bigram_bonus = 0.0
    if len(query_tokens) >= 2:
        bigrams = [f"{query_tokens[i]} {query_tokens[i + 1]}" for i in range(len(query_tokens) - 1)]
        bg_hits = sum(1 for bg in bigrams if bg in doc_norm)
        bigram_bonus = 0.15 * (bg_hits / len(bigrams))

    # 2. Bônus determinístico de domínio normativo / ponte bilíngue PT-EN
    rule_bonus = 0.0
    for target_docs, key_phrases in matched_rules:
        doc_matches = any(_norm_text(td) == doc_title_norm for td in target_docs)
        if doc_matches:
            rule_bonus += 0.22
            phrase_hits = sum(1 for kp in key_phrases if kp in doc_norm)
            if phrase_hits > 0:
                rule_bonus += 0.48 + min(0.25, 0.10 * (phrase_hits - 1))

    return (0.50 * dense_sim) + (0.35 * lexical_score) + bigram_bonus + rule_bonus


def query_knowledge_base(
    query: str,
    n_results: int = 3,
    collection_name: str | None = None,
) -> list[dict[str, Any]]:
    """Consulta trechos textuais relevantes na coleção do ChromaDB (RAG híbrido).

    Retorna trechos com citações obrigatórias:
    (documento, fonte_id, arquivo, pagina, versao_indice).
    """
    col_name = collection_name or CHROMA_COLLECTION
    client = get_chroma_client()

    if client is None:
        return []

    try:
        col = _get_or_create_collection_safe(client, col_name)
        q_vecs = embed_texts([query], is_query=True)
        candidate_k = max(n_results * 20, 60)

        if q_vecs:
            try:
                res = col.query(query_embeddings=q_vecs, n_results=candidate_k)
            except Exception:
                res = col.query(query_texts=[query], n_results=candidate_k)
        else:
            res = col.query(query_texts=[query], n_results=candidate_k)

        ids_list = res.get("ids", [[]])[0]
        documents = res.get("documents", [[]])[0]
        metadatas = res.get("metadatas", [[]])[0]
        distances = res.get("distances", [[]])[0]

        dense_by_id: dict[str, float] = {}
        direct_candidates: dict[str, dict[str, Any]] = {}
        for i, doc in enumerate(documents):
            if not doc:
                continue
            cid = ids_list[i] if i < len(ids_list) else str(i)
            meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            dist = float(distances[i]) if i < len(distances) else 1.0
            # Para vetores L2-normalizados, distância L2 ao quadrado está em [0, 2] e cosseno em [0, 1]
            sim = max(0.0, 1.0 - (dist / 2.0)) if dist > 1.0 else max(0.0, 1.0 - dist)
            dense_by_id[cid] = sim
            direct_candidates[cid] = {
                "id": cid,
                "text": doc,
                "norm_text": _norm_text(doc),
                "tokens": set(_tokenize(doc)),
                "meta": meta,
            }

        all_records = _get_cached_collection_chunks(col, col_name)
        pool = all_records if all_records else list(direct_candidates.values())
        if not pool:
            return []

        q_norm = _norm_text(query)
        q_tokens = _tokenize(query)
        matched_rules: list[tuple[list[str], list[str]]] = []
        for triggers, target_docs, key_phrases in _DOMAIN_RULES:
            if all(_norm_text(tr) in q_norm for tr in triggers):
                matched_rules.append((target_docs, [_norm_text(kp) for kp in key_phrases]))

        scored: list[tuple[float, dict[str, Any]]] = []
        for rec in pool:
            cid = rec["id"]
            d_sim = dense_by_id.get(cid, 0.25)
            h_score = _compute_hybrid_score(q_norm, q_tokens, rec, d_sim, matched_rules)
            scored.append((h_score, rec))

        scored.sort(key=lambda item: item[0], reverse=True)

        results: list[dict[str, Any]] = []
        for score, rec in scored[:n_results]:
            meta = rec["meta"]
            similarity = round(min(0.999, max(0.0, score)), 3)
            results.append(
                {
                    "text": rec["text"],
                    "source": meta.get("arquivo", meta.get("documento", "documento_oficial")),
                    "similarity": similarity,
                    "source_title": meta.get("documento", "Norma Oficial"),
                    "source_url": meta.get("link", "https://www.gov.br/anvisa"),
                    "page": meta.get("pagina"),
                    "fonte_id": meta.get("fonte_id"),
                    "versao_indice": meta.get("versao_indice", col_name),
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
    """Indexa lotes de documentos com embeddings explícitos e metadados obrigatórios no ChromaDB."""
    col_name = collection_name or CHROMA_COLLECTION
    client = get_chroma_client()

    if client is not None:
        try:
            col = _get_or_create_collection_safe(client, col_name)
            vecs = embed_texts(documents, is_query=False)
            if vecs:
                col.upsert(documents=documents, embeddings=vecs, metadatas=metadatas, ids=ids)
            else:
                col.upsert(documents=documents, metadatas=metadatas, ids=ids)
            _COLLECTION_DOCS_CACHE.pop(col_name, None)
            logger.info("Indexados %d documentos na coleção %s", len(documents), col_name)
            return True
        except Exception as exc:
            logger.error("Erro ao indexar no ChromaDB nativo: %s", exc)

    return False
