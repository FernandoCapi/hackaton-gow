// Mock of the engine API (/v1/*), active while API_URL is not set. With API_URL, next.config.ts
// rewrites /api/* to the real engine before this route is reached.
import type { OrderQuery, PolicyParams } from "@/lib/api";
import * as engine from "@/mock/engine";

const error = (status: number, code: string, message: string) =>
  Response.json({ error: { code, message } }, { status });

// Same bounds as PolicyParams in src/schemas.py.
const PARAM_RULES: Record<string, (v: unknown) => boolean> = {
  max_restrictions: (v) => Number.isInteger(v) && (v as number) >= 0 && (v as number) <= 10,
  risk_cutoff: (v) => typeof v === "number" && v >= 0 && v <= 1,
  safety_margin: (v) => typeof v === "number" && v >= 0 && v <= 0.5,
  amount_rule: (v) => v === "maximize_expected_profit" || v === "fixed_bands",
  min_amount: (v) => typeof v === "number" && v >= 500 && v <= 30000,
};

function invalidParams(params: unknown): string | null {
  if (typeof params !== "object" || params === null) return "params: campo obrigatório";
  for (const [key, value] of Object.entries(params)) {
    if (!PARAM_RULES[key]) return `params.${key}: campo não permitido`;
    if (!PARAM_RULES[key](value)) return `params.${key}: valor fora da faixa`;
  }
  return null;
}

function orderQuery(search: URLSearchParams): OrderQuery | string {
  const decision = search.get("decision") ?? undefined;
  const sort = search.get("sort") ?? "risk";
  const changed = search.get("changed");
  const page = Number(search.get("page") ?? 1);
  const pageSize = Number(search.get("page_size") ?? 50);
  if (decision && decision !== "APROVADO" && decision !== "NEGADO") return "decision: use APROVADO ou NEGADO";
  if (!["risk", "amount", "order_id"].includes(sort)) return "sort: use risk, amount ou order_id";
  if (!Number.isInteger(page) || page < 1) return "page: deve ser >= 1";
  if (!Number.isInteger(pageSize) || pageSize < 1 || pageSize > 200) return "page_size: deve estar entre 1 e 200";
  return {
    decision: decision as OrderQuery["decision"],
    changed: changed === null ? undefined : changed === "true",
    q: search.get("q") ?? undefined,
    sort: sort as OrderQuery["sort"],
    page,
    page_size: pageSize,
  };
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: Request, { params }: Ctx) {
  const route = (await params).path.join("/");
  if (route === "health") return Response.json(engine.health());
  if (route === "summary") return Response.json(engine.summary());
  if (route === "patterns") return Response.json(engine.patterns());
  if (route === "policy") return Response.json(engine.currentPolicy());
  if (route === "orders") {
    const query = orderQuery(new URL(request.url).searchParams);
    return typeof query === "string" ? error(422, "invalid_request", query) : Response.json(engine.listOrders(query));
  }
  if (route.startsWith("orders/")) {
    const id = decodeURIComponent(route.slice("orders/".length));
    try {
      return Response.json(engine.getOrder(id));
    } catch (e) {
      if (e instanceof engine.NotFound) return error(404, "order_not_found", `Pedido ${id} não existe na base de novos pedidos.`);
      throw e;
    }
  }
  if (route === "decisions.csv") {
    return new Response(engine.decisionsCsv(), {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="selic_final.csv"',
      },
    });
  }
  return error(404, "not_found", "Not Found");
}

export async function POST(request: Request, { params }: Ctx) {
  const route = (await params).path.join("/");
  const body = await request.json().catch(() => null);
  if (route !== "simulate" && route !== "policy/approve") return error(404, "not_found", "Not Found");
  const problem = invalidParams(body?.params);
  if (problem) return error(422, "invalid_request", problem);
  const policyParams = body.params as Partial<PolicyParams>;
  if (route === "simulate") return Response.json(engine.simulate(policyParams));
  if (typeof body.approved_by !== "string" || !body.approved_by.trim()) {
    return error(422, "invalid_request", "approved_by: informe o nome do analista");
  }
  return Response.json(engine.approvePolicy(policyParams, body.approved_by, body.note));
}
