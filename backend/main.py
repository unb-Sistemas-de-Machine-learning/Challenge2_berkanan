from fastapi import FastAPI
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
import time
import json
import asyncio
from typing import Any
from schemas import AnalysisRequest, AnalysisResponse, VerificationResult, ExtractedOCRData
from graph import app as langgraph_app
from database import check_postgres_connection, record_metric, get_taco_alimento
from chroma_client import check_chroma_connection, query_knowledge_base
from ocr_extraction import extract_from_image_base64

logger = logging.getLogger("berkanan.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Aquecendo o RAG...")
    logger.info("Aquecendo o RAG...")
    timeout_seconds = float(os.getenv("RAG_WARMUP_TIMEOUT_SECONDS", "20"))

    async def warm_rag() -> None:
        started_at = time.perf_counter()
        try:
            results = await asyncio.wait_for(
                asyncio.to_thread(
                    query_knowledge_base,
                    "teste de aquecimento",
                    1,
                ),
                timeout=timeout_seconds,
            )
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            if results:
                print(f"RAG aquecido com sucesso! ({elapsed_ms} ms, {len(results)} fontes)")
                logger.info(
                    "RAG aquecido com sucesso! (%d ms, %d fontes)",
                    elapsed_ms,
                    len(results),
                )
            else:
                logger.warning(
                    "RAG iniciado sem fontes disponiveis apos aquecimento (%d ms).",
                    elapsed_ms,
                )
        except TimeoutError:
            logger.warning(
                "Aquecimento do RAG excedeu %ss; continuando sem bloquear o servidor.",
                timeout_seconds,
            )
        except Exception as exc:
            logger.warning("Nao foi possivel aquecer o RAG: %s", exc)

    asyncio.create_task(warm_rag())

    yield


api = FastAPI(
    title="Berkanan Desafio 2 - API Local",
    lifespan=lifespan,
)

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

    if "llm_calls" in final_state:
        chamadas_llm = int(final_state.get("llm_calls", 0))
    else:
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

    extracted_ocr_data: dict[str, Any] | None = None

    if request.image_base64:
        ocr_result = extract_from_image_base64(request.image_base64)
        extracted = ocr_result.get("extracted") or {}
        numeric_values = {
            key: value
            for key, value in extracted.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            and key not in {"porcao_g"}
        }
        extracted_ocr_data = {
            "product_name": None,
            "values_per_100g": numeric_values,
            "ocr_text": ocr_result.get("ocr_text"),
            "consistency_passed": extracted.get("consistency_passed"),
            "consistency_errors": extracted.get("consistency_errors", []),
            "requires_user_confirmation": True,
            "alergicos_contem": extracted.get("alergicos_contem", ""),
            "alergicos_pode_conter": extracted.get("alergicos_pode_conter", ""),
        }
        response_time = int((time.perf_counter() - start_time) * 1000)
        ocr_warning = ocr_result.get("warning")
        warnings = [ocr_warning] if ocr_warning else []
        return AnalysisResponse(
            input_text=None,
            llm_explanation=None,
            matched_sources=[],
            response_time_ms=response_time,
            llm_calls=0,
            classification="INCONCLUSIVO",
            confidence_score=1.0,
            rag_sources_count=0,
            extracted_data=ExtractedOCRData(
                product_name=None,
                values_per_100g=numeric_values,
            ),
            warnings=warnings,
            verification=None,
            timestamp=datetime.now(timezone.utc),
        )

    if request.text:
        try:
            parsed_confirmation = json.loads(request.text)
            if isinstance(parsed_confirmation, dict):
                extracted_ocr_data = parsed_confirmation
                if "values_per_100g" in parsed_confirmation:
                    extracted_ocr_data = dict(parsed_confirmation["values_per_100g"])
                    extracted_ocr_data["product_name"] = parsed_confirmation.get("product_name")
                    extracted_ocr_data["alergicos_contem"] = ""
                    extracted_ocr_data["alergicos_pode_conter"] = ""
                    alias_map = {
                        "acucares": "acucares_adicionados_g",
                        "acucares_adicionados": "acucares_adicionados_g",
                        "gorduras_saturadas": "gorduras_saturadas_g",
                        "gorduras_totais": "gorduras_totais_g",
                        "sodio": "sodio_mg",
                        "calorias": "valor_energetico_kcal",
                        "carboidratos": "carboidratos_g",
                        "proteinas": "proteinas_g",
                        "fibra": "fibra_alimentar_g",
                    }
                    for alias, canonical in alias_map.items():
                        if alias in extracted_ocr_data and canonical not in extracted_ocr_data:
                            extracted_ocr_data[canonical] = extracted_ocr_data[alias]
        except json.JSONDecodeError:
            pass

    initial_state = {
        "request_type": request.request_type,
        "enable_verifier": request.enable_verifier,
        "verifier_mode": request.verifier_mode,
        "llm_calls": 0,
        "text_query": request.text,
        "image_base64": request.image_base64,
        "product_ids": request.product_ids,
        "user_profile": request.user_profile.model_dump(),
        "extracted_ocr_data": extracted_ocr_data,
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
        llm_calls=int(final_state.get("llm_calls", 0)),
        classification=final_state.get("classification_tone", "INCONCLUSIVO"),
        confidence_score=1.0 if final_state.get("verification_passed") else 0.5,
        rag_sources_count=len(final_state.get("matched_sources", [])),
        extracted_data=ExtractedOCRData(
            product_name=(extracted_ocr_data or {}).get("product_name"),
            values_per_100g={
                str(key): float(value)
                for key, value in (extracted_ocr_data or {}).items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            } if extracted_ocr_data else None,
        ) if extracted_ocr_data else None,
        warnings=final_state.get("warnings", []),
        verification=verification_result,
        timestamp=datetime.now(timezone.utc)
    )
