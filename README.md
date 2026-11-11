# hackaton-gow · Fortuna Crédito (time selic)

Solução do time **selic** para o Hackathon GOW 2026. A IA analisa o histórico de crédito da
Fortuna, encontra padrões de bom e mau pagamento e propõe uma política de aprovação e de valor
melhor que a atual. A política é aplicada aos 2.000 pedidos novos e gera o arquivo de decisões
`selic_final.csv`. A IA sugere; o analista de risco decide.

## Gerar o arquivo de decisões do zero

Pré-requisitos: Docker Desktop aberto, Python 3.12 ou mais novo (testado no 3.14), o dump
`fortuna_hackathon.dump` e o token do bureau do time.

```
git clone https://github.com/FernandoCapi/hackaton-gow.git
cd hackaton-gow
python -m venv .venv
.venv\Scripts\activate                     # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                     # Mac/Linux: cp .env.example .env  (preencha, ver abaixo)
docker compose up -d --wait
python scripts/restore_db.py <pasta>/fortuna_hackathon.dump --db fortuna
python -m src.decide
```

O último comando faz tudo o que falta e termina com `Formato validado: pronto para enviar.`:

1. confere o banco (10.000 pedidos históricos e 2.000 novos);
2. busca na API do bureau os dados dos clientes novos que ainda não estão em cache, com novas
   tentativas nas falhas 503 e na lentidão (`data/bureau_novos.csv`);
3. treina o modelo de risco se ele ainda não existir (`artifacts/`, ~15 s);
4. decide os 2.000 pedidos e grava `output/selic_final.csv`, validando todas as regras de formato
   do manual.

O treino é determinístico: rodar de novo, em qualquer máquina, gera o mesmo arquivo.
`python -m src.decide --retrain` força um novo treino.

### `.env`

Fica só na sua máquina (o Git ignora). Nunca commite o token.

```
DATABASE_URL=postgresql+psycopg://hackaton:hackaton@localhost:5432/fortuna
TEAM_ID=selic
BUREAU_URL=<endereço da API do bureau>
BUREAU_TOKEN=<token do time>
ANTHROPIC_API_KEY=                          # opcional; sem chave, use /explicar no Claude Code
```

O token só é usado para buscar o bureau dos clientes novos. A API devolve 404 para clientes do
histórico, cujo bureau já vem no banco.

## Como a política decide

Cada pedido passa por 5 passos, nesta ordem (todos os números são parâmetros ajustáveis):

1. **Fora do que o piloto testou:** nega score até 450, renda até R$ 1.500 ou restrição ativa.
2. **Sinais de aperto na conta:** nega quem gasta mais de 90% do que entra, usou cheque especial
   em 2 dos 3 meses antes do pedido, esvaziou a conta, tem entradas abaixo de 60% da renda
   declarada ou 8+ consultas ao CPF em 90 dias.
3. **Capacidade:** a parcela cabe em até 25% da renda efetiva (o menor valor entre a renda
   declarada e a média de entradas na conta); se não cabe, nega.
4. **Risco estimado pela IA:** um modelo treinado no histórico estima a chance de calote; nega
   acima de 15% (ou 12% para quem a política atual negaria).
5. **Limites do produto:** entre R$ 500 e o menor valor entre o pedido e R$ 30 mil.

Padrões encontrados: `docs/padroes.md`. Avaliação do motor (qualidade do modelo, ganho em R$,
estabilidade, vazamento, piloto): `docs/avaliacao-motor.md`.

## Outros comandos

```
python -m src.risk_model                   # treina e mostra as métricas do modelo
python -m src.simulate                     # simulação em R$: política atual x proposta
python -m src.evaluate                     # gera docs/avaliacao-motor.md (+ artifacts/casos.md, local)
uvicorn src.api:app --reload --port 8000   # API do motor para o painel (docs em /docs)
python -m src.api --export-openapi         # atualiza contracts/openapi.json após mudar o contrato
python -m pytest -q                        # testes (contrato da API e motor)
python -m src.bureau --check               # cobertura do cache do bureau
```

O painel (Next, em `web/`) consome a API; o guia de integração está em `docs/api.md`.

## Estrutura

| Caminho | O que é |
|---|---|
| `src/features.py` | Uma linha por pedido, só com informação do dia do pedido (lista fechada de variáveis) |
| `src/risk_model.py` | Modelo de calote (LightGBM), validação por tempo e teste de vazamento |
| `src/policy.py` | Política atual (reproduzida 100%) e proposta em 5 passos |
| `src/simulate.py` | Resultado em R$ no histórico (desfecho real) e nos pedidos novos (estimado) |
| `src/decide.py` | Gera e valida `output/selic_final.csv` |
| `src/evaluate.py` | Relatório para entender e defender o motor |
| `src/bureau.py` | Cliente da API do bureau com novas tentativas e cache |
| `src/api.py`, `src/schemas.py`, `src/service.py` | API do motor e seu contrato |
| `analysis/` | Análises exploratórias que originaram os padrões |
| `docs/` | Regras do desafio, decisões, padrões, plano, avaliação e guia da API |

## Cuidados

- O repositório é público: `dumps/`, `data/`, `artifacts/`, `output/` e `.env` ficam fora do Git.
- Para a IA de linguagem vão só números agregados, nunca linhas de clientes.
- Gênero, CEP, estado civil, idade e profissão não entram no modelo nem nas regras.
- O arquivo final é sempre gerado pelo código (CSV editado à mão desclassifica).

## Ensaio com dados de exemplo

O esqueleto original continua disponível para ensaio: `python scripts/load_sample.py`,
`python -m src.train`, `python -m src.explain` e `streamlit run app.py` (banco `hackaton`).
