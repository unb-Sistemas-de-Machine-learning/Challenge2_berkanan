"""Regras determinísticas de extração do OCR, alergênicos e consistência (ADR-002 / Issue #8 — R4).

Extrai do texto bruto de OCR (Tesseract, PaddleOCR ou reserva multimodal):
1. Os 10 nutrientes da tabela de informação nutricional (RDC 429/2020, art. 5º e 8º)
   na coluna por 100 g ou 100 ml e o tamanho da porção (`porcao_g`).
2. As declarações obrigatórias da seção "ALÉRGICOS: CONTÉM ..." e "PODE CONTER ..."
   (RDC 727/2022, arts. 13 e 14), normalizadas para nomes simples separados por `;`.
3. Normalização opcional por 100 g/ml quando apenas o valor por porção estiver disponível.
4. Checagens determinísticas de consistência (regra obrigatória:
   `acucares_totais_g <= carboidratos_g` e `acucares_adicionados_g <= acucares_totais_g`;
   checagens extras configuráveis conforme a issue #23).
5. Formatação de linhas no contrato de `leituras.csv` (`mlops/experiments/testset/protocolo_fotos.md`, seção 5):
   **campo não encontrado permanece vazio (`""` / `None`), nunca `0`**.
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from pathlib import Path
from typing import Any

NUMERIC_FIELDS: list[str] = [
    "valor_energetico_kcal",
    "carboidratos_g",
    "acucares_totais_g",
    "acucares_adicionados_g",
    "proteinas_g",
    "gorduras_totais_g",
    "gorduras_saturadas_g",
    "gorduras_trans_g",
    "fibra_alimentar_g",
    "sodio_mg",
    "porcao_g",
]

ALLERGEN_FIELDS: list[str] = [
    "alergicos_contem",
    "alergicos_pode_conter",
]

LEITURAS_CSV_COLUMNS: list[str] = [
    "motor",
    "foto_id",
    "tempo_ms",
    *NUMERIC_FIELDS,
    *ALLERGEN_FIELDS,
]

# Padrões de rótulos nutricionais segundo a RDC 429/2020 (sem acentos, lowercase)
_NUTRIENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "valor_energetico_kcal",
        re.compile(r"\b(?:valor\s*energetico|energia|calorias)\b", re.IGNORECASE),
    ),
    (
        "carboidratos_g",
        re.compile(r"\bcarboidratos?(?:\s*totais)?\b", re.IGNORECASE),
    ),
    (
        "acucares_totais_g",
        re.compile(r"\bacucares?\s*totais\b", re.IGNORECASE),
    ),
    (
        "acucares_adicionados_g",
        re.compile(r"\bacucares?\s*adicionados?\b", re.IGNORECASE),
    ),
    (
        "proteinas_g",
        re.compile(r"\bproteinas?\b", re.IGNORECASE),
    ),
    (
        "gorduras_totais_g",
        re.compile(r"\bgorduras?\s*totais\b", re.IGNORECASE),
    ),
    (
        "gorduras_saturadas_g",
        re.compile(r"\bgorduras?\s*saturadas?\b", re.IGNORECASE),
    ),
    (
        "gorduras_trans_g",
        re.compile(r"\bgorduras?\s*trans\b", re.IGNORECASE),
    ),
    (
        "fibra_alimentar_g",
        re.compile(r"\bfibras?\s*alimentar(?:es)?\b", re.IGNORECASE),
    ),
    (
        "sodio_mg",
        re.compile(r"\bsodio\b", re.IGNORECASE),
    ),
]

_PORTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\bporcao(?:\s*de)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:g|ml|gramas|mililitros)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bporcoes\s*por\s*embalagem[^\n]*?\bporcao\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:g|ml)\b",
        re.IGNORECASE,
    ),
]

_ZERO_PHRASE_RE = re.compile(
    r"\b(?:nao\s+contem\s+quantidade\s+significativa|zero)\b",
    re.IGNORECASE,
)

# Número com possível separador de milhar (ex.: 1.200) ou decimal (ex.: 4,5 / 4.5)
_NUMBER_TOKEN_RE = re.compile(
    r"(?<![a-zA-Z0-9])(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)\s*(kcal|kj|mg|g|ml|%)?(?![a-zA-Z0-9])",
    re.IGNORECASE,
)


def _strip_accents(text: str) -> str:
    normed = unicodedata.normalize("NFKD", text)
    return normed.encode("ascii", "ignore").decode("ascii")


def _clean_ocr_numeric_line(line: str) -> str:
    """Corrige trocas comuns de OCR entre dígitos (ex.: '1O0' -> '100', 'O,5' -> '0,5')."""
    # O/o entre dígitos ou antes de vírgula decimal
    line = re.sub(r"(?<=\d)[Oo](?=\d|\b|[.,])", "0", line)
    line = re.sub(r"\b[Oo](?=[.,]\d)", "0", line)
    return line


def _parse_number_str(raw_num: str) -> float | None:
    """Converte token numérico para float, removendo separador de milhar (1.000 -> 1000)."""
    token = raw_num.strip()
    if not token:
        return None
    # Caso de separador de milhar: 1.000 ou 1.250 (ponto seguido de exatos 3 dígitos sem vírgula)
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        token = token.replace(".", "")
    else:
        token = token.replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def format_numeric_value(val: float | int | None) -> str:
    """Formata número sem separador de milhar e sem `.0` supérfluo; `None` vira `""`."""
    if val is None:
        return ""
    fval = float(val)
    if abs(fval - round(fval)) < 1e-6:
        return str(int(round(fval)))
    formatted = f"{fval:.2f}".rstrip("0").rstrip(".")
    return formatted


def normalizar_por_100g(valor_porcao: float | None, porcao_g: float | None) -> float | None:
    """Converte o valor nutricional da porção para a base de 100 g ou 100 ml."""
    if valor_porcao is None or porcao_g is None or porcao_g <= 0:
        return None
    return round((float(valor_porcao) * 100.0) / float(porcao_g), 2)


def _detect_column_order(ascii_text: str) -> str:
    """Detecta se o cabeçalho da tabela traz `100g` antes de `porcao` (padrão RDC 429) ou o inverso."""
    for line in ascii_text.splitlines():
        low = line.lower()
        if "100" in low and ("porcao" in low or "vd" in low):
            pos_100 = low.find("100")
            pos_porcao = low.find("porcao")
            if pos_porcao != -1 and pos_porcao < pos_100:
                return "porcao_first"
            return "100g_first"
    return "100g_first"


def _extract_numbers_from_nutrient_line(
    line_after_label: str,
    field_name: str,
    column_order: str,
) -> tuple[float | None, float | None]:
    """Extrai `(valor_100g, valor_porcao)` de uma linha de nutriente da tabela RDC 429."""
    cleaned = _clean_ocr_numeric_line(line_after_label)
    # Remove referências literais de cabeçalho "100 g" ou "100 ml" se repetidas na linha
    cleaned = re.sub(r"\bpor\s+100\s*(?:g|ml)\b", " ", cleaned, flags=re.IGNORECASE)

    if _ZERO_PHRASE_RE.search(cleaned):
        return 0.0, 0.0

    candidates: list[float] = []
    for match in _NUMBER_TOKEN_RE.finditer(cleaned):
        raw_num, unit = match.group(1), (match.group(2) or "").lower()
        # Ignora valores em kJ quando buscamos kcal e ignora coluna %VD
        if unit == "%":
            continue
        if field_name == "valor_energetico_kcal" and unit == "kj":
            continue
        parsed = _parse_number_str(raw_num)
        if parsed is not None:
            candidates.append(parsed)

    if not candidates:
        return None, None

    if len(candidates) == 1:
        return candidates[0], None

    if column_order == "porcao_first":
        return candidates[1], candidates[0]
    return candidates[0], candidates[1]


def _normalize_allergen_list(raw_segment: str) -> str:
    """Normaliza lista de alergênicos conforme seção 4 do protocolo_fotos.md.

    Exemplo:
      'LEITE E DERIVADOS, DERIVADOS DE TRIGO E SOJA.' -> 'leite; trigo; soja'
    """
    ascii_seg = _strip_accents(raw_segment).lower()
    # Corta no primeiro ponto final ou início de outra declaração ("pode conter", "contem gluten", "contem lactose")
    ascii_seg = re.split(
        r"\b(?:pode\s+conter|contem\s+gluten|nao\s+contem\s+gluten|contem\s+lactose|industria\s+brasileira)\b",
        ascii_seg,
    )[0]
    ascii_seg = ascii_seg.split(".")[0]

    # Remove expressões de derivados mantendo o nome do alimento base
    ascii_seg = re.sub(r"\bderivados\s+de\b", " ", ascii_seg)
    ascii_seg = re.sub(r"\be\s+seus\s+derivados\b", " ", ascii_seg)
    ascii_seg = re.sub(r"\be\s+derivados\b", " ", ascii_seg)
    ascii_seg = re.sub(r"\bderivados\b", " ", ascii_seg)
    ascii_seg = re.sub(r"\btracos\s+de\b", " ", ascii_seg)

    # Separa por vírgula, ponto e vírgula, barra ou conjunção ' e '
    raw_items = re.split(r"[,;/]|\s+e\s+", ascii_seg)
    cleaned_items: list[str] = []
    seen: set[str] = set()

    for item in raw_items:
        token = re.sub(r"[^a-z0-9\-\s]", " ", item)
        token = re.sub(r"\s+", " ", token).strip(" -")
        if not token or token in {"de", "da", "do", "das", "dos", "ou"}:
            continue
        if token not in seen:
            seen.add(token)
            cleaned_items.append(token)

    return "; ".join(cleaned_items)


def extract_allergens(ocr_text: str) -> dict[str, str]:
    """Extrai `alergicos_contem` e `alergicos_pode_conter` do texto bruto de OCR."""
    ascii_text = _strip_accents(ocr_text)
    flat = re.sub(r"\s+", " ", ascii_text)

    contem_val = ""
    pode_conter_val = ""

    # 1. Busca bloco iniciado por ALÉRGICOS:
    m_alergicos = re.search(
        r"\balergicos?\s*[:\-]?\s*(.+)",
        flat,
        flags=re.IGNORECASE,
    )
    search_scope = m_alergicos.group(1) if m_alergicos else flat

    # Extrai "CONTÉM ..." (cuidando para não capturar "CONTÉM GLÚTEN" ou "CONTÉM LACTOSE" fora de ALÉRGICOS)
    m_contem = re.search(
        r"\bcontem\s+(?!gluten\b|lactose\b)([^.]+?)(?=\.\s*|\bpode\s+conter\b|\bcontem\s+gluten\b|\bnao\s+contem\s+gluten\b|\bcontem\s+lactose\b|$)",
        search_scope,
        flags=re.IGNORECASE,
    )
    if m_contem and m_alergicos:
        contem_val = _normalize_allergen_list(m_contem.group(1))

    # Extrai "PODE CONTER ..."
    m_pode = re.search(
        r"\bpode\s+conter\s+([^.]+?)(?=\.\s*|\bcontem\s+gluten\b|\bnao\s+contem\s+gluten\b|\bcontem\s+lactose\b|$)",
        search_scope,
        flags=re.IGNORECASE,
    )
    if m_pode:
        pode_conter_val = _normalize_allergen_list(m_pode.group(1))

    return {
        "alergicos_contem": contem_val,
        "alergicos_pode_conter": pode_conter_val,
    }


def check_consistency(
    extracted: dict[str, Any],
    enable_extra_checks: bool = False,
) -> dict[str, Any]:
    """Executa checagens determinísticas de consistência nos valores extraídos (ADR-002 / Issue #23).

    - Regra obrigatória ativa (aprovada pelo grupo):
      `acucares_totais_g <= carboidratos_g` e `acucares_adicionados_g <= acucares_totais_g`
      (e `acucares_adicionados_g <= carboidratos_g`).
    - Regras extras opcionais (`enable_extra_checks=True`, issue #23):
      - `gorduras_saturadas_g + gorduras_trans_g <= gorduras_totais_g`
      - Balanço calórico de Atwater (`4*(carb + prot) + 9*gord_totais` dentro de ±25% ou ±25 kcal).
    """
    errors: list[str] = []

    def _get_float(key: str) -> float | None:
        v = extracted.get(key)
        if v is None or str(v).strip() == "":
            return None
        try:
            return float(str(v).replace(",", "."))
        except ValueError:
            return None

    carbs = _get_float("carboidratos_g")
    sugars_total = _get_float("acucares_totais_g")
    sugars_added = _get_float("acucares_adicionados_g")

    if sugars_total is not None and carbs is not None and sugars_total > carbs + 1e-6:
        errors.append(
            f"Inconsistência: açúcares totais ({sugars_total} g) > carboidratos ({carbs} g)."
        )

    if sugars_added is not None and sugars_total is not None and sugars_added > sugars_total + 1e-6:
        errors.append(
            f"Inconsistência: açúcares adicionados ({sugars_added} g) > açúcares totais ({sugars_total} g)."
        )

    if sugars_added is not None and carbs is not None and sugars_added > carbs + 1e-6:
        errors.append(
            f"Inconsistência: açúcares adicionados ({sugars_added} g) > carboidratos ({carbs} g)."
        )

    if enable_extra_checks:
        fat_total = _get_float("gorduras_totais_g")
        fat_sat = _get_float("gorduras_saturadas_g") or 0.0
        fat_trans = _get_float("gorduras_trans_g") or 0.0
        if fat_total is not None and (fat_sat + fat_trans) > fat_total + 1e-6:
            errors.append(
                f"Inconsistência extra: gorduras saturadas + trans ({fat_sat + fat_trans} g) > gorduras totais ({fat_total} g)."
            )

        kcal = _get_float("valor_energetico_kcal")
        prot = _get_float("proteinas_g")
        if kcal is not None and carbs is not None and prot is not None and fat_total is not None:
            atwater_kcal = 4.0 * (carbs + prot) + 9.0 * fat_total
            tolerance = max(25.0, 0.25 * max(kcal, atwater_kcal))
            if abs(kcal - atwater_kcal) > tolerance:
                errors.append(
                    f"Inconsistência extra (Atwater): valor energético lido ({kcal} kcal) diverge do estimado ({round(atwater_kcal, 1)} kcal)."
                )

    return {
        "consistency_passed": len(errors) == 0,
        "consistency_errors": errors,
        "requires_user_confirmation": True,
    }


def extract_label_fields(
    ocr_text: str,
    normalize_from_portion_if_missing: bool = False,
    enable_extra_checks: bool = False,
) -> dict[str, Any]:
    """Extrai todos os campos da RDC 429/2020 e alergênicos a partir do texto de OCR.

    Campo não encontrado retorna `None` nos campos numéricos e `""` na serialização CSV (nunca `0`).
    """
    ascii_text = _strip_accents(ocr_text)
    column_order = _detect_column_order(ascii_text)

    values_100g: dict[str, float | None] = {f: None for f in NUMERIC_FIELDS}
    values_portion: dict[str, float | None] = {f: None for f in NUMERIC_FIELDS}

    # 1. Porção em g ou ml
    for pat in _PORTION_PATTERNS:
        m_port = pat.search(ascii_text)
        if m_port:
            values_100g["porcao_g"] = _parse_number_str(m_port.group(1))
            break

    # 2. Linhas da tabela nutricional
    lines = [ln.strip() for ln in ascii_text.splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        for field_name, pat in _NUTRIENT_PATTERNS:
            if values_100g[field_name] is not None:
                continue
            m = pat.search(line)
            if not m:
                continue
            tail = line[m.end() :]
            v100, vpor = _extract_numbers_from_nutrient_line(tail, field_name, column_order)
            # Se o número quebrou para a linha seguinte no OCR
            if v100 is None and idx + 1 < len(lines):
                next_line = lines[idx + 1]
                if not any(p.search(next_line) for _, p in _NUTRIENT_PATTERNS):
                    v100, vpor = _extract_numbers_from_nutrient_line(next_line, field_name, column_order)
            if v100 is not None:
                values_100g[field_name] = v100
                values_portion[field_name] = vpor

    # 3. Normalização opcional por 100 g/ml caso apenas a porção tenha sido informada
    porcao_g = values_100g["porcao_g"]
    if normalize_from_portion_if_missing and porcao_g and porcao_g > 0:
        for field_name in NUMERIC_FIELDS:
            if field_name == "porcao_g":
                continue
            if values_100g[field_name] is None and values_portion[field_name] is not None:
                values_100g[field_name] = normalizar_por_100g(values_portion[field_name], porcao_g)

    allergens = extract_allergens(ocr_text)
    consistency = check_consistency(values_100g, enable_extra_checks=enable_extra_checks)

    return {
        **values_100g,
        **allergens,
        **consistency,
    }


def build_leitura_csv_row(
    motor: str,
    foto_id: str,
    tempo_ms: int | float,
    extracted: dict[str, Any],
) -> dict[str, str]:
    """Converte o dicionário extraído para uma linha do contrato `leituras.csv`.

    Garante que campos não encontrados fiquem como string vazia `""`, nunca `"0"`.
    """
    row: dict[str, str] = {
        "motor": str(motor).strip(),
        "foto_id": str(foto_id).strip(),
        "tempo_ms": format_numeric_value(round(float(tempo_ms))),
    }
    for field in NUMERIC_FIELDS:
        val = extracted.get(field)
        if val is None or str(val).strip() == "":
            row[field] = ""
        else:
            row[field] = format_numeric_value(float(str(val).replace(",", ".")))
    for afield in ALLERGEN_FIELDS:
        row[afield] = str(extracted.get(afield) or "").strip()
    return row


def write_leituras_csv(rows: list[dict[str, str]], output_path: str | Path | None = None) -> str:
    """Gera o conteúdo CSV no formato exato de `leituras_modelo.csv` e grava em disco se solicitado."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=LEITURAS_CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for r in rows:
        clean_row = {col: str(r.get(col, "") if r.get(col) is not None else "") for col in LEITURAS_CSV_COLUMNS}
        writer.writerow(clean_row)
    content = buf.getvalue()
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
    return content
