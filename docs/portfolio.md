# UaiGraph — apresentação para portfólio

## Publicação para LinkedIn

Como explorar dados legislativos fazendo perguntas em linguagem natural — e visualizar as relações usadas para construir a resposta?

Esse foi o problema que escolhi trabalhar no UaiGraph, meu projeto de portfólio com Graph RAG aplicado à bancada de deputados federais de Minas Gerais.

O sistema reúne dados públicos da Câmara dos Deputados em um grafo no Neo4j. A partir de uma pergunta, identifica entidades, recupera relações entre parlamentares, partidos e proposições e usa esse contexto para gerar uma resposta acompanhada de um grafo interativo.

Na prática, é possível explorar perguntas como: “Quem são os deputados do mesmo partido de Célia Xakriabá?”

O projeto conecta diferentes partes do desenvolvimento de uma aplicação de IA:

- Coleta e ingestão de dados públicos em um grafo de conhecimento.
- API em Python/FastAPI e consultas em Cypher.
- Integração com Gemini e Groq, com fallback entre provedores.
- Interface responsiva em Angular com visualização de relações.
- Testes automatizados e configuração de deploy com Docker.

A escolha do grafo permite consultar relações explícitas, como filiação partidária e autoria de proposições. O contexto recuperado ajuda a fundamentar a resposta, mas não elimina erros: a cobertura dos dados e a avaliação da qualidade continuam sendo pontos importantes do projeto.

Código: https://github.com/Guilherme1709/UaiGraph
Demonstração: https://uaigraph.pages.dev/

Feedbacks sobre arquitetura, experiência de uso e avaliação de sistemas RAG são bem-vindos!

#Portfolio #Python #Angular #Neo4j #RAG

## Roteiro de vídeo — 60 a 90 segundos

1. **Problema (0–15s):** apresente a dificuldade de explorar relações entre deputados, partidos e proposições em dados públicos.
2. **Pergunta (15–35s):** abra a demonstração e pergunte sobre um parlamentar. Aguarde a resposta antes de gravar a próxima etapa, sem esconder eventuais limitações.
3. **Evidências (35–55s):** mostre a resposta e o grafo; abra um nó ou dossiê e explique o significado das relações exibidas.
4. **Arquitetura (55–75s):** mostre o diagrama do README e explique: pergunta → entidades → consulta ao Neo4j → contexto → resposta.
5. **Fechamento (75–90s):** mostre o repositório e mencione a evolução planejada: avaliação de respostas, busca híbrida e novas relações.

## Apresentação no GitHub

Descrição sugerida para o campo About:

> Graph RAG sobre deputados federais de Minas Gerais: Python/FastAPI, Neo4j e Angular, com respostas em linguagem natural e grafo interativo de relações.

Website: https://uaigraph.pages.dev/

Topics sugeridos: `graph-rag`, `neo4j`, `fastapi`, `angular`, `python`, `knowledge-graph`, `open-data`, `portfolio`.

## Antes de divulgar

- Abra a demonstração e execute as perguntas que pretende mostrar; a compilação local não confirma a disponibilidade dos serviços publicados.
- Capture uma tela com pergunta, resposta e grafo legíveis, sem chaves ou painéis privados.
- Confira as informações apresentadas com a fonte oficial e evite afirmar cobertura completa ou ausência de alucinações.
- Adicione o repositório e a demonstração à seção de destaques do seu perfil.
