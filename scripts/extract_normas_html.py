#!/usr/bin/env python3
"""Extrator determinístico de normas oficiais em HTML (DOU / Planalto) e limpeza de PDFs (R4).

Atende às issues #27, #20 e #6:
1. Extrai IN 75/2020, RDC 429/2020 e RDC 727/2022 a partir do HTML oficial do
   Diário Oficial da União (`<div class="texto-dou">`), preservando todas as
   tabelas célula por célula associadas aos cabeçalhos de coluna (corrigindo
   a tabela do Anexo XV da IN 75/2020 que ficava embaralhada na extração por PDF).
2. Extrai a Lei nº 10.674/2003 (obrigatoriedade de "contém Glúten" / "não contém Glúten")
   a partir do HTML oficial do Planalto.
3. Organiza as normas HTML por unidade normativa de citação (`Art. N` ou `Anexo X`),
   mantendo compatibilidade com o contrato JSON de `data/fontes_rag/*.json`
   (`documento`, `arquivo`, `link`, `unidade_citacao_tipo`, `total_paginas`, `paginas`).
4. Remove cabeçalhos repetitivos e números de página isolados dos JSONs extraídos
   de PDF (`guia_alimentar_2ed.json`, `oms_sugars_2015.json`, `oms_sodium_2012.json`).
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
FONTES_RAG_DIR = REPO_ROOT / "data" / "fontes_rag"
DEFAULT_HTML_CACHE = Path("/tmp/normas_html")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

NORMAS_HTML_SPECS: list[dict[str, str]] = [
    {
        "slug": "in_75_2020",
        "html_file": "in_75_2020.html",
        "json_file": "in_75_2020.json",
        "documento": "IN 75/2020",
        "arquivo": "in_75_2020_dou.html",
        "link": "https://www.in.gov.br/en/web/dou/-/instrucao-normativa-in-n-75-de-8-de-outubro-de-2020-282071143",
        "parser": "dou",
    },
    {
        "slug": "rdc_429_2020",
        "html_file": "rdc_429_2020.html",
        "json_file": "rdc_429_2020.json",
        "documento": "RDC 429/2020",
        "arquivo": "rdc_429_2020_dou.html",
        "link": "https://www.in.gov.br/en/web/dou/-/resolucao-de-diretoria-colegiada-rdc-n-429-de-8-de-outubro-de-2020-282070599",
        "parser": "dou",
    },
    {
        "slug": "rdc_727_2022",
        "html_file": "rdc_727_2022.html",
        "json_file": "rdc_727_2022.json",
        "documento": "RDC 727/2022",
        "arquivo": "rdc_727_2022_dou.html",
        "link": "https://www.in.gov.br/en/web/dou/-/resolucao-rdc-n-727-de-1-de-julho-de-2022-413249279",
        "parser": "dou",
    },
    {
        "slug": "lei_10674_2003",
        "html_file": "lei_10674_2003.html",
        "json_file": "lei_10674_2003.json",
        "documento": "Lei 10.674/2003",
        "arquivo": "lei_10674_2003_planalto.html",
        "link": "https://www.planalto.gov.br/ccivil_03/leis/2003/l10.674.htm",
        "parser": "planalto",
    },
]


def _normalize_ws(text: str) -> str:
    text = unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


class DOUContentParser(HTMLParser):
    """Extrai parágrafos e tabelas estruturadas de `<div class="texto-dou">`."""

    def __init__(self) -> None:
        super().__init__()
        self.in_texto_dou = False
        self.div_depth = 0
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.in_p = False
        self.blocks: list[tuple[str, Any]] = []
        self.cur_p: list[str] = []
        self.cur_table: list[list[str]] = []
        self.cur_row: list[str] = []
        self.cur_cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        if tag == "div" and "texto-dou" in ad.get("class", ""):
            self.in_texto_dou = True
            self.div_depth = 1
            return
        if not self.in_texto_dou:
            return
        if tag == "div":
            self.div_depth += 1
        elif tag == "table":
            self.in_table = True
            self.cur_table = []
        elif tag == "tr" and self.in_table:
            self.in_row = True
            self.cur_row = []
        elif tag in ("td", "th") and self.in_row:
            self.in_cell = True
            self.cur_cell = []
        elif tag == "p" and not self.in_table:
            self.in_p = True
            self.cur_p = []

    def handle_endtag(self, tag: str) -> None:
        if not self.in_texto_dou:
            return
        if tag == "div":
            self.div_depth -= 1
            if self.div_depth <= 0:
                self.in_texto_dou = False
        elif tag == "table" and self.in_table:
            self.in_table = False
            if self.cur_table:
                self.blocks.append(("table", self.cur_table))
        elif tag == "tr" and self.in_row:
            self.in_row = False
            if any(c.strip() for c in self.cur_row):
                self.cur_table.append(self.cur_row)
        elif tag in ("td", "th") and self.in_cell:
            self.in_cell = False
            self.cur_row.append(_normalize_ws("".join(self.cur_cell)))
        elif tag == "p" and self.in_p and not self.in_table:
            self.in_p = False
            txt = _normalize_ws("".join(self.cur_p))
            if txt:
                self.blocks.append(("p", txt))

    def handle_data(self, data: str) -> None:
        if not self.in_texto_dou:
            return
        if self.in_cell:
            self.cur_cell.append(data)
        elif self.in_p:
            self.cur_p.append(data)


def format_table_rows(rows: list[list[str]]) -> list[str]:
    """Formata linhas de tabela associando cabeçalhos às células de cada linha."""
    cleaned_rows = [[c for c in r if c] if len(r) == 1 else r for r in rows]
    cleaned_rows = [r for r in cleaned_rows if any(c.strip() for c in r)]
    if not cleaned_rows:
        return []

    first = cleaned_rows[0]
    has_multi_col = len(first) >= 2 and all(len(c) < 80 for c in first)
    lines: list[str] = []

    if has_multi_col and len(cleaned_rows) > 1:
        headers = [c.strip() for c in first]
        lines.append(" | ".join(headers))
        for row in cleaned_rows[1:]:
            if len(row) == len(headers) and len(headers) >= 2:
                parts = [
                    f"{headers[i]}: {row[i]}"
                    for i in range(len(headers))
                    if row[i].strip()
                ]
                if parts:
                    lines.append(" — ".join(parts))
            else:
                non_empty = [c.strip() for c in row if c.strip()]
                if non_empty:
                    lines.append(" | ".join(non_empty))
    else:
        for row in cleaned_rows:
            non_empty = [c.strip() for c in row if c.strip()]
            if non_empty:
                lines.append(" | ".join(non_empty))
    return lines


def segment_dou_blocks(documento: str, blocks: list[tuple[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa blocos do DOU por unidade normativa de citação (Artigo ou Anexo)."""
    units: list[tuple[str, list[str]]] = []
    current_label = "Preâmbulo"
    current_lines: list[str] = []
    context_heading = ""
    inside_alteration_quote = False
    inside_anexo = False

    art_re = re.compile(r"^Art\.\s*(\d+[º°]?(?:-[A-Z])?)\b")
    anexo_re = re.compile(r"^ANEXO\s+([IVXLCDM]+)\b", re.IGNORECASE)
    cap_sec_re = re.compile(r"^(CAPÍTULO\s+[IVXLCDM]+|Seção\s+[IVXLCDM]+)\b", re.IGNORECASE)

    def flush() -> None:
        nonlocal current_lines
        text = "\n".join(line for line in current_lines if line.strip()).strip()
        if text:
            units.append((current_label, [text]))
        current_lines = []

    for btype, content in blocks:
        if btype == "p":
            line = str(content).strip()
            if not line:
                continue

            m_anexo = anexo_re.match(line)
            if m_anexo:
                flush()
                inside_anexo = True
                inside_alteration_quote = False
                current_label = f"Anexo {m_anexo.group(1).upper()}"
                current_lines.append(f"[{documento} - {current_label}] {line}")
                continue

            if not inside_anexo:
                m_cap = cap_sec_re.match(line)
                if m_cap:
                    context_heading = line
                    current_lines.append(line)
                    continue

                # Artigos entre aspas são alterações de outras normas (ex.: Art. 41..49 da RDC 429)
                if line.startswith('"Art.') or line.startswith("“Art."):
                    inside_alteration_quote = True

                m_art = art_re.match(line)
                if m_art and not inside_alteration_quote:
                    flush()
                    art_num = m_art.group(1)
                    current_label = f"Art. {art_num}"
                    prefix = f"[{documento} - {current_label}"
                    if context_heading:
                        prefix += f" ({context_heading})"
                    prefix += "]"
                    current_lines.append(f"{prefix} {line}")
                    continue

                if inside_alteration_quote and (line.endswith('(NR)') or line.endswith('"(NR)') or line.endswith('” (NR)')):
                    inside_alteration_quote = False

            current_lines.append(line)
        elif btype == "table":
            table_lines = format_table_rows(content)
            if table_lines:
                current_lines.extend(table_lines)

    flush()

    paginas: list[dict[str, Any]] = []
    for idx, (label, lines) in enumerate(units, 1):
        paginas.append(
            {
                "pagina": idx,
                "unidade_citacao": label,
                "texto": "\n".join(lines),
            }
        )
    return paginas


def parse_planalto_lei_10674(documento: str, html: str) -> list[dict[str, Any]]:
    """Extrai os artigos da Lei 10.674/2003 do HTML do Planalto."""
    # Remove scripts/styles e extrai parágrafos
    cleaned = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    raw_ps = re.findall(r"<p[^>]*>(.*?)</p>", cleaned, flags=re.S | re.I)
    paragraphs: list[str] = []
    for p in raw_ps:
        txt = _normalize_ws(re.sub(r"<[^>]+>", "", p))
        if txt:
            paragraphs.append(txt)

    units: list[tuple[str, list[str]]] = []
    current_label = "Preâmbulo"
    current_lines: list[str] = []
    art_re = re.compile(r"^Art\.\s*(\d+)\s*(?:o|º|°)?\b")

    def flush() -> None:
        nonlocal current_lines
        if current_lines:
            units.append((current_label, list(current_lines)))
            current_lines = []

    for p in paragraphs:
        m = art_re.match(p)
        if m:
            flush()
            art_num = m.group(1)
            current_label = f"Art. {art_num}º"
            norm_p = re.sub(r"^Art\.\s*(\d+)\s*o\b", r"Art. \1º", p)
            current_lines.append(f"[{documento} - {current_label}] {norm_p}")
        else:
            norm_p = re.sub(r"^§\s*(\d+)\s*o\b", r"§ \1º", p)
            current_lines.append(norm_p)
    flush()

    paginas: list[dict[str, Any]] = []
    for idx, (label, lines) in enumerate(units, 1):
        paginas.append(
            {
                "pagina": idx,
                "unidade_citacao": label,
                "texto": "\n".join(lines),
            }
        )
    return paginas


def download_or_load_html(url: str, cache_path: Path) -> str:
    """Lê o HTML do cache local ou baixa diretamente da fonte oficial."""
    if cache_path.exists() and cache_path.stat().st_size > 1000:
        return cache_path.read_text(encoding="utf-8")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    raw = urllib.request.urlopen(req, timeout=25).read()
    text = ""
    for enc in ("utf-8", "iso-8859-1", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    cache_path.write_text(text, encoding="utf-8")
    return text


def clean_pdf_page_text(text: str) -> str:
    """Remove cabeçalhos repetitivos e números de página isolados de PDFs."""
    noise_patterns = [
        re.compile(r"^\s*\d{1,3}\s*$"),
        re.compile(r"^\s*MINISTÉRIO DA SAÚDE\s*$", re.IGNORECASE),
        re.compile(r"^\s*GUIA ALIMENTAR PARA A POPULAÇÃO BRASILEIRA\s*$", re.IGNORECASE),
        re.compile(r"^\s*WHO\s*\|\s*Guideline.*$", re.IGNORECASE),
    ]
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if any(pat.match(line) for pat in noise_patterns):
            continue
        cleaned_lines.append(line)
    out = "\n".join(cleaned_lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out


def clean_existing_pdf_jsons(fontes_dir: Path) -> None:
    """Limpa cabeçalhos e números de página dos JSONs extraídos de PDF."""
    for fname in ("guia_alimentar_2ed.json", "oms_sugars_2015.json", "oms_sodium_2012.json"):
        fpath = fontes_dir / fname
        if not fpath.exists():
            continue
        data = json.loads(fpath.read_text(encoding="utf-8"))
        for entry in data.get("paginas", []):
            raw_txt = str(entry.get("texto", ""))
            cleaned = clean_pdf_page_text(raw_txt)
            entry["texto"] = cleaned if cleaned else raw_txt.strip()
        fpath.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[OK] PDF limpo: {fname} ({len(data.get('paginas', []))} páginas)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", type=Path, default=DEFAULT_HTML_CACHE)
    ap.add_argument("--out-dir", type=Path, default=FONTES_RAG_DIR)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for spec in NORMAS_HTML_SPECS:
        html_path = args.cache_dir / spec["html_file"]
        html = download_or_load_html(spec["link"], html_path)

        if spec["parser"] == "dou":
            parser = DOUContentParser()
            parser.feed(html)
            paginas = segment_dou_blocks(spec["documento"], parser.blocks)
        else:
            paginas = parse_planalto_lei_10674(spec["documento"], html)

        payload = {
            "documento": spec["documento"],
            "arquivo": spec["arquivo"],
            "link": spec["link"],
            "unidade_citacao_tipo": "artigo_ou_anexo",
            "total_paginas": len(paginas),
            "paginas": paginas,
        }
        out_path = args.out_dir / spec["json_file"]
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            f"[OK] {spec['documento']} -> {out_path.name} "
            f"({len(paginas)} unidades normativas extraídas do HTML oficial)"
        )

    clean_existing_pdf_jsons(args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
