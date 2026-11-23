from rotulagem import classificar_alto_em
from langgraph.graph import StateGraph, END

from state import AgentState
from coordinator import coordinator_node, route_coordinator
from comparison_agent import comparison_agent_node
from verifier_agent import verifier_agent_node

def _gerar_resumo_rotulagem(resultado: dict) -> str:
    """
    Gera um resumo textual a partir do resultado determinístico.

    Não utiliza LLM e não altera a classificação produzida
    por classificar_alto_em().
    """

    status = resultado["status"]

    if status == "confirmar_valores":
        return (
            "Não foi possível concluir a classificação nutricional "
            "porque foram identificadas inconsistências nos valores "
            "informados. Confira os dados do rótulo antes de continuar."
        )

    regra_anexo_xvi = resultado.get("regra_anexo_xvi")

    if regra_anexo_xvi == "condicional":
        return (
            "Esta categoria de produto possui uma regra específica "
            "no Anexo XVI da IN 75/2020. A aplicação do selo depende "
            "da composição e dos ingredientes adicionados. "
            "O sistema não avaliou essa exceção."
        )

    if regra_anexo_xvi == "vedacao":
        return (
            "Esta categoria está abrangida pelas disposições de "
            "vedação do Anexo XVI da IN 75/2020. O sistema não "
            "declara ALTO EM para este produto."
        )

    alto_em = resultado.get("alto_em", [])
    nao_avaliados = resultado.get("nao_avaliados", [])

    if alto_em:
        nutrientes = ", ".join(alto_em)

        mensagem = (
            f"Com base nos valores informados, o produto atende "
            f"aos critérios de ALTO EM para: {nutrientes}."
        )
    else:
        mensagem = (
            "Com base nos valores informados, nenhum dos nutrientes "
            "avaliados atingiu os limites de ALTO EM."
        )

    if nao_avaliados:
        pendentes = ", ".join(nao_avaliados)
        mensagem += (
            f" Não foi possível avaliar os seguintes nutrientes: "
            f"{pendentes}."
        )

    return mensagem

def nutritional_agent_node(state: AgentState):
    """
    Nó nutricional.

    Para solicitações ocr_analysis, executa a classificação
    determinística de ALTO EM usando os valores confirmados
    pelo usuário.

    O conteúdo RAG continua provisório.
    """
    print("-> Agente Nutricional gerando resposta...")

    warnings = list(state.get("warnings", []))
    rotulagem_resultado = None

    if state.get("request_type") == "ocr_analysis":
        valores = state.get("valores_nutricionais_100")
        tipo = state.get("tipo_alimento")
        categoria = state.get("categoria_produto") or "outro"

        if valores is None or tipo is None:
            return {
                "draft_response": (
                    "Não foi possível realizar a classificação. "
                    "Os valores nutricionais confirmados e o tipo "
                    "de alimento são obrigatórios."
                ),
                "classification_tone": "ERRO",
                "warnings": warnings + [
                    "Dados nutricionais ou tipo de alimento ausentes."
                ],
                "verification_passed": False,
                "verification_errors": [
                    "Dados nutricionais ou tipo de alimento ausentes."
                ],
                "rotulagem_resultado": None,
            }

        try:
            rotulagem_resultado = classificar_alto_em(
                valores,
                tipo,
                categoria_produto=categoria,
            )

        except ValueError as exc:
            mensagem_erro = str(exc)

            return {
                "draft_response": (
                    "Não foi possível classificar o produto devido "
                    "a dados inválidos."
                ),
                "classification_tone": "ERRO",
                "warnings": warnings + [mensagem_erro],
                "verification_passed": False,
                "verification_errors": [mensagem_erro],
                "rotulagem_resultado": None,
            }

        resumo = _gerar_resumo_rotulagem(rotulagem_resultado)

        aviso = rotulagem_resultado.get("aviso")
        if aviso:
            warnings.append(aviso)

        warnings.extend(
            rotulagem_resultado.get("inconsistencias", [])
        )

        return {
            "rotulagem_resultado": rotulagem_resultado,
            "draft_response": resumo,
            "warnings": warnings,

            # ALTO EM não equivale a uma recomendação geral.
            "classification_tone": "INCONCLUSIVO",
        }

    # Fluxo provisório de QA: ainda não utiliza a classificação
    # de rotulagem.
    return {
        "rag_context": [
            "Guia Alimentar: Evite ultraprocessados."
        ],
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
        "warnings": warnings + [
            "Alto teor de açúcar para diabéticos."
        ],
        "classification_tone": "EVITAR",
        "rotulagem_resultado": None,
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