import type { Health } from "./api";

const SECTION_LABELS: Record<string, string> = {
  summary: "Visão geral",
  patterns: "Padrões",
  policy: "Política",
  simulate: "Laboratório",
  orders: "Pedidos",
  decisions_csv: "Arquivo de decisões",
};

/** Plain-language warning about sections still answered with example data, or null when all are live. */
export function exampleDataWarning(health: Health | undefined): string | null {
  if (!health || health.mode === "live") return null;
  const examples = Object.entries(health.sections).filter(([, mode]) => mode === "fixtures").map(([name]) => SECTION_LABELS[name] ?? name);
  if (examples.length === Object.keys(health.sections).length) return "Dados de exemplo: os números ainda não vêm do motor de decisão.";
  return `Ainda com dados de exemplo: ${examples.join(", ")}.`;
}
