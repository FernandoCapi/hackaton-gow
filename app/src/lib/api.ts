import type { components, operations } from "./api-types";

type Schemas = components["schemas"];
export type Health = Schemas["Health"];
export type Summary = Schemas["Summary"];
export type Pattern = Schemas["Pattern"];
export type Policy = Schemas["Policy"];
export type PolicyParams = Schemas["PolicyParams"];
export type ParamSpec = Schemas["ParamSpec"];
export type SimulationResult = Schemas["SimulationResult"];
export type OrderPage = Schemas["OrderPage"];
export type OrderSummary = Schemas["OrderSummary"];
export type OrderDetail = Schemas["OrderDetail"];
export type Decision = OrderSummary["decision"];

export type OrderQuery = {
  decision?: Decision;
  changed?: boolean;
  q?: string;
  sort?: NonNullable<operations["get_orders_v1_orders_get"]["parameters"]["query"]>["sort"];
  page?: number;
  page_size?: number;
};

export class ApiError extends Error {
  constructor(public code: string, message: string, public status: number) {
    super(message);
  }
}

// The browser always calls /api/*: Next serves the mock or proxies to the engine (see next.config.ts).
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/${path}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new ApiError(
      body?.error?.code ?? `http_${res.status}`,
      body?.error?.message ?? "Motor de decisão indisponível. Verifique se a API está no ar.",
      res.status,
    );
  }
  return body as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

function queryString(query: OrderQuery): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return params.size ? `?${params}` : "";
}

export const api = {
  health: () => request<Health>("health"),
  summary: () => request<Summary>("summary"),
  patterns: () => request<Pattern[]>("patterns"),
  policy: () => request<Policy>("policy"),
  simulate: (params: Partial<PolicyParams>) => request<SimulationResult>("simulate", post({ params })),
  approve: (params: Partial<PolicyParams>, approved_by: string, note?: string) =>
    request<Policy>("policy/approve", post({ params, approved_by, note })),
  orders: (query: OrderQuery) => request<OrderPage>(`orders${queryString(query)}`),
  order: (id: string) => request<OrderDetail>(`orders/${encodeURIComponent(id)}`),
};
