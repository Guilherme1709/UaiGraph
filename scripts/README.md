# Pipeline de ETL & Dados (Scripts)

Este diretório contém os scripts responsáveis pela coleta, tratamento e ingestão de dados da API Oficial da Câmara dos Deputados no banco de dados em grafo Neo4j.

---

## 🛠️ Scripts Disponíveis

### 1. `collector.py`
Conecta-se à API de Dados Abertos da Câmara dos Deputados (`dadosabertos.camara.leg.br/api/v2`), coletando:
- Deputados Federais em exercício eleitos por Minas Gerais (MG)
- Detalhes cadastrais (foto oficial, gabinete, e-mail institucional)
- Proposições prioritárias apresentadas (PL, PEC, PLP, PDL)

**Execução:**
```bash
python scripts/collector.py
```

---

### 2. `ingest_propositions.py`
Enriquece o grafo com as ementas oficiais e metadados detalhados das matérias legislativas dos parlamentares mineiros, removendo requerimentos administrativos irrelevantes.

**Execução:**
```bash
python scripts/ingest_propositions.py
```

---

### 3. `normalize_parties.py`
Garante a canonicidade e consistência das siglas partidárias (ex.: unifica variações como `PT/MG`, `PODE-MG`, `UNIÃO BRASIL` em seus nós canônicos únicos).

**Execução:**
```bash
python scripts/normalize_parties.py
```

---

### 4. `migrate_relationships.py`
Migra e padroniza relações legadas para o formato canônico em português (ex.: `MEMBER_OF` -> `FILIADO_A`, `PROPOSED` -> `PROPOS`).

**Execução:**
```bash
python scripts/migrate_relationships.py
```
