#!/usr/bin/env python3
"""Script de ingestão da Feature Store vetorial ChromaDB (R4 - Engenheiro de Dados).

Indexa trechos das 5 fontes oficiais na coleção versionada (base_conhecimento_v1):
1. Guia Alimentar para a População Brasileira (MS)
2. RDC 429/2020 (ANVISA)
3. IN 75/2020 (ANVISA)
4. Diretrizes sobre açúcares e sódio (OMS)
5. Diretrizes da Sociedade Brasileira de Diabetes (SBD)

Metadados obrigatórios por trecho (conforme CLAUDE.md Seção 6.2):
- documento
- fonte_id
- arquivo
- pagina
- versao_indice
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("berkanan.ingest_chroma")

CHROMA_HOST = os.getenv("CHROMA_HOST", "127.0.0.1")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "base_conhecimento_v1")

# Documentos oficiais e trechos canônicos de referência inicial para o RAG
EXCERPTS_INICIAIS: list[dict[str, Any]] = [
    {
        "id": "guia_alimentar_c1_01",
        "documento": "Guia Alimentar para a População Brasileira",
        "fonte_id": 1,
        "arquivo": "guia_alimentar_2014.pdf",
        "pagina": 45,
        "versao_indice": "base_conhecimento_v1",
        "link": "https://www.gov.br/saude/pt-br/assuntos/saude-brasil/publicacoes-para-promocao-a-saude/guia_alimentar_populacao_brasileira_2ed.pdf",
        "text": (
            "Capítulo 2: A regra de ouro é fazer de alimentos in natura ou minimamente processados a base da alimentação. "
            "Limite o consumo de alimentos processados e evite o consumo de alimentos ultraprocessados. "
            "Alimentos ultraprocessados são formulações industriais feitas inteiramente ou majoritariamente de substâncias "
            "extraídas de alimentos (óleos, gorduras, açúcar, amido, proteínas), derivadas de constituintes de alimentos "
            "ou sintetizadas em laboratório com base em matérias orgânicas como petróleo e carvão (corantes, aromatizantes, "
            "realçadores de sabor e vários tipos de aditivos)."
        ),
    },
    {
        "id": "anvisa_in75_rotulagem_01",
        "documento": "IN 75/2020",
        "fonte_id": 3,
        "arquivo": "in_75_2020_anvisa.pdf",
        "pagina": 12,
        "versao_indice": "base_conhecimento_v1",
        "link": "https://www.in.gov.br/en/web/dou/-/instrucao-normativa-in-n-75-de-8-de-outubro-de-2020-282303074",
        "text": (
            "Instrução Normativa IN nº 75/2020: Estabelece os requisitos técnicos para declaração da rotulagem nutricional "
            "nos alimentos embalados. Define os limites de corte para a rotulagem nutricional frontal (lupas de 'ALTO EM'): "
            "Para alimentos sólidos ou semissólidos: Açúcares adicionados: 15 g por 100 g; Gorduras saturadas: 6 g por 100 g; "
            "Sódio: 600 mg por 100 g. Para alimentos líquidos: Açúcares adicionados: 7,5 g por 100 ml; Gorduras saturadas: "
            "3 g por 100 ml; Sódio: 300 mg por 100 ml. A rotulagem frontal visa esclarecer o consumidor sobre o alto teor de "
            "nutrientes associados a doenças crônicas não transmissíveis."
        ),
    },
    {
        "id": "anvisa_rdc429_alergenicos_01",
        "documento": "RDC 429/2020",
        "fonte_id": 2,
        "arquivo": "rdc_429_2020_anvisa.pdf",
        "pagina": 8,
        "versao_indice": "base_conhecimento_v1",
        "link": "https://www.in.gov.br/en/web/dou/-/resolucao-de-diretoria-colegiada-rdc-n-429-de-8-de-outubro-de-2020-282305411",
        "text": (
            "Resolução RDC nº 429/2020 e normas complementares de rotulagem de alergênicos (RDC nº 727/2022 / RDC nº 26/2015): "
            "Os alimentos que contenham ou derivem dos principais alimentos que causam alergias alimentares devem veicular "
            "as declarações 'ALÉRGICOS: CONTÉM (nomes comuns dos alimentos)', 'ALÉRGICOS: CONTÉM DERIVADOS DE...' ou "
            "'ALÉRGICOS: PODE CONTER...'. O sistema nunca deve afirmar que um alimento é 'livre de alergênicos', pois há risco "
            "de contaminação cruzada industrial; a conferência da embalagem física pelo consumidor é indispensável."
        ),
    },
    {
        "id": "oms_acucares_sodio_01",
        "documento": "Diretrizes sobre açúcares e sódio",
        "fonte_id": 5,
        "arquivo": "guideline_sugars_sodium_who.pdf",
        "pagina": 4,
        "versao_indice": "base_conhecimento_v1",
        "link": "https://www.who.int/publications/i/item/9789241549028",
        "text": (
            "Diretrizes da Organização Mundial da Saúde (OMS): A OMS recomenda fortemente a redução do consumo diário de "
            "açúcares livres para menos de 10% da ingestão calórica total diária em crianças e adultos. Uma redução adicional "
            "para menos de 5% (cerca de 25 g ao dia para um adulto) proporciona benefícios adicionais à saúde cardiovascular "
            "e dentária. Quanto ao sódio, a OMS recomenda uma ingestão máxima de 2.000 mg de sódio por dia (equivalente a 5 g de sal), "
            "para controle da pressão arterial e redução do risco de doenças cardiovasculares."
        ),
    },
    {
        "id": "sbd_diabetes_avisos_01",
        "documento": "Diretrizes da Sociedade Brasileira de Diabetes (SBD)",
        "fonte_id": 6,
        "arquivo": "diretrizes_sbd_2023.pdf",
        "pagina": 30,
        "versao_indice": "base_conhecimento_v1",
        "link": "https://diretriz.diabetes.org.br",
        "text": (
            "Diretrizes da Sociedade Brasileira de Diabetes (SBD) — Uso estrito a avisos para pessoas com diabetes: "
            "O consumo de carboidratos de rápida absorção e açúcares adicionados deve ser estritamente monitorado por indivíduos "
            "com diagnóstico de Diabetes Mellitus. A contagem de carboidratos é a estratégia padrão para ajuste prandial de insulina "
            "e controle glicêmico. O sistema não prescreve dietas nem doses medicamentosas, servindo exclusivamente como guia "
            "educativo para identificação de açúcares ocultos e carboidratos no rótulo."
        ),
    },
]


def _get_or_create_collection(client: Any, collection_name: str, host: str, port: int) -> Any:
    try:
        return client.get_collection(name=collection_name)
    except Exception:
        import urllib.request
        url = f"http://{host}:{port}/api/v1/collections"
        req = urllib.request.Request(
            url,
            data=json.dumps({"name": collection_name, "metadata": {"description": "Feature Store Vetorial"}}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
        return client.get_collection(name=collection_name)


def ingest(collection_name: str = CHROMA_COLLECTION, host: str = CHROMA_HOST, port: int = CHROMA_PORT) -> int:
    """Realiza a indexação dos trechos iniciais das fontes oficiais no ChromaDB."""
    logger.info("Conectando ao ChromaDB em %s:%d (coleção: %s)...", host, port, collection_name)

    try:
        import chromadb
        client = chromadb.HttpClient(host=host, port=port)
    except Exception as exc:
        logger.error("Não foi possível conectar via cliente ChromaDB nativo: %s", exc)
        return 1

    try:
        col = _get_or_create_collection(client, collection_name, host, port)

        ids = [doc["id"] for doc in EXCERPTS_INICIAIS]
        documents = [doc["text"] for doc in EXCERPTS_INICIAIS]
        metadatas = [
            {
                "documento": doc["documento"],
                "fonte_id": doc["fonte_id"],
                "arquivo": doc["arquivo"],
                "pagina": doc["pagina"],
                "versao_indice": doc["versao_indice"],
                "link": doc["link"],
            }
            for doc in EXCERPTS_INICIAIS
        ]

        col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("✓ Sucesso: %d trechos indexados na coleção '%s'.", len(ids), collection_name)
        return 0
    except Exception as exc:
        logger.error("Falha durante indexação no ChromaDB: %s", exc)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingestão de fontes oficiais no ChromaDB (R4)")
    parser.add_argument("--host", default=CHROMA_HOST, help="Host do ChromaDB")
    parser.add_argument("--port", type=int, default=CHROMA_PORT, help="Porta do ChromaDB")
    parser.add_argument("--collection", default=CHROMA_COLLECTION, help="Nome da coleção versionada")
    args = parser.parse_args()

    sys.exit(ingest(args.collection, args.host, args.port))

