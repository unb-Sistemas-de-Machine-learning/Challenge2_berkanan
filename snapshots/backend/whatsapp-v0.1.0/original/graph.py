from langgraph.graph import StateGraph, END
from state import AgentState

def coordinator_node(state: AgentState):
    print("-> Coordenador roteando...")
    return {}

def nutritional_agent_node(state: AgentState):
    print("-> Agente Nutricional gerando resposta...")
    return {
        "rag_context": ["Guia Alimentar: Evite ultraprocessados."],
        "draft_response": "Este produto parece ser ultraprocessado. A quantidade de açúcar é alta.",
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

def verifier_agent_node(state: AgentState):
    print("-> Verificador (LLM) checando alucinações...")
    passed = bool(state.get("matched_sources"))
    return {
        "verification_passed": passed,
        "verification_errors": [] if passed else ["Resposta sem fontes."]
    }

def route_verifier(state: AgentState):
    if state.get("enable_verifier", False):
        return "verifier"
    return END

workflow = StateGraph(AgentState)
workflow.add_node("coordinator", coordinator_node)
workflow.add_node("nutritional", nutritional_agent_node)
workflow.add_node("verifier", verifier_agent_node)

workflow.set_entry_point("coordinator")
workflow.add_edge("coordinator", "nutritional")
workflow.add_conditional_edges("nutritional", route_verifier, {"verifier": "verifier", END: END})
workflow.add_edge("verifier", END)

app = workflow.compile()
