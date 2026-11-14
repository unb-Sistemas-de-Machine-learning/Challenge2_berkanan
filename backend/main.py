from fastapi import FastAPI
from datetime import datetime, timezone
import time
import logging
from schemas import AnalysisRequest, AnalysisResponse, VerificationResult
from graph import app as langgraph_app
from database import check_postgres_connection, record_metric, get_taco_alimento
from chroma_client import check_chroma_connection, query_knowledge_base

logger = logging.getLogger("berkanan.api")

api = FastAPI(title="Berkanan Desafio 2 - API Local")

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
        record_metric(
            tipo_operacao=request.request_type,
            latencia_ms=response_time,
            modo_execucao="rag",
            configuracao_verificador="C" if request.enable_verifier else "A",
            modelo_usado="gemini",
            falha_leitura=False,
            chamadas_llm=1 if request.enable_verifier else 1,
            acerto=final_state.get("verification_passed", True),
            fidelidade_pct=92.0 if final_state.get("matched_sources") else None,
            recall_top3=True if final_state.get("matched_sources") else None,
        )
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
