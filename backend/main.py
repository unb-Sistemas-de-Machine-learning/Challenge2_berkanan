from fastapi import FastAPI
from datetime import datetime, timezone
import logging
import os
import time
from typing import Any
from schemas import AnalysisRequest, AnalysisResponse, VerificationResult
from graph import app as langgraph_app
from database import check_postgres_connection, record_metric, get_taco_alimento
from chroma_client import check_chroma_connection, query_knowledge_base

logger = logging.getLogger("berkanan.api")

api = FastAPI(title="Berkanan Desafio 2 - API Local")

_OPERATION_MAP = {
    "ocr_analysis": "extracao_ocr",
    "comparison": "comparacao_produtos",
    "qa": "chat_nutricional",
}

_TEST_CATEGORY_BY_PREFIX = {
    "A": "A_guia_alimentar",
    "B": "B_rotulagem_anvisa",
    "C": "C_calculo_alto_em",
    "D": "D_comparacao_produtos",
    "E": "E_alergenicos",
    "F": "F_saude_oms",
    "G": "G_fora_do_escopo",
}


def _resolve_verifier_config(request: AnalysisRequest) -> str:
    """Mapeia enable_verifier/verifier_mode para A (sem), B (regras) ou C (LLM)."""
    if not request.enable_verifier:
        return "A"
    if request.verifier_mode == "llm":
        return "C"
    return "B"


def _resolve_categoria_teste(request: AnalysisRequest) -> str | None:
    """Retorna categoria_teste informada ou infere pelo prefixo (A..G) de id_questao_teste."""
    if request.categoria_teste:
        return request.categoria_teste
    if request.id_questao_teste:
        prefix = request.id_questao_teste.strip().upper()[:1]
        return _TEST_CATEGORY_BY_PREFIX.get(prefix)
    return None


def _build_telemetry_payload(
    request: AnalysisRequest,
    final_state: dict[str, Any],
    response_time_ms: int,
) -> dict[str, Any]:
    """Monta os parâmetros alinhados às colunas de metricas_requisicao (ADR-008 / 004_metricas.sql)."""
    config_verificador = _resolve_verifier_config(request)
    tipo_operacao = _OPERATION_MAP.get(request.request_type, request.request_type)

    if request.versao_ocr:
        versao_ocr = request.versao_ocr
    elif request.request_type == "ocr_analysis":
        versao_ocr = os.getenv("OCR_ENGINE", "nao_configurado")
    else:
        versao_ocr = "nenhum"

    # Fluxo de comparação usa apenas regras determinísticas em código (0 chamadas ao LLM)
    base_llm_calls = 0 if request.request_type == "comparison" else 1
    verifier_llm_calls = 1 if config_verificador == "C" else 0
    chamadas_llm = base_llm_calls + verifier_llm_calls

    if chamadas_llm == 0:
        modelo_usado = "regras"
    else:
        llm_model = os.getenv("LLM_MODEL", "not_configured")
        llm_provider = os.getenv("LLM_PROVIDER", "gemini")
        modelo_usado = (llm_provider if llm_model == "not_configured" else llm_model)[:50]

    verification_passed = final_state.get("verification_passed", True)
    verification_errors = final_state.get("verification_errors", []) or []
    tone = final_state.get("classification_tone", "INCONCLUSIVO")

    falha_leitura = (tone == "ERRO") or (request.enable_verifier and not verification_passed)
    tipo_falha = "; ".join(str(e) for e in verification_errors)[:100] if falha_leitura and verification_errors else (
        "erro_orquestracao" if tone == "ERRO" else None
    )

    return {
        "tipo_operacao": tipo_operacao,
        "latencia_ms": response_time_ms,
        "modo_execucao": request.modo_execucao,
        "categoria_teste": _resolve_categoria_teste(request),
        "id_questao_teste": request.id_questao_teste,
        "configuracao_verificador": config_verificador,
        "versao_ocr": versao_ocr,
        "modelo_usado": modelo_usado,
        "falha_leitura": falha_leitura,
        "tipo_falha": tipo_falha,
        "chamadas_llm": chamadas_llm,
    }

@api.get("/health")
@api.get("/api/health")
async def health_check():
    """Endpoint de diagnóstico verificando saúde do Backend, PostgreSQL e ChromaDB."""
    pg_status = check_postgres_connection()
    chroma_status = check_chroma_connection()
    overall_healthy = pg_status.get("connected", False) and chroma_status.get("connected", False)

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "service": "berkanan-backend",
        "postgres": pg_status,
        "chromadb": chroma_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

@api.post("/api/analyze", response_model=AnalysisResponse)
async def analyze(request: AnalysisRequest):
    start_time = time.perf_counter()

    initial_state = {
        "request_type": request.request_type,
        "enable_verifier": request.enable_verifier,
        "text_query": request.text,
        "image_base64": request.image_base64,
        "product_ids": request.product_ids,
        "user_profile": request.user_profile.model_dump(),
        "extracted_ocr_data": None,
        "comparison_data": None,
        "rag_context": [],
        "draft_response": None,
        "matched_sources": [],
        "warnings": [],
        "classification_tone": "INCONCLUSIVO",
        "verification_passed": True,
        "verification_errors": []
    }

    final_state = langgraph_app.invoke(initial_state)
    response_time = int((time.perf_counter() - start_time) * 1000)

    verification_result = None
    if request.enable_verifier:
        verification_result = VerificationResult(
            passed=final_state.get("verification_passed", True),
            errors=final_state.get("verification_errors", [])
        )

    # Registro de telemetria operacional no PostgreSQL (ADR-008 e R4)
    try:
        telemetry = _build_telemetry_payload(request, final_state, response_time)
        record_metric(**telemetry)
    except Exception as exc:
        logger.warning("Falha ao registrar telemetria: %s", exc)

    return AnalysisResponse(
        input_text=request.text or "Análise de rótulo",
        llm_explanation=final_state.get("draft_response"),
        matched_sources=final_state.get("matched_sources", []),
        response_time_ms=response_time,
        classification=final_state.get("classification_tone", "INCONCLUSIVO"),
        confidence_score=1.0 if final_state.get("verification_passed") else 0.5,
        rag_sources_count=len(final_state.get("matched_sources", [])),
        warnings=final_state.get("warnings", []),
        verification=verification_result,
        timestamp=datetime.now(timezone.utc)
    )
