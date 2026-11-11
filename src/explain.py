"""Turn model metrics and factors into a plain-language explanation for the client.

    python -m src.explain                 # calls the API with the ANTHROPIC_API_KEY from .env
    python -m src.explain --prompt-only   # writes the prompt for any assistant (e.g. /explicar)

Uses only aggregated results (metrics, factor importance, group averages). Never rows.
"""
import json
import os
import sys

import anthropic
import pandas as pd

import config

MODEL = "claude-opus-5-5"
OUTPUT = config.ARTIFACTS / "explanation.md"
PROMPT_OUTPUT = config.ARTIFACTS / "explain_prompt.md"

SYSTEM = """Você é um analista de negócio explicando o resultado de um modelo preditivo para
o cliente que vai tomar a decisão. O leitor não é técnico.

Escreva em português do Brasil, em markdown, com estas seções:
1. **O que os dados mostram** — de 2 a 4 frases com a conclusão principal.
2. **Principais fatores** — os fatores mais relevantes, cada um traduzido para linguagem de
   negócio e sustentado por um número dos dados recebidos.
3. **O que fazer** — de 2 a 4 ações concretas e priorizadas que decorrem dos fatores.
4. **Limites da análise** — o que o modelo não permite afirmar.

Não use jargão de ciência de dados (feature, SHAP, AUC). Use apenas números presentes nos
dados recebidos; não invente valores nem causas. Fatores indicam associação, não causa."""


def build_prompt() -> str:
    metrics = json.loads((config.ARTIFACTS / "metrics.json").read_text(encoding="utf-8"))
    profiles = json.loads((config.ARTIFACTS / "factor_profiles.json").read_text(encoding="utf-8"))
    factors = pd.read_csv(config.ARTIFACTS / "factors.csv").head(12)

    challenge = (config.ROOT / "docs" / "desafio.md").read_text(encoding="utf-8").strip()
    return "\n\n".join(
        [
            f"<desafio>\n{challenge or 'Briefing ainda nao informado.'}\n</desafio>",
            f"Cada linha analisada é um(a) {config.ENTITY_LABEL}. "
            f"O resultado previsto é: {config.POSITIVE_LABEL} (coluna {config.TARGET}).",
            f"<metricas>\n{json.dumps(metrics, indent=2, ensure_ascii=False)}\n</metricas>",
            f"<fatores>\n{factors.to_csv(index=False)}</fatores>",
            "<perfil_dos_fatores>\nMédia do resultado por grupo de cada fator "
            f"(average_outcome):\n{json.dumps(profiles, indent=2, ensure_ascii=False)}\n"
            "</perfil_dos_fatores>",
            "Escreva a explicação para o cliente.",
        ]
    )


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if not (config.ARTIFACTS / "metrics.json").exists():
        sys.exit("Rode `python -m src.train` antes.")
    has_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
    if "--prompt-only" in sys.argv or not has_key:
        PROMPT_OUTPUT.write_text(f"{SYSTEM}\n\n---\n\n{build_prompt()}\n", encoding="utf-8")
        print(f"Prompt salvo em {PROMPT_OUTPUT}.")
        print(f"Gere a explicacao com /explicar no Claude Code ou cole o prompt e salve em {OUTPUT}.")
        return

    client = anthropic.Anthropic()
    try:
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "medium"},
            system=SYSTEM,
            messages=[{"role": "user", "content": build_prompt()}],
        )
    except anthropic.AuthenticationError:
        sys.exit("Chave da Anthropic invalida.")
    except anthropic.RateLimitError:
        sys.exit("Limite de requisicoes atingido; tente de novo em instantes.")
    except anthropic.APIStatusError as error:
        sys.exit(f"Erro da API ({error.status_code}): {error.message}")
    except anthropic.APIConnectionError:
        sys.exit("Sem conexao com a API da Anthropic.")

    if response.stop_reason == "refusal":
        sys.exit("O modelo recusou a solicitacao.")
    explanation = "".join(block.text for block in response.content if block.type == "text")
    OUTPUT.write_text(explanation, encoding="utf-8")
    print(explanation)
    print(f"\nSalvo em {OUTPUT}")


if __name__ == "__main__":
    main()
