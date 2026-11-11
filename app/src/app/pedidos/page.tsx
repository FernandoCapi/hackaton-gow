"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronRight, Download, ListChecks, SlidersHorizontal, X } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";
import { api, type OrderQuery } from "@/lib/api";
import { brl, date, int, pct } from "@/lib/format";
import { Card, DecisionBadge, RiskMeter, Section, Status } from "@/components/ui";

const PAGE_SIZES = [20, 50, 100, 200]; // 200 is the API maximum for page_size
const select = "rounded-md border border-border bg-background px-2 py-1.5 text-sm";
const DEFAULT_QUERY: OrderQuery = { sort: "risk", page: 1, page_size: 20 };
const SORTS: { value: NonNullable<OrderQuery["sort"]>; label: string }[] = [
  { value: "risk", label: "Maior chance de calote" },
  { value: "risk_asc", label: "Menor chance de calote" },
  { value: "amount", label: "Maior valor pedido" },
  { value: "amount_asc", label: "Menor valor pedido" },
  { value: "approved", label: "Maior valor aprovado" },
  { value: "profit", label: "Maior resultado esperado" },
  { value: "recent", label: "Mais recentes" },
  { value: "order_id", label: "Nº do pedido" },
];

export default function OrdersPage() {
  const [query, setQuery] = useState<OrderQuery>(DEFAULT_QUERY);
  const set = (patch: Partial<OrderQuery>) => setQuery({ ...query, page: 1, ...patch });
  const orders = useQuery({ queryKey: ["orders", query], queryFn: () => api.orders(query), placeholderData: keepPreviousData });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });
  const csvIsExample = health.data?.sections.decisions_csv !== "live";
  const active = [query.decision !== undefined, query.changed !== undefined, !!query.q, query.sort !== DEFAULT_QUERY.sort].filter(Boolean).length;
  const filtered = active > 0;
  const dialog = useRef<HTMLDialogElement>(null);
  const [draft, setDraft] = useState<OrderQuery>(DEFAULT_QUERY);
  const openFilters = () => {
    setDraft(query);
    dialog.current?.showModal();
  };
  const pages = orders.data ? Math.max(1, Math.ceil(orders.data.total / query.page_size!)) : 1;

  return (
    <Section icon={ListChecks} title="Pedidos novos" subtitle="Decisão sugerida pela política em vigor, comparada com a regra antiga.">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={openFilters}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium shadow-sm hover:bg-background"
        >
          <SlidersHorizontal className="size-4" aria-hidden /> Filtros
          {active > 0 && <span className="rounded-full bg-accent px-1.5 text-xs text-on-solid tabular-nums">{active}</span>}
        </button>
        <span className="text-sm text-muted">Ordenado por: {SORTS.find((s) => s.value === query.sort)?.label}</span>
        {filtered && (
          <button type="button" onClick={() => setQuery({ ...DEFAULT_QUERY, page_size: query.page_size })} className="inline-flex items-center gap-1 text-sm text-accent hover:underline">
            <X className="size-3.5" aria-hidden /> Limpar filtros
          </button>
        )}
        <dialog
          ref={dialog}
          aria-labelledby="filters-title"
          className="m-auto w-[min(28rem,calc(100%-2rem))] rounded-xl border border-border bg-surface p-0 text-foreground shadow-xl backdrop:bg-black/50"
        >
          <form
            method="dialog"
            onSubmit={() => setQuery({ ...draft, page: 1, page_size: query.page_size })}
            className="grid gap-4 p-5"
          >
            <div className="flex items-center justify-between">
              <h2 id="filters-title" className="text-base font-semibold">Filtros</h2>
              <button type="button" onClick={() => dialog.current?.close()} aria-label="Fechar" className="rounded-md p-1 text-muted hover:bg-background">
                <X className="size-4" aria-hidden />
              </button>
            </div>
            <label className="grid gap-1 text-sm">Pedido ou cliente
              <input className={select} value={draft.q ?? ""} onChange={(e) => setDraft({ ...draft, q: e.target.value || undefined })} placeholder="P-99001 ou C-99001" />
            </label>
            <label className="grid gap-1 text-sm">Decisão
              <select className={select} value={draft.decision ?? ""} onChange={(e) => setDraft({ ...draft, decision: (e.target.value || undefined) as OrderQuery["decision"] })}>
                <option value="">Todas</option>
                <option value="APROVADO">Aprovados</option>
                <option value="NEGADO">Negados</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm">Em relação à regra antiga
              <select className={select} value={draft.changed === undefined ? "" : String(draft.changed)} onChange={(e) => setDraft({ ...draft, changed: e.target.value === "" ? undefined : e.target.value === "true" })}>
                <option value="">Todos</option>
                <option value="true">Decisão mudou</option>
                <option value="false">Decisão igual</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm">Ordenar por
              <select className={select} value={draft.sort} onChange={(e) => setDraft({ ...draft, sort: e.target.value as OrderQuery["sort"] })}>
                {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </label>
            <div className="mt-1 flex justify-between gap-2 border-t border-border pt-4">
              <button type="button" onClick={() => setDraft(DEFAULT_QUERY)} className="rounded-lg px-3 py-2 text-sm text-muted hover:bg-background hover:text-foreground">
                Limpar
              </button>
              <button type="submit" className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-on-solid hover:bg-accent-strong">
                Aplicar
              </button>
            </div>
          </form>
        </dialog>
        {/* Full official file (all 2,000 orders), ignores the filters above. The example CSV has only a
            handful of orders: never let it be sent as the official file. */}
        <div className="ml-auto text-right">
          {csvIsExample ? (
            <button disabled title="Disponível quando o motor gerar as decisões reais" className="rounded-md border border-border px-3 py-1.5 text-sm text-muted">
              Baixar selic_final.csv
            </button>
          ) : (
            <a href="/api/decisions.csv" download className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-on-solid shadow-sm hover:bg-accent-strong"><Download className="size-4" aria-hidden />Baixar selic_final.csv</a>
          )}
          {csvIsExample && <p className="mt-1 text-xs text-muted">Arquivo de exemplo: não enviar.</p>}
        </div>
      </div>

      <Status loading={orders.isLoading} error={orders.error} />
      {orders.data && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <caption className="sr-only">Pedidos novos e decisão sugerida</caption>
            <thead className="border-b border-border bg-surface-2 text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="px-3 py-2 font-medium">Pedido</th>
                <th className="px-3 py-2 font-medium">Data</th>
                <th className="px-3 py-2 text-right font-medium">Pedido (R$)</th>
                <th className="px-3 py-2 font-medium">Decisão</th>
                <th className="px-3 py-2 text-right font-medium">Aprovado (R$)</th>
                <th className="px-3 py-2 text-right font-medium">Chance de calote</th>
                <th className="px-3 py-2 font-medium">Regra antiga</th>
                <th className="px-3 py-2"><span className="sr-only">Detalhes</span></th>
              </tr>
            </thead>
            <tbody>
              {orders.data.items.map((o) => (
                <tr key={o.order_id} className="border-b border-border last:border-0 hover:bg-background">
                  <td className="px-3 py-2"><Link href={`/pedidos/${o.order_id}`} className="font-medium text-accent hover:underline">{o.order_id}</Link></td>
                  <td className="px-3 py-2">{date(o.order_date)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{brl(o.requested_amount)}</td>
                  <td className="px-3 py-2"><DecisionBadge decision={o.decision} /></td>
                  <td className="px-3 py-2 text-right tabular-nums">{brl(o.approved_amount)}</td>
                  <td className="px-3 py-2 text-right tabular-nums"><span className="inline-flex items-center gap-2"><RiskMeter value={o.default_risk} />{pct(o.default_risk)}</span></td>
                  <td className="px-3 py-2">
                    <DecisionBadge decision={o.current_decision} subtle />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <Link
                      href={`/pedidos/${o.order_id}`}
                      aria-label={`Ver detalhes do pedido ${o.order_id}`}
                      className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-accent/40 px-2.5 py-1 text-xs font-medium text-accent hover:bg-accent-soft"
                    >
                      Ver detalhes <ChevronRight className="size-3.5" aria-hidden />
                    </Link>
                  </td>
                </tr>
              ))}
              {orders.data.items.length === 0 && (
                <tr><td colSpan={8} className="px-3 py-6 text-center text-muted">Nenhum pedido com esses filtros.</td></tr>
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
