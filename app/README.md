# Painel do analista (Next)

Painel da Fortuna Crédito: padrões encontrados pela IA, política em passos, laboratório de
simulação e consulta de pedidos. Só busca e desenha; toda regra de negócio fica no motor.

```
npm install
npm run dev                                   # http://localhost:3000, com dados de exemplo
API_URL=http://localhost:8000 npm run dev     # usando o motor real (uvicorn src.api:app --port 8000)
npx openapi-typescript ../contracts/openapi.json -o src/lib/api-types.ts   # após mudar o contrato
```

No PowerShell: `$env:API_URL="http://localhost:8000"; npm run dev`.

## Como os dados chegam

O navegador sempre chama `/api/*`.

- **Sem `API_URL`:** responde o mock em `src/app/api/[...path]/route.ts` + `src/mock/engine.ts`,
  que lê `../contracts/fixtures/` e imita `src/service.py` em modo de exemplo (filtros,
  paginação, erros, simulação escalada, aprovação gravada em `.mock-approved-policy.json`; apague o arquivo para voltar à versão 1).
- **Com `API_URL`:** `next.config.ts` redireciona `/api/*` para `API_URL/v1/*` antes do mock.
  `API_URL` é lido ao iniciar o `dev` e no `build`; mudou, reinicie.

Enquanto o motor responder `mode: "fixtures"`, aparece a faixa "Dados de exemplo" e o botão
do `selic_final.csv` fica bloqueado (o arquivo de exemplo tem só 6 pedidos).

## Estrutura

| Caminho | O quê |
|---|---|
| `src/lib/api-types.ts` | Tipos gerados do contrato (não editar à mão) |
| `src/lib/api.ts` | Cliente da API e erros `{ error: { code, message } }` |
| `src/lib/format.ts` | R$, %, datas em pt-BR |
| `src/app/page.tsx` | Visão geral → Padrões → Política → Laboratório |
| `src/app/pedidos/` | Lista com filtros e detalhe do pedido |
| `src/components/` | Seções e peças de tela |
| `src/mock/engine.ts` | Mock do motor (só enquanto não há integração) |
