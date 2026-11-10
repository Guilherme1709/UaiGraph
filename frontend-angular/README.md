# Frontend do UaiGraph

Interface Angular para consultar a API e explorar relações no grafo. Usa Signals para o estado da tela e Vis.js Network para a visualização.

## Desenvolvimento

Com a API rodando na porta 8000:

```bash
npm ci
npm start
```

Acesse `http://localhost:4200`. O endereço da API fica em `src/environments/environment.ts`; a configuração de produção fica em `environment.prod.ts`.

## Build e testes

```bash
npm run build
npm test -- --watch=false
```

O build gera os arquivos em `dist/frontend-angular/browser`.

## Organização

- `services`: cliente HTTP e estado da interface.
- `shared/components`: grafo, dossiê, filtros e detalhes de proposições.
- `desktop` e `mobile`: layouts selecionados conforme a largura da tela.

Consulte o [README do projeto](../README.md) para configurar o backend e carregar os dados.
