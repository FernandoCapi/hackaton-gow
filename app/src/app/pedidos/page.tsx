"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { api, type OrderQuery } from "@/lib/api";
import { brl, date, int, pct } from "@/lib/format";
import { Card, DecisionBadge, Section, Status } from "@/components/ui";

const PAGE_SIZES = [20, 50, 100, 200]; // 200 is the API maximum for page_size
const select = "rounded-md border border-border bg-background px-2 py-1.5 text-sm";

export default function OrdersPage() {
  const [query, setQuery] = useState<OrderQuery>({ sort: "risk", page: 1, page_size: 20 });
  const set = (patch: Partial<OrderQuery>) => setQuery({ ...query, page: 1, ...patch });
  const orders = useQuery({ queryKey: ["orders", query], queryFn: () => api.orders(query), placeholderData: keepPreviousData });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const csvIsExample = health.data?.sections.decisions_csv !== "live";
  const pages =orders.data ? Math.max(1, Math.ceil(orders.data.total / query.page_size!)) : 1;

  return (
    <Section title="Pedidos novos" subtitle="Decisão sugerida pela política em vigor, comparada com a regra antiga.">
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="flex flex-col text-sm">Decisão
          <select className={select} value={query.decision ?? ""} onChange={(e) => set({ decision: (e.target.value || undefined) as OrderQuery["decision"] })}>
            <option value="">Todas</option>
            <option value="APROVADO">Aprovados</option>
            <option value="NEGADO">Negados</option>
          </select>
        </label>
        <label className="flex flex-col text-sm">Em relação à regra antiga
          <select className={select} value={query.changed === undefined ? "" : String(query.changed)} onChange={(e) => set({ changed: e.target.value === "" ? undefined : e.target.value === "true" })}>
            <option value="">Todos</option>
            <option value="true">Decisão mudou</option>
            <option value="false">Decisão igual</option>
          </select>
        </label>
        <label className="flex flex-col text-sm">Pedido ou cliente
          <input className={select} value={query.q ?? ""} onChange={(e) => set({ q: e.target.value || undefined })} placeholder="P-99001 ou C-99001" />
        </label>
        {/* Full official file (all 2,000 orders), ignores the filters above. The example CSV has only a
            handful of orders: never let it be sent as the official file. */}
        <div className="ml-auto text-right">
          {csvIsExample ? (
            <button disabled title="Disponível quando o motor gerar as decisões reais" className="rounded-md border border-border px-3 py-1.5 text-sm text-muted">
              Baixar selic_final.csv
            </button>
          ) : (
            <a href="/api/decisions.csv" download className="rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-background">Baixar selic_final.csv</a>
          )}
          {csvIsExample && <p className="mt-1 text-xs text-muted">Arquivo de exemplo: não enviar.</p>}
        </div>
      </div>

      <Status loading={orders.isLoading} error={orders.error} />
      {orders.data && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <caption className="sr-only">Pedidos novos e decisão sugerida</caption>
            <thead className="border-b border-border text-left text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Pedido</th>
                <th className="px-3 py-2 font-medium">Data</th>
                <th className="px-3 py-2 text-right font-medium">Pedido (R$)</th>
                <th className="px-3 py-2 font-medium">Decisão</th>
                <th className="px-3 py-2 text-right font-medium">Aprovado (R$)</th>
                <th className="px-3 py-2 text-right font-medium">Chance de calote</th>
                <th className="px-3 py-2 font-medium">Regra antiga</th>
              </tr>
            </thead>
            <tbody>
              {orders.data.items.map((o) => (
                <tr key={o.order_id} className="border-b border-border last:border-0 hover:bg-background">
                  <td className="px-3 py-2"><Link href={`/pedidos/${o.order_id}`} className="font-medium underline">{o.order_id}</Link></td>
                  <td className="px-3 py-2">{date(o.order_date)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{brl(o.requested_amount)}</td>
                  <td className="px-3 py-2"><DecisionBadge decision={o.decision} /></td>
                  <td className="px-3 py-2 text-right tabular-nums">{brl(o.approved_amount)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{pct(o.default_risk)}</td>
                  <td className="px-3 py-2">
                    <DecisionBadge decision={o.current_decision} subtle />
                  </td>
                </tr>
              ))}
              {orders.data.items.length === 0 && (
                <tr><td colSpan={7} className="px-3 py-6 text-center text-muted">Nenhum pedido com esses filtros.</td></tr>
              )}
            </tbody>
          </table>
        </Card>
      )}
      {orders.data && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-muted">
          <div className="flex items-center gap-3">
            <span>
              {orders.data.total
                ? `${int((orders.data.page - 1) * orders.data.page_size + 1)}–${int((orders.data.page - 1) * orders.data.page_size + orders.data.items.length)} de ${int(orders.data.total)} pedidos`
                : "0 pedidos"}
            </span>
            <label className="flex items-center gap-2">
              Itens por página
              <select className={select} value={query.page_size} onChange={(e) => set({ page_size: Number(e.target.value) })}>
                {PAGE_SIZES.map((size) => <option key={size} value={size}>{size}</option>)}
              </select>
            </label>
          </div>
          <div className="flex items-center gap-2">
            <button disabled={query.page === 1} onClick={() => setQuery({ ...query, page: query.page! - 1 })} className="rounded-md border border-border px-2 py-1 disabled:opacity-40">Anterior</button>
            <span>Página {query.page} de {pages}</span>
            <button disabled={query.page! >= pages} onClick={() => setQuery({ ...query, page: query.page! + 1 })} className="rounded-md border border-border px-2 py-1 disabled:opacity-40">Próxima</button>
          </div>
        </div>
      )}
    </Section>
  );
}
