"""Módulo de integração com o banco de dados relacional PostgreSQL (ADR-001 e ADR-008).

Gerencia a conexão com o PostgreSQL, consultas à TACO (taco_alimentos),
limites da rotulagem frontal (limites_rotulagem - IN 75/2020),
cache de rótulos nutricionais processados (produtos_lidos)
e registro de telemetria / observabilidade (metricas_requisicao).
"""

from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

logger = logging.getLogger("berkanan.database")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "berkanan_dev")
POSTGRES_USER = os.getenv("POSTGRES_USER", "berkanan_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "dev_only_change_me")


def _get_connection_kwargs() -> dict[str, Any]:
    return {
        "host": POSTGRES_HOST,
        "port": POSTGRES_PORT,
        "dbname": POSTGRES_DB,
        "user": POSTGRES_USER,
        "password": POSTGRES_PASSWORD,
        "connect_timeout": 3,
    }


@contextmanager
def get_db_cursor() -> Generator[Any, None, None]:
    """Context manager para obter um cursor de conexão com o PostgreSQL.

    Trata graciosamente a ausência do driver psycopg2 ou indisponibilidade do banco.
    """
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        logger.warning("Driver psycopg2 não instalado. Operações relacionais indisponíveis.")
        yield None
        return

    conn = None
    try:
        conn = psycopg2.connect(**_get_connection_kwargs())
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cursor
        conn.commit()
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.warning("Falha na conexão ou operação PostgreSQL: %s", exc)
        yield None
    finally:
        if conn:
            conn.close()


def check_postgres_connection() -> dict[str, Any]:
    """Verifica a conectividade com o PostgreSQL e inspeciona as tabelas principais."""
    try:
        import psycopg2
    except ImportError:
        return {
            "status": "driver_missing",
            "message": "Driver psycopg2 não instalado",
            "connected": False,
        }

    with get_db_cursor() as cur:
        if cur is None:
            return {
                "status": "unreachable",
                "message": f"Não foi possível conectar em {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}",
                "connected": False,
            }

        try:
            cur.execute("SELECT current_database(), current_user, version();")
            info = cur.fetchone()

            # Contagem das tabelas do R4
            tables = ["fontes_documentos", "taco_alimentos", "limites_rotulagem", "produtos_lidos", "metricas_requisicao"]
            counts: dict[str, int] = {}
            for tbl in tables:
                try:
                    cur.execute(f"SELECT COUNT(*) AS total FROM {tbl};")  # noqa: S608
                    counts[tbl] = cur.fetchone()["total"]
                except Exception:
                    counts[tbl] = -1

            return {
                "status": "connected",
                "database": info["current_database"],
                "user": info["current_user"],
                "server_version": info["version"].split(",")[0],
                "table_counts": counts,
                "connected": True,
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": str(exc),
                "connected": False,
            }


def get_taco_alimento(search: str) -> list[dict[str, Any]]:
    """Busca alimentos na tabela TACO por código exato ou similaridade no nome."""
    with get_db_cursor() as cur:
        if cur is None:
            return []
        try:
            cur.execute(
                """
                SELECT codigo_taco, nome, grupo, energia_kcal, energia_kj,
                       proteina_g, lipidios_g, saturados_g, carboidrato_g, fibra_g, sodio_mg
                FROM taco_alimentos
                WHERE codigo_taco = %s OR nome ILIKE %s
                ORDER BY nome ASC
                LIMIT 10;
                """,
                (search.strip(), f"%{search.strip()}%"),
            )
            return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Erro ao buscar alimento TACO: %s", exc)
            return []


def get_limites_rotulagem(
    categoria: str | None = None, nutriente: str | None = None
) -> list[dict[str, Any]]:
    """Consulta os limites de rotulagem frontal da IN 75/2020."""
    with get_db_cursor() as cur:
        if cur is None:
            return []
        try:
            query = "SELECT id, norma, categoria, nutriente, limite_100g, unidade, trecho_norma FROM limites_rotulagem WHERE 1=1"
            params: list[Any] = []
            if categoria:
                query += " AND categoria = %s"
                params.append(categoria)
            if nutriente:
                query += " AND nutriente = %s"
                params.append(nutriente)
            query += " ORDER BY id ASC;"
            cur.execute(query, tuple(params))
            return [dict(row) for row in cur.fetchall()]
        except Exception as exc:
            logger.error("Erro ao consultar limites de rotulagem: %s", exc)
            return []


def get_cached_product(hash_rotulo: str) -> dict[str, Any] | None:
    """Recupera produto previamente lido pelo hash do rótulo (produtos_lidos)."""
    with get_db_cursor() as cur:
        if cur is None:
            return None
        try:
            cur.execute(
                """
                SELECT id, hash_rotulo, nome_produto, categoria, porcao_quantidade, porcao_unidade,
                       energia_kcal_100g, carboidrato_100g, acucares_totais_100g, acucares_adicionados_100g,
                       proteina_100g, gorduras_totais_100g, gorduras_saturadas_100g, gorduras_trans_100g,
                       fibra_100g, sodio_100g, valores_porcao_jsonb, percentual_vd_jsonb,
                       alergenicos_texto_bruto, alergenicos_extraidos, metodo_extracao,
                       versao_regras, confirmado_usuario, criado_em
                FROM produtos_lidos
                WHERE hash_rotulo = %s;
                """,
                (hash_rotulo,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        except Exception as exc:
            logger.error("Erro ao buscar produto no cache: %s", exc)
            return None


def save_cached_product(data: dict[str, Any]) -> bool:
    """Insere ou atualiza um produto no cache (produtos_lidos)."""
    with get_db_cursor() as cur:
        if cur is None:
            return False
        try:
            cur.execute(
                """
                INSERT INTO produtos_lidos (
                    hash_rotulo, nome_produto, categoria, porcao_quantidade, porcao_unidade,
                    energia_kcal_100g, carboidrato_100g, acucares_totais_100g, acucares_adicionados_100g,
                    proteina_100g, gorduras_totais_100g, gorduras_saturadas_100g, gorduras_trans_100g,
                    fibra_100g, sodio_100g, valores_porcao_jsonb, percentual_vd_jsonb,
                    alergenicos_texto_bruto, alergenicos_extraidos, metodo_extracao,
                    versao_regras, confirmado_usuario, atualizado_em
                ) VALUES (
                    %(hash_rotulo)s, %(nome_produto)s, %(categoria)s, %(porcao_quantidade)s, %(porcao_unidade)s,
                    %(energia_kcal_100g)s, %(carboidrato_100g)s, %(acucares_totais_100g)s, %(acucares_adicionados_100g)s,
                    %(proteina_100g)s, %(gorduras_totais_100g)s, %(gorduras_saturadas_100g)s, %(gorduras_trans_100g)s,
                    %(fibra_100g)s, %(sodio_100g)s, %(valores_porcao_jsonb)s, %(percentual_vd_jsonb)s,
                    %(alergenicos_texto_bruto)s, %(alergenicos_extraidos)s, %(metodo_extracao)s,
                    %(versao_regras)s, %(confirmado_usuario)s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (hash_rotulo) DO UPDATE SET
                    nome_produto = EXCLUDED.nome_produto,
                    categoria = EXCLUDED.categoria,
                    porcao_quantidade = EXCLUDED.porcao_quantidade,
                    porcao_unidade = EXCLUDED.porcao_unidade,
                    energia_kcal_100g = EXCLUDED.energia_kcal_100g,
                    carboidrato_100g = EXCLUDED.carboidrato_100g,
                    acucares_totais_100g = EXCLUDED.acucares_totais_100g,
                    acucares_adicionados_100g = EXCLUDED.acucares_adicionados_100g,
                    proteina_100g = EXCLUDED.proteina_100g,
                    gorduras_totais_100g = EXCLUDED.gorduras_totais_100g,
                    gorduras_saturadas_100g = EXCLUDED.gorduras_saturadas_100g,
                    gorduras_trans_100g = EXCLUDED.gorduras_trans_100g,
                    fibra_100g = EXCLUDED.fibra_100g,
                    sodio_100g = EXCLUDED.sodio_100g,
                    valores_porcao_jsonb = EXCLUDED.valores_porcao_jsonb,
                    percentual_vd_jsonb = EXCLUDED.percentual_vd_jsonb,
                    alergenicos_texto_bruto = EXCLUDED.alergenicos_texto_bruto,
                    alergenicos_extraidos = EXCLUDED.alergenicos_extraidos,
                    confirmado_usuario = EXCLUDED.confirmado_usuario,
                    atualizado_em = CURRENT_TIMESTAMP;
                """,
                {
                    "hash_rotulo": data["hash_rotulo"],
                    "nome_produto": data.get("nome_produto"),
                    "categoria": data.get("categoria"),
                    "porcao_quantidade": data.get("porcao_quantidade"),
                    "porcao_unidade": data.get("porcao_unidade"),
                    "energia_kcal_100g": data.get("energia_kcal_100g"),
                    "carboidrato_100g": data.get("carboidrato_100g"),
                    "acucares_totais_100g": data.get("acucares_totais_100g"),
                    "acucares_adicionados_100g": data.get("acucares_adicionados_100g"),
                    "proteina_100g": data.get("proteina_100g"),
                    "gorduras_totais_100g": data.get("gorduras_totais_100g"),
                    "gorduras_saturadas_100g": data.get("gorduras_saturadas_100g"),
                    "gorduras_trans_100g": data.get("gorduras_trans_100g"),
                    "fibra_100g": data.get("fibra_100g"),
                    "sodio_100g": data.get("sodio_100g"),
                    "valores_porcao_jsonb": json.dumps(data.get("valores_porcao_jsonb", {})),
                    "percentual_vd_jsonb": json.dumps(data.get("percentual_vd_jsonb", {})),
                    "alergenicos_texto_bruto": data.get("alergenicos_texto_bruto"),
                    "alergenicos_extraidos": json.dumps(data.get("alergenicos_extraidos", [])),
                    "metodo_extracao": data.get("metodo_extracao", "regras_r4"),
                    "versao_regras": data.get("versao_regras", "v1.0"),
                    "confirmado_usuario": data.get("confirmado_usuario", False),
                },
            )
            return True
        except Exception as exc:
            logger.error("Erro ao salvar produto no cache: %s", exc)
            return False


def record_metric(
    tipo_operacao: str,
    latencia_ms: int,
    modo_execucao: str = "rag",
    categoria_teste: str | None = None,
    id_questao_teste: str | None = None,
    configuracao_verificador: str | None = None,
    versao_ocr: str | None = None,
    modelo_usado: str = "gemini",
    falha_leitura: bool = False,
    tipo_falha: str | None = None,
    chamadas_llm: int = 1,
    acerto: bool | None = None,
    fidelidade_pct: float | None = None,
    recall_top3: bool | None = None,
    recusa_correta: bool | None = None,
    custo_estimado_usd: float | None = None,
    avaliacao_usuario_nota: int | None = None,
) -> bool:
    """Grava uma linha de telemetria na tabela metricas_requisicao (ADR-008)."""
    with get_db_cursor() as cur:
        if cur is None:
            return False
        try:
            cur.execute(
                """
                INSERT INTO metricas_requisicao (
                    timestamp_requisicao, tipo_operacao, modo_execucao, categoria_teste,
                    id_questao_teste, configuracao_verificador, versao_ocr, modelo_usado,
                    latencia_ms, falha_leitura, tipo_falha, chamadas_llm, acerto,
                    fidelidade_pct, recall_top3, recusa_correta, custo_estimado_usd,
                    avaliacao_usuario_nota
                ) VALUES (
                    CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                );
                """,
                (
                    tipo_operacao,
                    modo_execucao,
                    categoria_teste,
                    id_questao_teste,
                    configuracao_verificador,
                    versao_ocr,
                    modelo_usado,
                    latencia_ms,
                    falha_leitura,
                    tipo_falha,
                    chamadas_llm,
                    acerto,
                    fidelidade_pct,
                    recall_top3,
                    recusa_correta,
                    custo_estimado_usd,
                    avaliacao_usuario_nota,
                ),
            )
            return True
        except Exception as exc:
            logger.warning("Não foi possível gravar telemetria em metricas_requisicao: %s", exc)
            return False

