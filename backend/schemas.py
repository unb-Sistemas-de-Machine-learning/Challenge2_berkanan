from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Literal, Any
from uuid import UUID
from datetime import datetime

RequestType = Literal["ocr_analysis", "comparison", "qa"]
RecommendationTone = Literal["SAUDAVEL", "ATENCAO", "EVITAR", "INCONCLUSIVO", "ERRO"]

ProductCategory = Literal[
    "queijo",
    "leite",
    "leite_fermentado",
    "ovos",
    "carne_peixe",
    "frutas_vegetais_cereais_castanhas",
    "farinha",
    "oleo_azeite",
    "sal",
    "anexo_xvi_itens_11_18",
    "outro",
]

FoodType = Literal["solido", "liquido"]


class NutritionalValues100(BaseModel):
    # Rejeita campos extras que não estão definidos no modelo.
    model_config = ConfigDict(extra="forbid")
    
    acucares_adicionados: Optional[float] = None
    gorduras_saturadas: Optional[float] = None
    sodio: Optional[float] = None
    acucares_totais: Optional[float] = None
    carboidratos: Optional[float] = None

class UserProfile(BaseModel):
    has_diabetes: bool = False
    has_hypertension: bool = False

class AnalysisRequest(BaseModel):
    request_type: RequestType = "ocr_analysis"
    text: Optional[str] = None
    image_base64: Optional[str] = None
    product_ids: Optional[List[str]] = None
    user_profile: UserProfile = Field(default_factory=UserProfile)
    enable_verifier: bool = True
    verifier_mode: Optional[Literal["rules", "llm"]] = None
    modo_execucao: Literal["rag", "llm_puro"] = "rag"
    categoria_teste: Optional[str] = None
    id_questao_teste: Optional[str] = None
    versao_ocr: Optional[str] = None

    # Dados nutricionais confirmados pelo usuário.
    valores_nutricionais_100: Optional[NutritionalValues100] = None
    tipo_alimento: Optional[FoodType] = None
    categoria_produto: ProductCategory = "outro"

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
    classification: RecommendationTone = "INCONCLUSIVO"
    confidence_score: float = 1.0
    rag_sources_count: int = 0
    extracted_data: Optional[ExtractedOCRData] = None
    warnings: List[str] = []
    verification: Optional[VerificationResult] = None

    # Permite devolver o resultado completo de classificar_alto_em(), incluindo alto_em, nao_avaliados, avaliacao, regra_anexo_xvi e aviso, quando aplicáveis.
    rotulagem: Optional[Dict[str, Any]] = None