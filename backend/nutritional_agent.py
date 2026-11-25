import json
import logging
import os
import queue
import socket
import threading
import time
from typing import Any

from dotenv import load_dotenv

import database
from chroma_client import query_knowledge_base
from rotulagem import LIMITES_RESERVA, carregar_limites, classificar_alto_em
from state import AgentState

logger = logging.getLogger("berkanan.nutritional")

load_dotenv()

AVISO_SAUDAVEL = (
    "Nenhum nutriente atingiu os limites de ALTO EM da IN 75. Isso não quer dizer "
    "que o produto seja saudável em todos os aspectos: o Guia Alimentar recomenda "
    "preferir alimentos in natura ou minimamente processados."
)


def _get_gemini_model() -> Any | None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("replace_with"):
        return None

    model_name = os.getenv("LLM_MODEL", "").strip()
    if not model_name or model_name == "not_configured":
        logger.warning("LLM_MODEL não configurada no ambiente.")
        return None

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=8000),
        )
        return client
    except Exception as exc:
        logger.warning("Gemini indisponível: %s", exc)
        return None


def _get_llm_call_limit() -> int:
    try:
        limit = int(os.getenv("MAX_LLM_CALLS_PER_RESPONSE", "2"))
    except (TypeError, ValueError):
        limit = 2
    return max(limit, 0)


def _load_rotulagem_limits() -> tuple[dict, list[str]]:
    try:
        rows = database.get_limites_rotulagem()
    except Exception as exc:
        logger.warning(
            "limites da reserva em código, banco indisponível: %s",
            exc,
        )
        return dict(LIMITES_RESERVA), [
            "limites da reserva em código, banco indisponível"
        ]

    if not rows:
        logger.warning("limites da reserva em código, banco indisponível")
        return dict(LIMITES_RESERVA), [
            "limites da reserva em código, banco indisponível"
        ]

    return carregar_limites(lambda: rows), []


def _apply_taco_reference(dados_produto: dict[str, Any]) -> dict[str, Any]:
    """Completa somente dados por 100 g/100 ml quando houver categoria ou tipo."""
    relevant_keys = (
        "acucares_adicionados_g",
        "gorduras_saturadas_g",
        "sodio_mg",
    )
    if any(dados_produto.get(key) is not None for key in relevant_keys):
        return dados_produto

    search = (
        dados_produto.get("tipo_alimento")
        or dados_produto.get("categoria")
    )
    if not search:
        return dados_produto

    try:
        rows = database.get_taco_alimento(str(search))
    except Exception as exc:
        logger.warning("Consulta TACO indisponível: %s", exc)
        return dados_produto

    if not rows:
        return dados_produto

    row = rows[0]
    completed = dict(dados_produto)
    if completed.get("gorduras_saturadas_g") is None:
        completed["gorduras_saturadas_g"] = row.get("saturados_g")
    if completed.get("sodio_mg") is None:
        completed["sodio_mg"] = row.get("sodio_mg")
    return completed


def _deterministic_nutrition_analysis(
    dados_produto: dict[str, Any],
    limites: dict | None = None,
) -> dict[str, Any]:
    tipo = dados_produto.get("tipo_alimento")
    if tipo not in {"liquido", "solido"}:
        return {
            "status": "confirmar_tipo",
            "tipo": tipo,
            "alto_em": [],
            "nao_avaliados": [],
            "inconsistencias": [],
            "avaliacao": {},
        }
    values = {
        "acucares_adicionados": dados_produto.get("acucares_adicionados_g"),
        "gorduras_saturadas": dados_produto.get("gorduras_saturadas_g"),
        "sodio": dados_produto.get("sodio_mg"),
    }
    return classificar_alto_em(values, tipo, limites)


def _deterministic_classification(
    dados_produto: dict[str, Any],
    classificacao: dict[str, Any],
) -> str:
    """Define o tom sem depender do LLM; o LLM apenas explica o resultado."""
    if classificacao.get("status") in {"confirmar_tipo", "confirmar_valores"}:
        return "INCONCLUSIVO"

    relevant_fields = (
        "acucares_adicionados_g",
        "gorduras_saturadas_g",
        "sodio_mg",
    )
    if not any(dados_produto.get(field) is not None for field in relevant_fields):
        return "INCONCLUSIVO"

    if classificacao.get("alto_em"):
        return "EVITAR"

    if classificacao.get("nao_avaliados"):
        return "ATENCAO"

    return "SAUDAVEL"


def nutritional_agent_node(state: AgentState) -> dict:
    print("-> Agente Nutricional chamando RAG e Gemini...")

    dados_produto = state.get("extracted_ocr_data") or {}
    if not isinstance(dados_produto, dict):
        dados_produto = {}

    llm_calls = state.get("llm_calls", 0)
    tipo_alimento = dados_produto.get("tipo_alimento")
    if tipo_alimento not in {"liquido", "solido"}:
        return {
            "draft_response": (
                "Não há evidência suficiente para concluir a análise sem a "
                "confirmação do tipo do produto (sólido ou líquido)."
            ),
            "classification_tone": "INCONCLUSIVO",
            "warnings": [
                "Tipo do produto (sólido ou líquido) não informado; "
                "confirme o tipo antes da análise."
            ],
            "rag_context": [],
            "matched_sources": [],
            "llm_calls": llm_calls,
        }

    dados_produto = _apply_taco_reference(dados_produto)

    confirmed_text = state.get("text_query")
    query = confirmed_text
    if not query:
        query = "Rótulo nutricional açúcar gordura saturada sódio alergênicos IN 75 RDC 429"

    matched_sources: list[dict[str, Any]] = []
    chroma_host = os.getenv("CHROMA_HOST", "127.0.0.1")
    chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
    try:
        with socket.create_connection((chroma_host, chroma_port), timeout=0.5):
            pass
    except OSError:
        chroma_reachable = False
    else:
        chroma_reachable = True

    if chroma_reachable:
        result_queue: queue.Queue[list[dict[str, Any]]] = queue.Queue(maxsize=1)
        rag_started_at = time.perf_counter()

        def _rag_lookup() -> None:
            try:
                result_queue.put(query_knowledge_base(str(query), n_results=3) or [])
            except Exception as exc:
                logger.warning("Consulta RAG indisponível: %s", exc)
                result_queue.put([])

        rag_thread = threading.Thread(target=_rag_lookup, daemon=True)
        rag_thread.start()
        try:
            matched_sources = result_queue.get(timeout=5.0)
        except queue.Empty:
            logger.warning("Consulta RAG excedeu o timeout de 5 segundos.")
        finally:
            rag_elapsed_ms = int((time.perf_counter() - rag_started_at) * 1000)
            print(f"-> RAG: consulta concluida em {rag_elapsed_ms} ms")
    contexto = "\n\n".join(
        f"[Fonte: {item.get('source_title') or item.get('source')}] {item.get('text', '')}"
        for item in matched_sources
        if item.get("text")
    )

    limites, fallback_warnings = _load_rotulagem_limits()
    classificacao_deterministica = _deterministic_nutrition_analysis(
        dados_produto,
        limites,
    )
    alto_em = classificacao_deterministica.get("alto_em", [])
    inconsistencias = classificacao_deterministica.get("inconsistencias", [])
    deterministic_tone = _deterministic_classification(
        dados_produto,
        classificacao_deterministica,
    )
    warnings = list(inconsistencias)
    warnings.extend(fallback_warnings)

    contem = dados_produto.get("alergicos_contem")
    pode_conter = dados_produto.get("alergicos_pode_conter")
    if contem is None and pode_conter is None:
        warnings.append(
            "Não foi possível ler a linha ALÉRGICOS; confira a embalagem."
        )
    if contem:
        warnings.append(f"Alérgenos declarados: {contem}. Confira a embalagem física.")
    if pode_conter:
        warnings.append(
            f"Pode conter: {pode_conter}. Confira sempre a embalagem."
        )
    warnings.append(
        "O sistema é informativo e não substitui médico, nutricionista ou prescrição."
    )

    model = _get_gemini_model()
    llm_limit = _get_llm_call_limit()
    resultado: dict[str, Any]

    if not matched_sources:
        resultado = {
            "draft_response": "Não há evidência suficiente nas fontes recuperadas para sustentar uma análise.",
            "classification_tone": deterministic_tone,
            "warnings": warnings,
        }
    elif model is None:
        alto_texto = ", ".join(alto_em) if alto_em else "nenhum dos limites avaliados"
        resultado = {
            "draft_response": (
                "Análise determinística concluída. "
                f"Classificação ALTO EM: {alto_texto}. "
                "Os valores e limites foram obtidos do rótulo confirmado e da norma IN 75/2020."
                if alto_em
                else "Análise determinística concluída. Nenhum dos limites avaliados "
                "foi atingido pelos dados confirmados."
            ),
            "classification_tone": deterministic_tone,
            "warnings": warnings,
        }
    else:
        if llm_calls >= llm_limit:
            logger.warning(
                "Limite de chamadas ao LLM atingido (%s); chamada do agente nutricional ignorada.",
                llm_limit,
            )
            warnings.append(
                "Limite de chamadas ao LLM atingido; a resposta foi preservada em modo determinístico."
            )
            alto_texto = ", ".join(alto_em) if alto_em else "nenhum dos limites avaliados"
            resultado = {
                "draft_response": (
                    "Análise determinística concluída. "
                    f"Classificação ALTO EM: {alto_texto}. "
                    "Os valores foram obtidos do rótulo confirmado e da norma IN 75/2020."
                ),
                "classification_tone": deterministic_tone,
                "warnings": warnings,
            }
        else:
            llm_calls += 1
            prompt = f"""
Contexto oficial recuperado:
{contexto}

Dados confirmados do produto:
{json.dumps(dados_produto, ensure_ascii=False)}

Classificação determinística já calculada por código:
{json.dumps(classificacao_deterministica, ensure_ascii=False)}

Perfil do usuário:
Diabético: {bool((state.get("user_profile") or {}).get("has_diabetes"))}
Hipertenso: {bool((state.get("user_profile") or {}).get("has_hypertension"))}

Gere uma explicação somente baseada no contexto oficial e nos dados confirmados.
Não calcule nem invente valores nutricionais.
Responda apenas JSON válido com:
- draft_response: explicação clara
- classification_tone: SAUDAVEL, ATENCAO ou EVITAR
- warnings: lista de avisos
"""
            try:
                gemini_started_at = time.perf_counter()
                response = model.models.generate_content(
                    model=os.getenv("LLM_MODEL", "").strip(),
                    contents=prompt,
                )
                gemini_elapsed_ms = int((time.perf_counter() - gemini_started_at) * 1000)
                print(f"-> Gemini: chamada concluida em {gemini_elapsed_ms} ms")
                texto_limpo = (response.text or "").strip()
                if texto_limpo.startswith("```"):
                    texto_limpo = texto_limpo.strip("`")
                    if texto_limpo.lower().startswith("json"):
                        texto_limpo = texto_limpo[4:].strip()
                resultado = json.loads(texto_limpo)
            except Exception as exc:
                logger.warning("Falha ao processar resposta Gemini: %s", exc)
                resultado = {
                    "draft_response": "Não foi possível gerar uma explicação com o LLM. Os dados determinísticos foram preservados.",
                    "classification_tone": deterministic_tone,
                    "warnings": warnings,
                }

    tone = resultado.get("classification_tone")
    if tone not in {"SAUDAVEL", "ATENCAO", "EVITAR", "INCONCLUSIVO", "ERRO"}:
        tone = "INCONCLUSIVO"

    if deterministic_tone == "INCONCLUSIVO":
        tone = "INCONCLUSIVO"
    else:
        tone = deterministic_tone

    llm_warnings = resultado.get("warnings", [])
    if not isinstance(llm_warnings, list):
        llm_warnings = []

    forbidden_warning_text = (
        "não afirmar",
        "não declare",
        "nunca afirmar",
    )
    safe_llm_warnings = [
        str(warning)
        for warning in llm_warnings
        if warning
        and not any(text in str(warning).lower() for text in forbidden_warning_text)
    ]
    merged_warnings = list(dict.fromkeys(warnings + safe_llm_warnings))
    if tone == "SAUDAVEL" and AVISO_SAUDAVEL not in merged_warnings:
        merged_warnings.append(AVISO_SAUDAVEL)

    return {
        "draft_response": resultado.get("draft_response")
        or "Não há evidência suficiente para sustentar uma análise.",
        "classification_tone": tone,
        "warnings": merged_warnings,
        "rag_context": [item["text"] for item in matched_sources if item.get("text")],
        "matched_sources": matched_sources,
        "llm_calls": llm_calls,
    }
