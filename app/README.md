# Painel do analista (Next)

Painel da Fortuna Crédito: padrões encontrados pela IA, política em passos, laboratório de
simulação e consulta de pedidos. Só busca e desenha; toda regra de negócio fica no motor.

```
# 1. motor (na raiz do repo, com a .venv)
uvicorn src.api:app --port 8000

# 2. painel
cd app
npm install
npm run dev                                   # http://localhost:3000
```

O painel chama `/api/*` e o Next repassa para `http://localhost:8000/v1/*`. Para outro
endereço, defina `API_URL` antes do `npm run dev` (PowerShell: `$env:API_URL="http://..."`).
`API_URL` é lido ao iniciar; mudou, reinicie.

## Motor real × dados de exemplo

O próprio motor decide a origem dos dados (`GET /v1/health` → `sections`):

- **Ao vivo:** banco restaurado, bureau em cache (`python -m src.bureau`) e modelo treinado
  (`python -m src.risk_model`).
- **Exemplo:** sem isso, ou com `ENGINE_MODE=fixtures`, responde com `contracts/fixtures/`.
  Basta `pip install -r requirements.txt`; não precisa de banco.

O painel avisa quais seções ainda estão com dados de exemplo. O botão do `selic_final.csv`
só libera quando `decisions_csv` está ao vivo.

## Contrato

Mudou `contracts/openapi.json`? Regere os tipos:

```
npx openapi-typescript ../contracts/openapi.json -o src/lib/api-types.ts
```

## Estrutura

| Caminho | O quê |
|---|---|
| `src/lib/api-types.ts` | Tipos gerados do contrato (não editar à mão) |
| `src/lib/api.ts` | Cliente da API e erros `{ error: { code, message } }` |
| `src/lib/format.ts` | R$, %, datas em pt-BR |
| `src/lib/health.ts` | Aviso de seções ainda com dados de exemplo |
| `src/app/` | Páginas: visão geral, padrões, política, laboratório, pedidos |
| `src/components/` | Menu lateral, seções e peças de tela |
