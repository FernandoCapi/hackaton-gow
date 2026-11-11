import { RuleTag } from "./ui";

/** Shown on every page: the analyst always knows which rule a number belongs to. */
export default function RulesLegend() {
  return (
    <div className="mb-6 flex flex-col gap-2 rounded-xl border border-border bg-surface px-4 py-3 text-xs text-muted sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-6">
      <span className="font-medium text-foreground">Como ler:</span>
      <span className="flex items-center gap-2"><RuleTag kind="nova" /> política proposta; é ela que gera o arquivo oficial de decisões</span>
      <span className="flex items-center gap-2"><RuleTag kind="antiga" /> regra atual da Fortuna: score acima de 600, renda acima de R$ 2.000, sem restrições e parcela até 30% da renda (nega o que passa disso)</span>
    </div>
  );
}
