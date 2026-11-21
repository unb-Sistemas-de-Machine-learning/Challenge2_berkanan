from typing import TypedDict, List, Optional, Dict, Any

class AgentState(TypedDict):
    request_type: str
    enable_verifier: bool
    verifier_mode: str
    llm_calls: int
    text_query: Optional[str]
    image_base64: Optional[str]
    product_ids: Optional[List[str]]
    user_profile: Dict[str, bool]
    extracted_ocr_data: Optional[Dict[str, Any]]
    comparison_data: Optional[Dict[str, Any]]
    rag_context: List[str]
    draft_response: Optional[str]
    matched_sources: List[Dict[str, Any]]
    warnings: List[str]
    classification_tone: str
    verification_passed: bool
    verification_errors: List[str]
