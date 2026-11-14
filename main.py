from fastapi import FastAPI
from datetime import datetime, timezone
import time
from schemas import AnalysisRequest, AnalysisResponse, VerificationResult
from graph import app as langgraph_app

api = FastAPI(title="Berkanan Desafio 2 - API Local")

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
