
import math
import os
from typing import Any, Dict, List

from state import AgentState


# Expressões que identificam explicitamente insuficiência de evidências.
# A lista deve ser ampliada conforme os contratos de resposta evoluírem.
INSUFFICIENT_EVIDENCE_MARKERS = (
    "não foi possível realizar a comparação",
    "não existem nutrientes em comum",
    "não há evidência suficiente",
    "não foi possível verificar",
    "dados insuficientes",
)


def _validate_response(state: AgentState) -> List[str]:
    """Verifica se existe uma resposta textual válida."""
    response = state.get("draft_response")

    if not isinstance(response, str) or not response.strip():
        return ["V01: Resposta ausente ou vazia."]

    return []


def _validate_sources(state: AgentState) -> List[str]:
    """
    Verifica a estrutura das fontes recuperadas.

    Não comprova a veracidade semântica do conteúdo das fontes.
    """
    sources = state.get("matched_sources")

    if not isinstance(sources, list):
        return ["V03: Lista de fontes possui formato inválido."]

    if not sources:
        return ["V02: Resposta sem fontes documentais."]

    errors = []

    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            errors.append(
                f"V03: Fonte {index + 1} possui formato inválido."
            )
            continue

        if not isinstance(source.get("text"), str) or not source["text"].strip():
            errors.append(
                f"V03: Fonte {index + 1} não possui texto válido."
            )

        if not isinstance(source.get("source"), str) or not source["source"].strip():
            errors.append(
                f"V03: Fonte {index + 1} não possui identificação."
            )

        similarity = source.get("similarity")

        if (
            not isinstance(similarity, (int, float))
            or isinstance(similarity, bool)
            or not math.isfinite(similarity)
            or not 0 <= similarity <= 1
        ):
            errors.append(
                f"V03: Similaridade da fonte {index + 1} é inválida."
            )

    return errors


def _is_explicitly_inconclusive(state: AgentState) -> bool:
    """
    Identifica respostas que declaram explicitamente
    insuficiência de evidências.

    A classificação sozinha não é suficiente: o texto também
    precisa comunicar a limitação ao usuário.
    """
    classification = state.get("classification_tone")
    response = state.get("draft_response")

    if classification != "INCONCLUSIVO":
        return False

    if not isinstance(response, str):
        return False

    normalized_response = response.casefold()

    return any(
        marker in normalized_response
        for marker in INSUFFICIENT_EVIDENCE_MARKERS
    )


def verifier_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Verificador determinístico - configuração B.

    Verifica presença da resposta, necessidade e estrutura
    das fontes documentais.

    Não utiliza LLM e não realiza validação semântica
    das afirmações.
    """
    print("-> Verificador determinístico avaliando resposta...")

    errors = _validate_response(state)

    if not errors:
        if _is_explicitly_inconclusive(state):
            # Uma resposta que declara insuficiência de evidências
            # pode ser válida mesmo sem fontes recuperadas.
            print("-> Verificador: insuficiência declarada.")
        else:
            errors.extend(_validate_sources(state))

    passed = not errors

    return {
        "verification_passed": passed,
        "verification_errors": errors
    }


def verifier_agent_llm_node(state: AgentState) -> Dict[str, Any]:
    """Verificador semântico Configuração C (LLM)."""
    print("-> Verificador LLM (Config C) checando alucinações...")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or api_key.startswith("replace_with"):
        return {
            "verification_passed": False,
            "verification_errors": [
                "Configuração C indisponível: GEMINI_API_KEY não configurada."
            ],
            "llm_calls": state.get("llm_calls", 0),
        }

    model_name = os.getenv("LLM_MODEL", "").strip()
    if not model_name or model_name == "not_configured":
        return {
            "verification_passed": False,
            "verification_errors": [
                "Configuração C indisponível: LLM_MODEL não configurada no ambiente."
            ],
            "llm_calls": state.get("llm_calls", 0),
        }

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=8000),
        )
        prompt = f"""
Resposta gerada:
{state.get("draft_response")}

Fontes usadas:
{state.get("matched_sources")}

A resposta está 100% suportada pelas fontes?
Responda apenas 'SIM' ou 'NAO'.
"""
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        passed = "SIM" in (response.text or "").upper()
        return {
            "verification_passed": passed,
            "verification_errors": [] if passed else [
                "O LLM detectou afirmações sem suporte nas fontes."
            ],
            "llm_calls": state.get("llm_calls", 0) + 1,
        }
    except Exception as exc:
        return {
            "verification_passed": False,
            "verification_errors": [
                f"Falha ao executar o verificador LLM: {exc}"
            ],
            "llm_calls": state.get("llm_calls", 0),
        }
