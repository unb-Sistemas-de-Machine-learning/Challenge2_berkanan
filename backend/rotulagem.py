"""Cálculo determinístico do "ALTO EM" (rotulagem nutricional frontal, IN 75/2020, Anexo XV).

Regra 3 do projeto: todo número vem da base estruturada via código; o LLM só explica.
Este módulo não chama LLM. Os agentes (nutricional e de comparação) devem usá-lo em vez
de reimplementar a regra.

Valores de entrada sempre por 100 g (sólidos ou semissólidos) ou 100 ml (líquidos):
    carboidratos, acucares_totais, acucares_adicionados, gorduras_saturadas (g) e sodio (mg).
Valor ausente (None) significa "não lido" e nunca é tratado como 0.

Fora do escopo por enquanto: exceções do Anexo XVI (queijos, leites etc.), issue #21.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("berkanan.rotulagem")

NUTRIENTES_ALTO_EM = ("acucares_adicionados", "gorduras_saturadas", "sodio")
TIPOS = ("solido", "liquido")
FONTE = "IN 75/2020, Anexo XV"

# Categorias selecionáveis pelo usuário na confirmação dos valores. Estou adicionando elas pois optei por acrescentar um agrupamento que identifica explicitamente os itens 11 a 18 do Anexo XVI.
CATEGORIAS_PRODUTO = (
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
)

# Itens 1 a 6: a aplicação da rotulagem depende da composição
# e da análise dos ingredientes adicionados.
CATEGORIAS_CONDICIONAIS_ANEXO_XVI = {
    "queijo",
    "leite_fermentado",
    "ovos",
    "carne_peixe",
    "frutas_vegetais_cereais_castanhas",
    "farinha",
}

# Itens 7 a 18: não declarar ALTO EM.
CATEGORIAS_VEDADAS_ANEXO_XVI = {
    "leite",
    "oleo_azeite",
    "sal",
    "anexo_xvi_itens_11_18",
}

# Mensagens de retorno para o usuário quando a categoria do produto estiver em uma das listas acima.
AVISO_ANEXO_XVI_CONDICIONAL = (
    "A norma não permite o selo neste tipo de alimento, exceto quando "
    "há ingredientes adicionados que alteram o nutriente; confira a "
    "lista de ingredientes."
)

AVISO_ANEXO_XVI_VEDACAO = (
    "Esta categoria está abrangida pelas disposições de vedação do "
    "Anexo XVI da IN 75/2020. O sistema não declara ALTO EM para "
    "este tipo de produto."
)

_TOLERANCIA = 1e-9  # só para erro de ponto flutuante na normalização (ex.: 6 / 30 * 100)

# Nomes usados na tabela limites_rotulagem (migração 008) -> nomes deste módulo.
_DB_NUTRIENTE = {"açúcares adicionados": "acucares_adicionados", "gorduras saturadas": "gorduras_saturadas", "sódio": "sodio"}
_DB_CATEGORIA = {"sólido": "solido", "líquido": "liquido"}


@dataclass(frozen=True)
class Limite:
    valor: float
    unidade: str
    trecho: str
    origem: str  # "postgresql" ou "reserva"


def _reserva(valor: float, unidade: str, tipo: str, texto: str) -> Limite:
    rotulo = "Alimentos sólidos ou semissólidos" if tipo == "solido" else "Alimentos líquidos"
    return Limite(valor, unidade, f'{FONTE} ({rotulo}): "{texto}"', "reserva")


# Mesmos valores e trechos literais da migração 008, para quando o banco estiver fora do ar.
LIMITES_RESERVA: dict[tuple[str, str], Limite] = {
    ("solido", "acucares_adicionados"): _reserva(15, "g", "solido", "Quantidade maior ou igual a 15 g de açúcares adicionados por 100 g do alimento."),
    ("liquido", "acucares_adicionados"): _reserva(7.5, "g", "liquido", "Quantidade maior ou igual a 7,5 g de açúcares adicionados por 100 ml do alimento."),
    ("solido", "gorduras_saturadas"): _reserva(6, "g", "solido", "Quantidade maior ou igual a 6 g de gorduras saturadas por 100 g do alimento."),
    ("liquido", "gorduras_saturadas"): _reserva(3, "g", "liquido", "Quantidade maior ou igual a 3 g de gorduras saturadas por 100 ml do alimento."),
    ("solido", "sodio"): _reserva(600, "mg", "solido", "Quantidade maior ou igual a 600 mg de sódio por 100 g do alimento."),
    ("liquido", "sodio"): _reserva(300, "mg", "liquido", "Quantidade maior ou igual a 300 mg de sódio por 100 ml do alimento."),
}


def carregar_limites(consulta: Optional[Callable[[], list[dict[str, Any]]]] = None) -> dict[tuple[str, str], Limite]:
    """Lê os 6 limites do PostgreSQL; completa com a reserva o que faltar (e registra no log)."""
    if consulta is None:
        try:
            from database import get_limites_rotulagem
            consulta = get_limites_rotulagem
        except Exception as exc:  # banco ou dependência indisponível
            logger.warning("Limites do banco indisponíveis (%s); usando a reserva da IN 75.", exc)
            return dict(LIMITES_RESERVA)

    limites: dict[tuple[str, str], Limite] = {}
    for row in consulta() or []:
        chave = (_DB_CATEGORIA.get(str(row.get("categoria", "")).strip()), _DB_NUTRIENTE.get(str(row.get("nutriente", "")).strip()))
        if None in chave or row.get("limite_100g") is None:
            continue
        limites[chave] = Limite(float(row["limite_100g"]), str(row.get("unidade") or LIMITES_RESERVA[chave].unidade),
                                str(row.get("trecho_norma") or LIMITES_RESERVA[chave].trecho), "postgresql")
    faltando = [k for k in LIMITES_RESERVA if k not in limites]
    if faltando:
        logger.warning("Limites ausentes no banco %s; usando a reserva da IN 75.", faltando)
        limites.update({k: LIMITES_RESERVA[k] for k in faltando})
    return limites


def normalizar_por_100(valor_porcao: float, tamanho_porcao: float) -> float:
    """Converte o valor declarado na porção para 100 g ou 100 ml (ex.: 6 g em 30 g -> 20 g)."""
    if tamanho_porcao is None or tamanho_porcao <= 0:
        raise ValueError("Tamanho da porção deve ser maior que zero.")
    if valor_porcao is None or valor_porcao < 0:
        raise ValueError("Valor da porção deve ser um número não negativo.")
    return valor_porcao * 100 / tamanho_porcao


def checar_consistencia(valores_100: dict[str, Optional[float]]) -> list[str]:
    """Checagem aprovada pelo grupo: açúcares totais <= carboidratos.

    As checagens extras sugeridas pelo R4 aguardam a decisão da issue #23.
    """
    problemas = []
    acucares, carboidratos = valores_100.get("acucares_totais"), valores_100.get("carboidratos")
    if acucares is not None and carboidratos is not None and acucares > carboidratos + _TOLERANCIA:
        problemas.append(
            f"Açúcares totais ({acucares:g} g) maiores que carboidratos ({carboidratos:g} g): "
            "a leitura do rótulo parece inconsistente. Confira os valores antes da análise."
        )
    return problemas


def classificar_alto_em(
    valores_100: dict[str, Optional[float]],
    tipo: str,
    limites: Optional[dict[tuple[str, str], Limite]] = None,
    *,
    categoria_produto: str = "outro",
) -> dict[str, Any]:
    """Classifica o produto quanto ao ALTO EM.

    Retorna `status = "confirmar_valores"` (sem classificar)
    quando a leitura é inconsistente.

    Categorias abrangidas pelo Anexo XVI recebem o tratamento
    específico definido pela norma.

    `alto` por nutriente: True, False ou None
    (valor não lido, não avaliado).
    """

    # 1. Validação do tipo de alimento.
    if tipo not in TIPOS:
        raise ValueError(
            f"tipo deve ser 'solido' ou 'liquido', recebido {tipo!r}."
        )

    # 2. Validação dos valores nutricionais.
    for nome, valor in valores_100.items():
        if valor is not None and valor < 0:
            raise ValueError(
                f"{nome} não pode ser negativo ({valor})."
            )

    # 3. Verificação da categoria do produto.
    # Categorias inválidas geram ValueError.
    # Categorias válidas podem retornar uma exceção ou None.
    excecao_anexo_xvi = _verificar_excecao_anexo_xvi(
        categoria_produto
    )

    # 4. Verificação de inconsistências nutricionais.
    inconsistencias = checar_consistencia(valores_100)

    resultado: dict[str, Any] = {
        "tipo": tipo,
        "base": "100 g" if tipo == "solido" else "100 ml",
        "fonte": FONTE,
        "inconsistencias": inconsistencias,
        "categoria_produto": categoria_produto,
    }

    # 5. Valores inconsistentes exigem confirmação.
    if inconsistencias:
        return {
            **resultado,
            "status": "confirmar_valores",
            "alto_em": [],
            "nao_avaliados": list(NUTRIENTES_ALTO_EM),
            "avaliacao": {},
        }

    # 6. Aplicação das exceções do Anexo XVI.
    if excecao_anexo_xvi is not None:
        return {
            **resultado,
            "status": "ok",
            "alto_em": [],
            "nao_avaliados": list(NUTRIENTES_ALTO_EM),
            "avaliacao": {},
            **excecao_anexo_xvi,
        }

    # 7. Regra original do Anexo XV.
    # Para "outro", o comportamento permanece o mesmo.
    limites = limites or carregar_limites()

    avaliacao = {}

    for nutriente in NUTRIENTES_ALTO_EM:
        limite = limites[(tipo, nutriente)]
        valor = valores_100.get(nutriente)

        avaliacao[nutriente] = {
            "valor": valor,
            "limite": limite.valor,
            "unidade": limite.unidade,
            "alto": (
                None
                if valor is None
                else valor + _TOLERANCIA >= limite.valor
            ),
            "trecho_norma": limite.trecho,
            "origem_limite": limite.origem,
        }

    return {
        **resultado,
        "status": "ok",
        "alto_em": [
            n for n, a in avaliacao.items() if a["alto"]
        ],
        "nao_avaliados": [
            n for n, a in avaliacao.items() if a["alto"] is None
        ],
        "avaliacao": avaliacao,
    }

# Função auxiliar para implementação do Anexo XVI
def _verificar_excecao_anexo_xvi(
    categoria_produto: str,
) -> Optional[dict[str, Any]]:
    """Verifica se a categoria selecionada está abrangida pelo Anexo XVI.

    Retorna informações sobre a exceção quando aplicável.
    Retorna None quando a regra normal do Anexo XV deve ser aplicada.
    """

    # Primeiro, valida se a categoria é reconhecida.
    if categoria_produto not in CATEGORIAS_PRODUTO:
        raise ValueError(
            f"categoria_produto inválida: {categoria_produto!r}."
        )

    # Verifica categorias condicionais (itens 1 a 6).
    if categoria_produto in CATEGORIAS_CONDICIONAIS_ANEXO_XVI:
        return {
            "regra_anexo_xvi": "condicional",
            "aviso": AVISO_ANEXO_XVI_CONDICIONAL,
        }

    # Verifica categorias com vedação (itens 7 a 18).
    if categoria_produto in CATEGORIAS_VEDADAS_ANEXO_XVI:
        return {
            "regra_anexo_xvi": "vedacao",
            "aviso": AVISO_ANEXO_XVI_VEDACAO,
        }

    # Categoria "outro": segue a regra normal do Anexo XV.
    return None