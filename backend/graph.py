
from langgraph.graph import StateGraph, END

from state import AgentState
from coordinator import coordinator_node, route_coordinator
from comparison_agent import comparison_agent_node
from verifier_agent import verifier_agent_node, verifier_agent_llm_node
from nutritional_agent import nutritional_agent_node


def route_verifier(state: AgentState):
    """
    Decide se a resposta deve passar pelo verificador.
    """
    if state.get("enable_verifier", False):
        if state.get("verifier_mode", "rules") == "llm":
            return "verifier_llm"
        return "verifier_rules"

    return END


workflow = StateGraph(AgentState)

# Registro dos nós
workflow.add_node("coordinator", coordinator_node)
workflow.add_node("nutritional", nutritional_agent_node)
workflow.add_node("comparison", comparison_agent_node)
workflow.add_node("verifier_rules", verifier_agent_node)
workflow.add_node("verifier_llm", verifier_agent_llm_node)

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
        "verifier_rules": "verifier_rules",
        "verifier_llm": "verifier_llm",
        END: END
    }
)

workflow.add_conditional_edges(
    "comparison",
    route_verifier,
    {
        "verifier_rules": "verifier_rules",
        "verifier_llm": "verifier_llm",
        END: END
    }
)

# O fluxo termina depois da verificação.
workflow.add_edge("verifier_rules", END)
workflow.add_edge("verifier_llm", END)

# Compilação do grafo
app = workflow.compile()