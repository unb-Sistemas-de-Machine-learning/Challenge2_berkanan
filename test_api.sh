#!/bin/bash

echo "--- TESTE 1: Com Verificador Ligado ---"
curl -s -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"request_type": "ocr_analysis", "enable_verifier": true, "user_profile": {"has_diabetes": true}}' | python3 -m json.tool

echo -e "\n--- TESTE 2: Com Verificador Desligado (Benchmark Gustavo) ---"
curl -s -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"request_type": "ocr_analysis", "enable_verifier": false, "user_profile": {"has_diabetes": true}}' | python3 -m json.tool
