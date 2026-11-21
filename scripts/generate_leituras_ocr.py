#!/usr/bin/env python3
"""Pipeline CLI de extração de rótulos por OCR e geração de `leituras.csv` (ADR-002 / Issue #8 — R4).

Gera `leituras.csv` no formato exigido pela Seção 5 de `mlops/experiments/testset/protocolo_fotos.md`
(`motor,foto_id,tempo_ms,valor_energetico_kcal,...,alergicos_pode_conter`) para cada motor testado
(`tesseract`, `paddleocr`, `gemini` ou textos brutos de OCR em JSON/diretório).

Regras garantidas:
- Pré-processamento OpenCV (escala de cinza + binarização adaptativa/Otsu) quando `cv2` está disponível.
- Extração determinística por regex dos 10 nutrientes da RDC 429/2020 (por 100 g/ml), porção e linha ALÉRGICOS.
- Campo não encontrado permanece vazio (`""`), nunca `0`.

Exemplos de uso:
  # 1. A partir de diretório de fotos reais (ex.: testset/fotos/)
  python3 scripts/generate_leituras_ocr.py --fotos-dir mlops/experiments/testset/fotos \
      --motors tesseract paddleocr --out mlops/experiments/results/ocr_v1/leituras.csv

  # 2. A partir de arquivo JSON com textos brutos de OCR por motor e foto_id
  python3 scripts/generate_leituras_ocr.py --ocr-json leituras_brutas.json \
      --out mlops/experiments/results/ocr_v1/leituras.csv
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
for candidate in (REPO_ROOT / "backend", Path("/app")):
    if candidate.exists() and str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from ocr_extraction import (  # noqa: E402
    build_leitura_csv_row,
    extract_label_fields,
    write_leituras_csv,
)


def preprocess_image_opencv(image_path: Path) -> Path:
    """Aplica pré-processamento leve com OpenCV se instalado; retorna caminho da imagem."""
    try:
        import cv2  # type: ignore

        img = cv2.imread(str(image_path))
        if img is None:
            return image_path
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        tmp_out = Path(f"/tmp/berkanan_ocr_{image_path.stem}.png")
        cv2.imwrite(str(tmp_out), thresh)
        return tmp_out
    except Exception:
        return image_path


def run_ocr_engine(motor: str, image_path: Path) -> str:
    """Executa o motor de OCR solicitado (`tesseract` ou `paddleocr`) sobre a imagem."""
    proc_path = preprocess_image_opencv(image_path)
    try:
        if motor == "tesseract":
            try:
                import pytesseract  # type: ignore
                from PIL import Image  # type: ignore

                return str(pytesseract.image_to_string(Image.open(proc_path), lang="por"))
            except ImportError:
                res = subprocess.run(
                    ["tesseract", str(proc_path), "stdout", "-l", "por"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                return res.stdout

        if motor == "paddleocr":
            from paddleocr import PaddleOCR  # type: ignore

            ocr = PaddleOCR(use_angle_cls=True, lang="pt", show_log=False)
            result = ocr.ocr(str(proc_path), cls=True)
            lines: list[str] = []
            for page in result or []:
                for item in page or []:
                    if len(item) >= 2 and item[1]:
                        lines.append(str(item[1][0]))
            return "\n".join(lines)

        raise RuntimeError(f"Motor OCR '{motor}' não suportado ou não configurado localmente.")
    finally:
        if proc_path != image_path and proc_path.exists():
            proc_path.unlink(missing_ok=True)


def process_from_ocr_json(json_path: Path) -> list[dict[str, str]]:
    """Processa textos brutos de OCR de um JSON (lista de `{motor, foto_id, texto, tempo_ms?}`)."""
    items: list[dict[str, Any]] = json.loads(json_path.read_text(encoding="utf-8"))
    rows: list[dict[str, str]] = []
    for item in items:
        motor = str(item.get("motor", "tesseract"))
        foto_id = str(item["foto_id"])
        raw_text = str(item.get("texto", ""))
        t0 = time.perf_counter()
        extracted = extract_label_fields(raw_text)
        elapsed_ms = item.get("tempo_ms")
        if elapsed_ms is None:
            elapsed_ms = max(1, round((time.perf_counter() - t0) * 1000))
        rows.append(build_leitura_csv_row(motor, foto_id, elapsed_ms, extracted))
    return rows


def process_from_fotos_dir(fotos_dir: Path, motors: list[str]) -> list[dict[str, str]]:
    """Executa cada motor sobre todas as fotos (`.jpg`, `.jpeg`, `.png`) do diretório."""
    image_files = sorted(
        p for p in fotos_dir.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    rows: list[dict[str, str]] = []
    for motor in motors:
        for img_path in image_files:
            foto_id = img_path.stem
            t0 = time.perf_counter()
            raw_text = run_ocr_engine(motor, img_path)
            extracted = extract_label_fields(raw_text)
            elapsed_ms = max(1, round((time.perf_counter() - t0) * 1000))
            rows.append(build_leitura_csv_row(motor, foto_id, elapsed_ms, extracted))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fotos-dir", type=Path, help="Diretório com as fotos dos rótulos")
    parser.add_argument(
        "--motors",
        nargs="+",
        default=["tesseract", "paddleocr"],
        help="Motores de OCR a executar sobre --fotos-dir",
    )
    parser.add_argument(
        "--ocr-json",
        type=Path,
        help="Arquivo JSON com textos brutos de OCR [{motor, foto_id, texto, tempo_ms?}]",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Caminho de saída do arquivo leituras.csv",
    )
    args = parser.parse_args(argv)

    if args.ocr_json:
        rows = process_from_ocr_json(args.ocr_json)
    elif args.fotos_dir:
        rows = process_from_fotos_dir(args.fotos_dir, args.motors)
    else:
        parser.error("Informe --fotos-dir ou --ocr-json.")
        return 2

    write_leituras_csv(rows, args.out)
    print(f"[OK] {len(rows)} leituras gravadas em {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
