#!/usr/bin/env python3
"""Extrator determinístico e reproduzível da Tabela TACO (4ª ed., 2011) para SQL.

Lê o PDF oficial da TACO 4ª edição (hospedado pelo CFN) usando `pdftotext -bbox`
(coordenadas 2D x/y), evitando deslocamento de colunas por células vazias
(ex.: alimento nº 160 com manganês em branco).

Regras documentadas (conforme legendas das páginas 65 e 95 do PDF e migração 002):
- Vírgula decimal -> ponto decimal.
- "NA" (não aplicável) -> NULL (nunca 0).
- "Tr" (traço) -> NULL (nunca 0).
- "*" (análises sendo reavaliadas) -> NULL (nunca 0).
- Célula em branco ("†" análises não solicitadas ou ausente na Tabela 2) -> NULL.
- Cada alimento é unido pelo Número do Alimento entre:
  - Tabela 1 (página esquerda: centesimal; página direita: sódio);
  - Tabela 2 (ácidos graxos: coluna Saturados).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

TACO_CFN_URL = (
    "https://cfn.org.br/wp-content/uploads/2017/03/"
    "taco_4_edicao_ampliada_e_revisada.pdf"
)
FONTE_DOCUMENTO_NOME = "Tabela Brasileira de Composição de Alimentos (TACO)"
XHTML_NS = {"x": "http://www.w3.org/1999/xhtml"}

# Intervalos de páginas no PDF da 4ª edição (1-based)
TABELA1_LEFT_PAGES = range(29, 68, 2)   # 29, 31, ..., 67
TABELA1_RIGHT_PAGES = range(30, 69, 2)  # 30, 32, ..., 68
TABELA2_LEFT_PAGES = range(71, 100, 2)  # 71, 73, ..., 99

SPECIAL_NULL_TOKENS = {"", "NA", "Tr", "*"}
DECIMAL_RE = re.compile(r"^\d+(,\d+)?$")


@dataclass(frozen=True)
class WordBox:
    """Palavra extraída do PDF com centro e limites em pontos."""

    y_mid: float
    x_mid: float
    x_min: float
    x_max: float
    text: str


@dataclass
class TacoRecord:
    """Registro consolidado de um alimento da TACO por 100 g."""

    codigo_taco: str
    nome: str
    grupo: str
    energia_kcal: Decimal | None
    energia_kj: Decimal | None
    proteina_g: Decimal | None
    lipidios_g: Decimal | None
    saturados_g: Decimal | None
    carboidrato_g: Decimal | None
    fibra_g: Decimal | None
    sodio_mg: Decimal | None


def download_taco_pdf(dest: Path, url: str = TACO_CFN_URL) -> None:
    """Baixa o PDF oficial da TACO caso não seja fornecido localmente."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())


def run_pdftotext_bbox(pdf_path: Path) -> ET.Element:
    """Executa `pdftotext -bbox` e retorna a árvore XML das páginas."""
    proc = subprocess.run(
        ["pdftotext", "-bbox", str(pdf_path), "-"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return ET.fromstring(proc.stdout)


def group_page_lines(page: ET.Element) -> list[dict[str, Any]]:
    """Agrupa tokens da página em linhas ordenadas por y_mid e x_min."""
    words: list[WordBox] = []
    for elem in page.findall(".//x:word", XHTML_NS):
        if not elem.text:
            continue
        x0, x1 = float(elem.attrib["xMin"]), float(elem.attrib["xMax"])
        y0, y1 = float(elem.attrib["yMin"]), float(elem.attrib["yMax"])
        words.append(WordBox((y0 + y1) / 2.0, (x0 + x1) / 2.0, x0, x1, elem.text))

    words.sort(key=lambda w: (w.y_mid, w.x_min))
    lines: list[dict[str, Any]] = []
    for w in words:
        if lines and abs(w.y_mid - lines[-1]["y"]) < 4.0:
            lines[-1]["words"].append(w)
        else:
            lines.append({"y": w.y_mid, "words": [w]})

    for ln in lines:
        ln["words"].sort(key=lambda w: w.x_min)
    return lines


def assign_words_to_columns(
    words: list[WordBox], centers: list[float], min_x: float, max_dist: float = 22.0
) -> list[str]:
    """Atribui cada token ao centro de coluna mais próximo dentro de `max_dist`."""
    buckets: list[list[str]] = [[] for _ in centers]
    for w in words:
        if w.x_mid < min_x:
            continue
        dists = [abs(w.x_mid - c) for c in centers]
        best_idx = min(range(len(centers)), key=lambda i: dists[i])
        if dists[best_idx] > max_dist:
            raise ValueError(
                f"Token fora de coluna esperada: {w.text!r} em x={w.x_mid:.1f} "
                f"(distância mínima={dists[best_idx]:.1f})"
            )
        buckets[best_idx].append(w.text)
    return [" ".join(b).strip() for b in buckets]


def parse_taco_value(raw: str, context: str) -> Decimal | None:
    """Converte string da TACO em Decimal ou None para NA, Tr, * e vazio."""
    token = raw.strip()
    if token in SPECIAL_NULL_TOKENS:
        return None
    if not DECIMAL_RE.fullmatch(token):
        raise ValueError(f"Valor inesperado em {context}: {token!r}")
    return Decimal(token.replace(",", "."))


def _find_tabela1_left_headers(lines: list[dict[str, Any]]) -> tuple[float, list[float]]:
    hdr_y = max(ln["y"] for ln in lines if any("(kcal)" in w.text for w in ln["words"]))
    unit_line = next(ln for ln in lines if abs(ln["y"] - hdr_y) < 1.0)
    units = [w for w in unit_line["words"] if w.x_min > 360.0]
    if len(units) != 11:
        raise ValueError(f"Esperadas 11 colunas na Tabela 1 (esq.), obtidas {len(units)}")
    return hdr_y, [u.x_mid for u in units]


def _find_tabela1_right_headers(lines: list[dict[str, Any]]) -> tuple[float, list[float]]:
    hdr_y = max(ln["y"] for ln in lines if any("Manganês" in w.text for w in ln["words"]))
    unit_line = min((ln for ln in lines if ln["y"] > hdr_y + 4.0), key=lambda ln: ln["y"])
    units = [w for w in unit_line["words"] if w.x_min > 115.0]
    if len(units) != 15:
        raise ValueError(f"Esperadas 15 colunas na Tabela 1 (dir.), obtidas {len(units)}")
    return unit_line["y"], [u.x_mid for u in units]


def _find_tabela2_left_headers(lines: list[dict[str, Any]]) -> tuple[float, list[float]]:
    hdr_y = max(ln["y"] for ln in lines if any("turados" in w.text for w in ln["words"]))
    unit_line = min((ln for ln in lines if ln["y"] > hdr_y + 4.0), key=lambda ln: ln["y"])
    units = [w for w in unit_line["words"] if w.x_min > 360.0]
    if len(units) != 10:
        raise ValueError(f"Esperadas 10 colunas na Tabela 2 (esq.), obtidas {len(units)}")
    return unit_line["y"], [u.x_mid for u in units]


def extract_taco_records(root: ET.Element) -> list[TacoRecord]:
    """Extrai e consolida os 597 alimentos da TACO por 100 g."""
    pages = root.findall(".//x:page", XHTML_NS)
    if len(pages) < 100:
        raise ValueError(f"PDF inválido ou incompleto: {len(pages)} páginas encontradas")

    # 1. Tabela 1 (páginas esquerdas): nome, grupo e composição centesimal
    t1_left: dict[int, tuple[str, str, list[str]]] = {}
    current_group = ""
    for pno in TABELA1_LEFT_PAGES:
        lines = group_page_lines(pages[pno - 1])
        hdr_y, centers = _find_tabela1_left_headers(lines)
        for ln in lines:
            if ln["y"] <= hdr_y + 2.0 or ln["y"] > 518.0:
                continue
            ws: list[WordBox] = ln["words"]
            if ws[0].x_min < 115.0 and ws[0].text.isdigit():
                fid = int(ws[0].text)
                if not current_group:
                    raise ValueError(f"Alimento {fid} sem grupo definido na p.{pno}")
                nome = " ".join(w.text for w in ws[1:] if w.x_mid < 365.0)
                cols = assign_words_to_columns(ws, centers, min_x=365.0)
                t1_left[fid] = (nome, current_group, cols)
            elif ws[0].x_min < 115.0 and not ws[0].text.startswith(("*", "†")):
                current_group = " ".join(w.text for w in ws)

    # 2. Tabela 1 (páginas direitas): Sódio (índice 3)
    t1_sodium: dict[int, str] = {}
    for pno in TABELA1_RIGHT_PAGES:
        lines = group_page_lines(pages[pno - 1])
        hdr_y, centers = _find_tabela1_right_headers(lines)
        for ln in lines:
            if ln["y"] <= hdr_y + 2.0 or ln["y"] > 518.0:
                continue
            ws = ln["words"]
            if ws[0].x_min < 115.0 and ws[0].text.isdigit():
                fid = int(ws[0].text)
                cols = assign_words_to_columns(ws, centers, min_x=118.0)
                t1_sodium[fid] = cols[3]

    # 3. Tabela 2 (páginas esquerdas): Saturados (índice 0)
    t2_saturated: dict[int, tuple[str, str]] = {}
    for pno in TABELA2_LEFT_PAGES:
        lines = group_page_lines(pages[pno - 1])
        hdr_y, centers = _find_tabela2_left_headers(lines)
        for ln in lines:
            if ln["y"] <= hdr_y + 2.0 or ln["y"] > 518.0:
                continue
            ws = ln["words"]
            if ws[0].x_min < 115.0 and ws[0].text.isdigit():
                fid = int(ws[0].text)
                nome2 = " ".join(w.text for w in ws[1:] if w.x_mid < 365.0)
                cols = assign_words_to_columns(ws, centers, min_x=365.0)
                t2_saturated[fid] = (nome2, cols[0])

    if set(t1_left) != set(range(1, 598)) or set(t1_sodium) != set(range(1, 598)):
        raise ValueError(
            f"Cobertura incompleta da Tabela 1: esq={len(t1_left)}, dir={len(t1_sodium)}"
        )

    records: list[TacoRecord] = []
    for fid in range(1, 598):
        nome, grupo, cols = t1_left[fid]
        if fid in t2_saturated:
            nome2, raw_sat = t2_saturated[fid]
            norm1 = re.sub(r"\s+", "", nome.lower())
            norm2 = re.sub(r"\s+", "", nome2.lower())
            if norm1 != norm2:
                raise ValueError(f"Divergência T1/T2 no alimento {fid}: {nome!r} vs {nome2!r}")
        else:
            raw_sat = ""

        # Índices na Tabela 1 (esq.): 1=kcal, 2=kJ, 3=proteína, 4=lipídeos, 6=carboidrato, 7=fibra
        records.append(
            TacoRecord(
                codigo_taco=str(fid),
                nome=nome,
                grupo=grupo,
                energia_kcal=parse_taco_value(cols[1], f"fid={fid} kcal"),
                energia_kj=parse_taco_value(cols[2], f"fid={fid} kJ"),
                proteina_g=parse_taco_value(cols[3], f"fid={fid} proteina"),
                lipidios_g=parse_taco_value(cols[4], f"fid={fid} lipidios"),
                saturados_g=parse_taco_value(raw_sat, f"fid={fid} saturados"),
                carboidrato_g=parse_taco_value(cols[6], f"fid={fid} carboidrato"),
                fibra_g=parse_taco_value(cols[7], f"fid={fid} fibra"),
                sodio_mg=parse_taco_value(t1_sodium[fid], f"fid={fid} sodio"),
            )
        )
    return records


def _sql_str(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _sql_num(value: Decimal | None) -> str:
    return "NULL" if value is None else f"{value:.2f}"


def render_migration_sql(records: list[TacoRecord]) -> str:
    """Gera o SQL idempotente da migração 007_carga_taco.sql."""
    header = f"""-- ============================================================================
-- ARQUIVO: migrations/007_carga_taco.sql
-- DESCRIÇÃO: Carga completa e idempotente dos {len(records)} alimentos da TACO
--            (4ª edição revisada e ampliada, NEPA/UNICAMP, 2011) por 100 g.
--            Gerado de forma determinística a partir do PDF oficial por:
--            scripts/extract_taco_sql.py (pdftotext -bbox por coordenadas 2D).
--
-- REGRAS DE TRATAMENTO APLICADAS (LEGENDAS DO PDF, PÁGS. 65 E 95):
-- - Vírgula decimal convertida para ponto decimal.
-- - "NA" (não aplicável) -> NULL (nunca 0).
-- - "Tr" (traço / abaixo do limite de quantificação) -> NULL (nunca 0).
-- - "*" (análises sendo reavaliadas) -> NULL (nunca 0).
-- - Célula em branco ("†" análises não solicitadas / ausente na Tabela 2) -> NULL.
-- - Energia, proteína, lipídeos, carboidrato e fibra: Tabela 1 (pág. esquerda).
-- - Sódio: Tabela 1 (pág. direita), unido por Número do Alimento.
-- - Gordura saturada: Tabela 2 (ácidos graxos, coluna Saturados), unido por nº.
-- - A TACO não traz açúcares totais nem adicionados.
--
-- FONTE: {TACO_CFN_URL}
-- AUTOR: Davi Rodrigues (R4 Engenheiro de Dados) - Equipe Berkanan
-- ============================================================================

INSERT INTO taco_alimentos (
    codigo_taco,
    fonte_id,
    nome,
    grupo,
    energia_kcal,
    energia_kj,
    proteina_g,
    lipidios_g,
    saturados_g,
    carboidrato_g,
    fibra_g,
    sodio_mg
)
SELECT
    v.codigo_taco,
    f.id AS fonte_id,
    v.nome,
    v.grupo,
    v.energia_kcal,
    v.energia_kj,
    v.proteina_g,
    v.lipidios_g,
    v.saturados_g,
    v.carboidrato_g,
    v.fibra_g,
    v.sodio_mg
FROM (
    VALUES
"""

    rows = []
    for r in records:
        rows.append(
            "        ("
            f"{_sql_str(r.codigo_taco)}, "
            f"{_sql_str(r.nome)}, "
            f"{_sql_str(r.grupo)}, "
            f"{_sql_num(r.energia_kcal)}::numeric(8,2), "
            f"{_sql_num(r.energia_kj)}::numeric(8,2), "
            f"{_sql_num(r.proteina_g)}::numeric(8,2), "
            f"{_sql_num(r.lipidios_g)}::numeric(8,2), "
            f"{_sql_num(r.saturados_g)}::numeric(8,2), "
            f"{_sql_num(r.carboidrato_g)}::numeric(8,2), "
            f"{_sql_num(r.fibra_g)}::numeric(8,2), "
            f"{_sql_num(r.sodio_mg)}::numeric(8,2)"
            ")"
        )

    footer = f"""
) AS v(
    codigo_taco,
    nome,
    grupo,
    energia_kcal,
    energia_kj,
    proteina_g,
    lipidios_g,
    saturados_g,
    carboidrato_g,
    fibra_g,
    sodio_mg
)
CROSS JOIN (
    SELECT id
    FROM fontes_documentos
    WHERE documento = '{FONTE_DOCUMENTO_NOME}'
) AS f
ON CONFLICT (codigo_taco) DO UPDATE SET
    fonte_id = EXCLUDED.fonte_id,
    nome = EXCLUDED.nome,
    grupo = EXCLUDED.grupo,
    energia_kcal = EXCLUDED.energia_kcal,
    energia_kj = EXCLUDED.energia_kj,
    proteina_g = EXCLUDED.proteina_g,
    lipidios_g = EXCLUDED.lipidios_g,
    saturados_g = EXCLUDED.saturados_g,
    carboidrato_g = EXCLUDED.carboidrato_g,
    fibra_g = EXCLUDED.fibra_g,
    sodio_mg = EXCLUDED.sodio_mg,
    atualizado_em = CURRENT_TIMESTAMP;
"""
    return header + ",\n".join(rows) + footer


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extrai a TACO 4ª edição (por 100 g) e gera migrations/007_carga_taco.sql."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=None,
        help="Caminho local do PDF da TACO. Se omitido, baixa do link oficial do CFN.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "migrations" / "007_carga_taco.sql",
        help="Arquivo SQL de saída (padrão: migrations/007_carga_taco.sql).",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = args.pdf
        if pdf_path is None:
            pdf_path = Path(tmpdir) / "taco_4_edicao.pdf"
            print(f"[INFO] Baixando TACO oficial de {TACO_CFN_URL} ...")
            download_taco_pdf(pdf_path)

        root = run_pdftotext_bbox(pdf_path)
        records = extract_taco_records(root)
        sql_text = render_migration_sql(records)
        args.out.write_text(sql_text, encoding="utf-8")

        grupos = len({r.grupo for r in records})
        sat_present = sum(1 for r in records if r.saturados_g is not None)
        print(
            f"[OK] {len(records)} alimentos ({grupos} grupos; {sat_present} com saturados_g) "
            f"gravados em {args.out}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
