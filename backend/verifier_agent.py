
import math
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
