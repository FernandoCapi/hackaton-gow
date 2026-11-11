# hackaton-gow

Esqueleto para o hackathon interno da GOW: banco PostgreSQL → dataset → modelo → explicação
em linguagem de negócio → painel de decisão.

## Pré-requisitos

- Docker Desktop aberto
- Python 3.12 ou mais novo (testado no 3.14)
- Git

## Setup

```
git clone https://github.com/FernandoCapi/hackaton-gow.git
cd hackaton-gow
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # Mac/Linux: cp .env.example .env
docker compose up -d --wait
```

Banco: `localhost:5432`, usuário, senha e banco `hackaton`.

## Ensaio com dados de exemplo

```
python scripts/load_sample.py     # churn sintético em 3 tabelas
python -m src.profile             # visão geral do schema
python -m src.train               # modelo baseline, grava artifacts/
python -m src.explain             # com ANTHROPIC_API_KEY no .env chama a API; sem chave, gera o prompt para /explicar
streamlit run app.py              # painel em http://localhost:8501
```

## No dia

1. Coloque o arquivo recebido em `dumps/` e restaure (aceita `.sql`, `.sql.gz`, `.dump`,
   `.backup`, `.tar` ou uma pasta de CSVs). O banco `hackaton` é recriado do zero:
   ```
   python scripts/restore_db.py dumps/<arquivo>
   ```
2. `python -m src.profile --save` para entender as tabelas.
3. Reescreva `sql/dataset.sql`: uma linha por entidade a pontuar, com a coluna-alvo.
4. Ajuste `config.py`: `TARGET`, `ID_COLUMN`, `DATE_COLUMN`, `TASK`, `DROP_COLUMNS` e os rótulos.
5. `python -m src.train`, depois `python -m src.explain` e `streamlit run app.py`.

Com Claude Code, os comandos `/kickoff`, `/explorar-banco`, `/explicar` e `/pitch` conduzem
os passos, a explicação para o cliente e o roteiro da apresentação.

## Acesso à IA

Cada pessoa usa o próprio acesso: a assinatura do Claude Code basta para todo o fluxo
(a explicação sai pelo `/explicar`). Quem tiver chave de API pode colocá-la no próprio `.env`
para usar `python -m src.explain` direto. Nunca compartilhe nem commite credenciais.

## Cuidados

- O repositório é público: `dumps/`, `artifacts/` e `.env` ficam fora do Git.
- `src/explain.py` envia à API apenas métricas e médias por grupo, nunca linhas de clientes.
- Linhas com alvo nulo recebem score, mas não entram no treino.
