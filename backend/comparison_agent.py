
import math
from typing import Any, Dict, List, Optional

from state import AgentState


def _is_valid_number(value: Any) -> bool:
    """
    Verifica se um valor é numérico, finito e não negativo.

    bool é excluído explicitamente porque, em Python,
    bool é uma subclasse de int.
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _get_validated_products(
    comparison_data: Optional[Dict[str, Any]]
) -> Optional[List[Dict[str, Any]]]:
    """
    Recupera os dois produtos somente quando os dados
    possuem a estrutura esperada e foram validados.
    """
    if not isinstance(comparison_data, dict):
        return None

    products = comparison_data.get("products")

    if not isinstance(products, list) or len(products) != 2:
        return None

    if not comparison_data.get("basis"):
        return None

    for product in products:
        if not isinstance(product, dict):
            return None

        if product.get("validated") is not True:
            return None

        if not product.get("product_name"):
            return None

        if not product.get("source"):
            return None

        nutrients = product.get("nutrients")

        if not isinstance(nutrients, dict):
            return None

    return products


def _compare_nutrients(
    product_a: Dict[str, Any],
    product_b: Dict[str, Any]
) -> List[str]:
    """
    Compara apenas nutrientes presentes nos dois produtos,
    com valores válidos e unidades iguais.

    Não aplica limites nutricionais nem recomenda produtos.
    """
    nutrients_a = product_a["nutrients"]
    nutrients_b = product_b["nutrients"]

    common_nutrients = set(nutrients_a) & set(nutrients_b)

    comparisons = []

    for nutrient in sorted(common_nutrients):
        data_a = nutrients_a[nutrient]
        data_b = nutrients_b[nutrient]

        if not isinstance(data_a, dict) or not isinstance(data_b, dict):
            continue

        value_a = data_a.get("value")
        value_b = data_b.get("value")
        unit_a = data_a.get("unit")
        unit_b = data_b.get("unit")

        if not _is_valid_number(value_a):
            continue

        if not _is_valid_number(value_b):
            continue

        if not unit_a or unit_a != unit_b:
            continue

        if value_a == value_b:
            difference = (
                f"{nutrient}: ambos apresentam {value_a:g} {unit_a}."
            )
        elif value_a > value_b:
            difference = (
                f"{nutrient}: {product_a['product_name']} apresenta "
                f"{value_a:g} {unit_a}, enquanto "
                f"{product_b['product_name']} apresenta "
                f"{value_b:g} {unit_b}."
            )
        else:
            difference = (
                f"{nutrient}: {product_b['product_name']} apresenta "
                f"{value_b:g} {unit_b}, enquanto "
                f"{product_a['product_name']} apresenta "
                f"{value_a:g} {unit_a}."
            )

        comparisons.append(difference)

    return comparisons


def comparison_agent_node(state: AgentState) -> dict:
    """
    Agente determinístico de comparação.

    Compara dados nutricionais previamente validados.
    Não utiliza LLM, não inventa valores e não determina
    qual produto é universalmente mais saudável.
    """
    comparison_data = state.get("comparison_data")
    existing_sources = state.get("matched_sources", [])
    existing_warnings = state.get("warnings", [])

    products = _get_validated_products(comparison_data)

    if products is None:
        return {
            "draft_response": (
                "Não foi possível realizar a comparação. "
                "São necessários dados nutricionais validados "
                "de exatamente dois produtos, com a mesma base "
                "de comparação e informações de origem."
            ),
            "comparison_data": comparison_data,
            "matched_sources": existing_sources,
            "warnings": existing_warnings + [
                "Comparação não realizada: dados dos produtos "
                "ausentes, incompletos ou não validados."
            ],
            "classification_tone": "INCONCLUSIVO"
        }

    product_a, product_b = products

    comparisons = _compare_nutrients(product_a, product_b)

    if not comparisons:
        return {
            "draft_response": (
                "Os dados dos dois produtos foram recebidos, mas "
                "não existem nutrientes em comum com valores e "
                "unidades válidos para realizar a comparação."
            ),
            "comparison_data": comparison_data,
            "matched_sources": existing_sources,
            "warnings": existing_warnings + [
                "Não foram encontrados dados nutricionais "
                "comparáveis entre os produtos."
            ],
            "classification_tone": "INCONCLUSIVO"
        }

    basis = comparison_data["basis"]

    explanation = [
        f"Comparação entre {product_a['product_name']} e "
        f"{product_b['product_name']}.",
        f"Base de comparação: {basis}.",
        "",
        "Diferenças encontradas:"
    ]

    explanation.extend(
        f"- {comparison}" for comparison in comparisons
    )

    explanation.extend([
        "",
        "Esta comparação apresenta diferenças numéricas entre "
        "os dados fornecidos. Ela não determina, por si só, "
        "qual produto é mais saudável ou mais adequado para "
        "uma condição de saúde específica."
    ])

    warnings = list(existing_warnings)

    warnings.append(
        "Comparação descritiva: não foram aplicados limites "
        "nutricionais ou critérios regulatórios."
    )

    if not existing_sources:
        warnings.append(
            "Nenhuma fonte documental do RAG foi disponibilizada "
            "para fundamentar recomendações nutricionais."
        )

    return {
        "comparison_data": comparison_data,
        "draft_response": "\n".join(explanation),
        "matched_sources": existing_sources,
        "warnings": warnings,
        "classification_tone": "INCONCLUSIVO"
    }
