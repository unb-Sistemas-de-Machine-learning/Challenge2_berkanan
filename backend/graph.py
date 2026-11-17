
from langgraph.graph import StateGraph, END

from state import AgentState
from coordinator import coordinator_node, route_coordinator
from comparison_agent import comparison_agent_node
from verifier_agent import verifier_agent_node


def nutritional_agent_node(state: AgentState):
    """
    Nó nutricional provisório.

    Mantido conforme a implementação anterior do Carlos.
    Os dados e as fontes retornados aqui ainda são simulados
    e não representam uma integração RAG real.
    """
    print("-> Agente Nutricional gerando resposta...")

    return {
        "rag_context": ["Guia Alimentar: Evite ultraprocessados."],
        "draft_response": (
            "Este produto parece ser ultraprocessado. "
            "A quantidade de açúcar é alta."
        ),
        "matched_sources": [{
            "text": "Evite o consumo de alimentos ultraprocessados...",
            "source": "guia_alimentar_pag_45.pdf",
            "similarity": 0.92,
            "source_url": "https://www.gov.br",
            "source_title": "Guia Alimentar"
        }],
        "warnings": ["Alto teor de açúcar para diabéticos."],
        "classification_tone": "EVITAR"
    }


def route_verifier(state: AgentState):
    """
    Decide se a resposta deve passar pelo verificador.
    """
    if state.get("enable_verifier", False):
        return "verifier"

    return END


workflow = StateGraph(AgentState)

# Registro dos nós
workflow.add_node("coordinator", coordinator_node)
workflow.add_node("nutritional", nutritional_agent_node)
workflow.add_node("comparison", comparison_agent_node)
workflow.add_node("verifier", verifier_agent_node)

# Ponto inicial
workflow.set_entry_point("coordinator")

# O coordenador decide qual agente será executado.
workflow.add_conditional_edges(
    "coordinator",
    route_coordinator,
    {
        "nutritional": "nutritional",
        "comparison": "comparison",
        "invalid": END
    }
)

# Após a execução de cada agente, verifica se o verificador
# deve ser executado.
workflow.add_conditional_edges(
    "nutritional",
    route_verifier,
    {
        "verifier": "verifier",
        END: END
    }
)

workflow.add_conditional_edges(
    "comparison",
    route_verifier,
    {
        "verifier": "verifier",
        END: END
    }
)

# O fluxo termina depois da verificação.
workflow.add_edge("verifier", END)

# Compilação do grafo
app = workflow.compile()