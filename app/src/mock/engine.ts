// Mock of the decision engine: same contract as src/service.py in fixtures mode, served from
// contracts/fixtures/. Used while API_URL is not set (see next.config.ts). Server-only.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import type {
  Health, OrderDetail, OrderPage, OrderQuery, OrderSummary, Pattern, Policy, PolicyParams,
  SimulationResult, Summary,
} from "@/lib/api";

const FIXTURES = path.join(process.cwd(), "..", "contracts", "fixtures");
const fixture = <T>(name: string): T => JSON.parse(readFileSync(path.join(FIXTURES, `${name}.json`), "utf-8"));

export class NotFound extends Error {}

const SUMMARY_KEYS: (keyof OrderSummary)[] = [
  "order_id", "customer_id", "order_date", "requested_amount", "term_months", "decision", "approved_amount",
  "default_risk", "expected_profit", "current_decision", "current_approved_amount", "changed_vs_current",
];

const brl = (v: number) => `R$ ${Math.round(v).toLocaleString("pt-BR")}`;
const pct = (v: number) => `${(Math.round(v * 1000) / 10).toString().replace(".", ",")}%`;

export const health = (): Health => ({
  status: "ok",
  mode: "fixtures",
  sections: { summary: "fixtures", patterns: "fixtures", policy: "fixtures", simulate: "fixtures", orders: "fixtures", decisions_csv: "fixtures" },
  data_cutoff: "2026-09-30",
  model_version: null,
});

export const summary = () => fixture<Summary>("summary");
export const patterns = () => fixture<Pattern[]>("patterns");

export function withDefaults(params: Partial<PolicyParams> = {}): PolicyParams {
  return { max_restrictions: 0, risk_cutoff: 0.2, safety_margin: 0, amount_rule: "maximize_expected_profit", min_amount: 500, ...params };
}

function policySteps(p: PolicyParams): Policy["steps"] {
  const amountText = p.amount_rule === "maximize_expected_profit"
    ? "Testa valores de 100% a 30% do pedido e aprova o que dá o maior resultado esperado: valores menores reduzem a parcela e o risco."
    : "Reduz o valor por faixa de risco: quanto maior o risco, menor a fração do pedido aprovada.";
  const margin = p.safety_margin ? ` Exige resultado esperado de pelo menos ${pct(p.safety_margin!)} do valor.` : "";
  return [
    { order: 1, kind: "filter", title: "Filtro de restrições", rule_text: `Nega pedidos com mais de ${p.max_restrictions} restrições ativas no bureau.` },
    { order: 2, kind: "risk", title: "Risco estimado pela IA", rule_text: `Um modelo treinado no histórico estima a chance de o cliente não pagar. Acima de ${pct(p.risk_cutoff!)}, nega.${margin}` },
    { order: 3, kind: "amount", title: "Valor aprovado", rule_text: amountText },
    { order: 4, kind: "limit", title: "Limites do produto", rule_text: `O valor fica entre ${brl(p.min_amount!)} e o menor entre o valor pedido e R$ 30.000; abaixo de ${brl(p.min_amount!)}, nega.` },
  ];
}

function withParams(base: Policy, params: PolicyParams): Policy {
  const values = params as Record<string, number | string>;
  return {
    ...base,
    params,
    steps: policySteps(params),
    param_specs: base.param_specs.map((spec) => ({ ...spec, value: values[spec.name] })),
  };
}

// Approved policy survives dev reloads, like artifacts/approved_policy.json in the engine. Delete the file to reset.
const APPROVED = path.join(process.cwd(), ".mock-approved-policy.json");

export function currentPolicy(): Policy {
  if (existsSync(APPROVED)) return JSON.parse(readFileSync(APPROVED, "utf-8"));
  const base = fixture<Policy>("policy");
  return withParams(base, withDefaults(base.params));
}

export function approvePolicy(params: Partial<PolicyParams>, approvedBy: string, note?: string | null): Policy {
  const previous = currentPolicy();
  const approved: Policy = {
    ...withParams(previous, withDefaults(params)),
    version: previous.version + 1,
    approved_at: new Date().toISOString(),
    approved_by: approvedBy,
    note: note ?? null,
  };
  writeFileSync(APPROVED, JSON.stringify(approved, null, 2));
  return approved;
}

/** Scales the example so the controls react, like service.simulate: NOT a real simulation. */
export function simulate(input: Partial<PolicyParams>): SimulationResult {
  const params = withDefaults(input);
  const base = fixture<SimulationResult>("simulation");
  const cutoff = params.risk_cutoff!, margin = params.safety_margin!, restrictions = params.max_restrictions!;
  const looseness = cutoff / 0.2;
  const quality = Math.max(0, 1 - 4 * (cutoff - 0.2) ** 2 - 2 * margin);
  const restrictionBonus = 1 + 0.03 * restrictions;
  const round2 = (v: number) => Math.round(v * 100) / 100;

  const hist = base.historical;
  const proposed = round2(hist.proposed_result * quality);
  const approvedNew = Math.min(2000, Math.round(base.new_orders.approved * looseness ** 0.3 * restrictionBonus));
  return {
    params,
    historical: {
      ...hist,
      proposed_result: proposed,
      gain: round2(proposed - hist.current_result),
      approved_proposed: Math.round(hist.approved_proposed * looseness ** 0.3 * restrictionBonus),
    },
    new_orders: {
      ...base.new_orders,
      approved: approvedNew,
      denied: 2000 - approvedNew,
      total_approved_amount: round2((base.new_orders.total_approved_amount * approvedNew) / base.new_orders.approved),
    },
    by_risk_band: base.by_risk_band.map((band) => ({ ...band, proposed_result: round2(band.proposed_result * quality) })),
  };
}

const orders = () => fixture<OrderDetail[]>("orders");

export function listOrders(query: OrderQuery): OrderPage {
  const { decision, changed, q, sort = "risk", page = 1, page_size = 50 } = query;
  let rows = orders();
  if (decision) rows = rows.filter((r) => r.decision === decision);
  if (changed !== undefined) rows = rows.filter((r) => r.changed_vs_current === changed);
  if (q) {
    const needle = q.trim().toUpperCase();
    rows = rows.filter((r) => r.order_id.includes(needle) || r.customer_id.includes(needle));
  }
  const compare: Record<string, (a: OrderDetail, b: OrderDetail) => number> = {
    risk: (a, b) => b.default_risk - a.default_risk,
    amount: (a, b) => b.requested_amount - a.requested_amount,
    order_id: (a, b) => a.order_id.localeCompare(b.order_id),
  };
  rows.sort(compare[sort]);
  const start = (page - 1) * page_size;
  const items = rows.slice(start, start + page_size).map(
    (r) => Object.fromEntries(SUMMARY_KEYS.map((k) => [k, r[k]])) as OrderSummary,
  );
  return { items, total: rows.length, page, page_size };
}

export function getOrder(id: string): OrderDetail {
  const order = orders().find((r) => r.order_id === id.trim().toUpperCase());
  if (!order) throw new NotFound(id);
  return order;
}

export function decisionsCsv(): string {
  const rows = [...orders()].sort((a, b) => a.order_id.localeCompare(b.order_id));
  const lines = rows.map((r) => `${r.order_id},${r.decision},${(r.decision === "APROVADO" ? r.approved_amount : 0).toFixed(2)}`);
  return ["id_pedido,decisao,valor_aprovado", ...lines].join("\n") + "\n";
}
