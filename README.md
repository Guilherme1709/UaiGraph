# GraphPoliticsRAG 🏛️🔍

Sistema de **Graph RAG (Retrieval-Augmented Generation sobre Grafos de Conhecimento)** focado na bancada de Deputados Federais de Minas Gerais (MG) no Congresso Nacional.

Combina modelagem de dados conectada no **Neo4j**, extração de entidades e inferência grounded via **Groq / Google Gemini**, com interface reativa desenvolvida em **Angular 21 + Vis.js**.

---

## 🚀 Arquitetura

```
[ Frontend Angular ] ──> [ FastAPI Server (api.py) ]
                                │
          ┌─────────────────────┴─────────────────────┐
          ▼                                           ▼
[ Neo4j Graph DB ]                           [ Provedores de LLM ]
• Parlamentares, Partidos, Proposições       • Groq (Llama / Mixtral)
• Caminhos de Coautoria & Filiação           • Google Gemini 2.5 Flash
```

---

## 📦 Estrutura do Repositório

```text
├── api.py                    # Servidor FastAPI com rate limiting, CORS seguro e endpoints REST
├── database.py               # Camada de persistência Neo4j, índices fulltext e shortest paths
├── engine.py                 # Pipeline Graph-RAG, extração estruturada e inferência com LLM
├── cli.py                    # Interface de terminal interativa (CLI)
├── requirements.txt          # Dependências Python fixadas
├── Dockerfile                # Imagem de container pronta para produção (non-root)
├── README.md                 # Documentação executiva do projeto
│
├── frontend-angular/         # Aplicação web SPA (Angular 21 + Vis.js Network)
│   ├── src/                  # Componentes reativos, serviços e environments
│   └── public/               # Assets públicos estáticos
│
├── scripts/                  # Pipeline de ETL e carga de dados da Câmara
│   ├── collector.py          # Extrator dos dados abertos da Câmara
│   ├── ingest_propositions.py# Carga das proposições no Neo4j
│   ├── normalize_parties.py  # Tratamento e canonicidade partidária
│   └── migrate_relationships.py # Padronização de labels e relações Cypher
│
└── tests/                    # Suíte de testes unitários automatizados
    ├── test_api_and_engine.py# Testes de normalização e validação de schemas
    └── test_routes.py        # Testes de contratos e endpoints HTTP da API
```

---

## ⚙️ Configuração do Ambiente

1. Clone o repositório:
```bash
git clone <url-do-repositorio>
cd political-graph-rag
```

2. Crie um ambiente virtual e instale as dependências:
```bash
python -m venv venv
# No Windows:
.\venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

3. Configure o arquivo de variáveis de ambiente:
```bash
cp .env.example .env
```
Preencha `.env` com suas credenciais do **Neo4j Aura**, **Groq API** e **Gemini API**.

> ⚠️ **IMPORTANTE**: Nunca faça commit do arquivo `.env`. Suas chaves de API e senhas devem ser mantidas em sigilo absoluto.

---

## 🧪 Executando os Testes

```bash
python -m unittest discover tests
```

---

## 🏃 Como Rodar Localmente

### 1. Iniciar o Backend (FastAPI)
```bash
python api.py
```
A API estará disponível em: `http://localhost:8000`  
Documentação Swagger interativa: `http://localhost:8000/docs`

### 2. Iniciar o Frontend (Angular)
```bash
cd frontend-angular
npm install
npm start
```
O frontend estará acessível em: `http://localhost:4200`

---

## 🐳 Deploy com Docker

Para construir e executar a imagem em produção:

```bash
docker build -t graphpolitics-api .
docker run -d -p 8000:8000 --env-file .env graphpolitics-api
```

---

## 🛡️ Medidas de Segurança Implementadas

- **Rate Limiting:** Proteção contra esgotamento de cotas de LLM via `slowapi` (`/api/chat` limitado a 20 req/min).
- **CORS Estrito:** Origens configuráveis via `CORS_ORIGINS`.
- **Validação de Payload:** Validação de tamanho e tipos nos dados de entrada via Pydantic.
- **Prevenção de Vazamento de Erros:** Exceções internas e stack traces do banco não são expostos na resposta HTTP.
- **Proteção contra Injeção de Prompt:** Delimitação estrita de blocos de contexto e instruções defensivas no engine de IA.
