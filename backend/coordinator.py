
from typing import Optional

from state import AgentState


# Mapeamento entre os tipos de solicitação e os nós do LangGraph.
# OCR utiliza provisoriamente o agente nutricional existente.
ROUTE_BY_REQUEST_TYPE = {
    "ocr_analysis": "nutritional",
    "comparison": "comparison",
    "qa": "nutritional",
}


def get_route_for_request(request_type: str) -> Optional[str]:
    """
    Determina o fluxo correspondente ao tipo de solicitação.

    Retorna o nome do nó de destino ou None caso o tipo
    de solicitação não seja reconhecido.
    """
    return ROUTE_BY_REQUEST_TYPE.get(request_type)


def coordinator_node(state: AgentState) -> dict:
    """
    Nó responsável por validar o tipo de solicitação
    antes do roteamento.
    """
    request_type = state.get("request_type")

    print(f"-> Coordenador: analisando solicitação '{request_type}'")

    route = get_route_for_request(request_type)

    if route is None:
        error_message = (
            f"Tipo de solicitação não reconhecido: {request_type}"
        )

        print(f"-> Coordenador: {error_message}")

        return {
            "draft_response": (
                "Não foi possível processar a solicitação "
                "porque seu tipo não é reconhecido."
            ),
            "classification_tone": "ERRO",
            "warnings": state.get("warnings", []) + [error_message],
            "verification_passed": False,
            "verification_errors": (
                state.get("verification_errors", []) + [error_message]
            ),
        }

    print(f"-> Coordenador: encaminhando para '{route}'")

    return {}


def route_coordinator(state: AgentState) -> str:
    """
    Função condicional utilizada pelo LangGraph para
    selecionar o próximo nó.
    """
    request_type = state.get("request_type")
    route = get_route_for_request(request_type)

    return route if route is not None else "invalid"
