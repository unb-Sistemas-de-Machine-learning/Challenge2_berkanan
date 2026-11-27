from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Literal
from uuid import UUID
from datetime import datetime

RequestType = Literal["ocr_analysis", "comparison", "qa"]
RecommendationTone = Literal["SAUDAVEL", "ATENCAO", "EVITAR", "INCONCLUSIVO", "ERRO"]

class UserProfile(BaseModel):
    has_diabetes: bool = False
    has_hypertension: bool = False


class ConfirmedData(BaseModel):
    model_config = ConfigDict(extra="allow")

    tipo_alimento: Optional[Literal["liquido", "solido"]] = None
    categoria_produto: Optional[str] = None
    values_per_100g: Optional[dict[str, float]] = None
    product_name: Optional[str] = None


class ComparisonNutrient(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None


class ComparisonProduct(BaseModel):
    product_id: Optional[str] = None
    product_name: str
    source: str
    validated: bool
    nutrients: dict[str, ComparisonNutrient]


class ComparisonData(BaseModel):
    basis: str
    products: List[ComparisonProduct]


class AnalysisRequest(BaseModel):
    request_type: RequestType = "ocr_analysis"
    text: Optional[str] = None
    image_base64: Optional[str] = None
    product_ids: Optional[List[str]] = None
    confirmed_data: Optional[ConfirmedData] = None
    comparison_data: Optional[ComparisonData] = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    enable_verifier: bool = True
    verifier_mode: Literal["rules", "llm"] = Field(
        default="rules",
        description="Modo de verificação para o benchmark",
    )
    modo_execucao: Literal["rag", "llm_puro"] = "rag"
    categoria_teste: Optional[str] = None
    id_questao_teste: Optional[str] = None
    versao_ocr: Optional[str] = None

class MatchedSource(BaseModel):
    text: str
    source: str
    similarity: float
    source_url: Optional[str] = None
    source_title: Optional[str] = None

class ExtractedOCRData(BaseModel):
    product_name: Optional[str] = None
    values_per_100g: Optional[Dict[str, float]] = None

class VerificationResult(BaseModel):
    passed: bool
    errors: List[str] = []

class AnalysisResponse(BaseModel):
    id: Optional[UUID] = None
    input_text: Optional[str] = None
    llm_explanation: Optional[str] = None
    matched_sources: List[MatchedSource] = []
    timestamp: Optional[datetime] = None
    response_time_ms: int = 0
    llm_calls: int = Field(
        default=0,
        description="Quantidade de chamadas ao LLM na requisição",
    )
    classification: RecommendationTone = "INCONCLUSIVO"
    confidence_score: float = 1.0
    rag_sources_count: int = 0
    extracted_data: Optional[ExtractedOCRData] = None
    warnings: List[str] = []
    verification: Optional[VerificationResult] = None
