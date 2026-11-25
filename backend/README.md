
# Berkanan - Desafio 2 (Backend API e Agentes)

Este repositório contém o esqueleto local da API (FastAPI) e dos Agentes (LangGraph) para o Desafio 2.

## Como rodar o projeto

### Pré-requisitos
*   Python 3.10 ou superior instalado.

### 1. Configurar o ambiente virtual
Abra o terminal na pasta `backend` e execute:
```bash
python3 -m venv venv
source venv/bin/activate  # No Windows use: venv\Scripts\activate
```

### 2. Instalar as dependências
Com o ambiente virtual ativado, rode:
```bash
pip install -r requirements.txt
```

### 3. Subir a API (Terminal 1)
```bash
uvicorn main:api --reload
```
*   A API ficará ativa em `http://localhost:8000`.
*   Para ver a documentação visual (Swagger), acesse `http://localhost:8000/docs`.
*   Deixe este terminal aberto enquanto estiver testando.

### 4. Rodar os Testes Automatizados (Terminal 2)
Abra um segundo terminal na mesma pasta e execute:
```bash
chmod +x test_api.sh
./test_api.sh
```
*   **Teste 1 (`enable_verifier: true`)**: Valida o fluxo completo passando pelo verificador.
*   **Teste 2 (`enable_verifier: false`)**: Valida o modo rápido para o benchmark do Gustavo, pulando o verificador.

## 📂 Estrutura de arquivos
*   `main.py`: Rota da API FastAPI (`POST /api/analyze`).
*   `graph.py`: Definição do fluxo no LangGraph (Coordenador -> Nutricional -> Verificador).
*   `state.py`: Contrato interno dos agentes (`AgentState`).
*   `schemas.py`: Contratos de entrada e saída (Pydantic).
*   `test_api.sh`: Script para testar a API via `curl`.

## Contrato do agente nutricional

`AnalysisRequest.verifier_mode` aceita `"rules"` (verificador determinístico, Configuração B)
ou `"llm"` (verificador Configuração C ligável). `enable_verifier=false` desliga ambos.

`AnalysisResponse.llm_calls` informa quantas tentativas ao LLM foram realizadas na resposta.
O máximo é controlado por `MAX_LLM_CALLS_PER_RESPONSE` (padrão `2`) e configurado no ambiente.