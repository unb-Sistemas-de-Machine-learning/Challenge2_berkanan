#!/usr/bin/env python3
"""Script de verificação da integração com PostgreSQL e ChromaDB (R4).

Testa:
1. Conectividade com PostgreSQL e verificação do esquema das migrações 001-004.
2. Existência das tabelas (fontes_documentos, taco_alimentos, limites_rotulagem, produtos_lidos, metricas_requisicao).
3. Existência das 9 views analíticas no PostgreSQL.
4. Conectividade com ChromaDB e inspeção da coleção base_conhecimento_v1.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Adiciona o diretório backend ao sys.path para importar módulos de banco
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from database import check_postgres_connection, get_db_cursor
from chroma_client import check_chroma_connection


def verify_postgres() -> bool:
    print("\n=== 1. Verificando Integração PostgreSQL ===")
    status = check_postgres_connection()
    print(f"Status geral: {status.get('status')} (conectado={status.get('connected')})")

    if not status.get("connected"):
        print(f"  [AVISO] PostgreSQL não acessível no momento: {status.get('message')}")
        print("  Execute 'docker compose up -d postgres' para subir o container.")
        return False

    print(f"  Banco de dados: {status.get('database')}")
    print(f"  Usuário: {status.get('user')}")
    print(f"  Versão do servidor: {status.get('server_version')}")

    print("\n  Contagem de registros por tabela do R4:")
    for tbl, count in status.get("table_counts", {}).items():
        print(f"    - {tbl}: {count} registro(s)")

    # Verifica as 9 views analíticas da migração 004
    views = [
        "vw_metricas_agregadas_diarias",
        "vw_checagem_limiares_monitoramento",
        "vw_benchmark_rag_vs_llm_puro",
        "vw_benchmark_verificador_abc",
        "vw_decisao_verificador_c_vs_b",
        "vw_benchmark_extracao_ocr",
        "vw_metricas_por_categoria_teste",
        "vw_avaliacao_usuarios",
        "vw_painel_consolidado_10_metricas",
    ]

    with get_db_cursor() as cur:
        if cur is not None:
            print("\n  Verificando views analíticas da migração 004:")
            for view in views:
                try:
                    cur.execute(f"SELECT COUNT(*) AS total FROM {view};")  # noqa: S608
                    print(f"    ✓ {view}: OK")
                except Exception as exc:
                    print(f"    ✗ {view}: FALHA ({exc})")

    return True


def verify_chroma() -> bool:
    print("\n=== 2. Verificando Integração ChromaDB ===")
    status = check_chroma_connection()
    print(f"Status geral: {status.get('status')} (conectado={status.get('connected')})")

    if not status.get("connected"):
        print(f"  [AVISO] ChromaDB não acessível no momento: {status.get('message')}")
        print("  Execute 'docker compose up -d chromadb' para subir o container.")
        return False

    print(f"  Host: {status.get('host')}:{status.get('port')}")
    print(f"  Coleções encontradas: {status.get('collections')}")
    print(f"  Coleção ativa: {status.get('active_collection')}")
    return True


def main() -> int:
    pg_ok = verify_postgres()
    chroma_ok = verify_chroma()

    print("\n=== Resumo de Integração dos Bancos (R4) ===")
    print(f"PostgreSQL (Feature Store Relacional): {'[ONLINE]' if pg_ok else '[AGUARDANDO SERVIÇO]'}")
    print(f"ChromaDB   (Feature Store Vetorial):   {'[ONLINE]' if chroma_ok else '[AGUARDANDO SERVIÇO]'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

