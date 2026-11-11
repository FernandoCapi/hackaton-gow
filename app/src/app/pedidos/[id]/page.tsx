"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { use } from "react";
import { api, type OrderDetail } from "@/lib/api";
import { brl, date, int, pct } from "@/lib/format";
import { Card, DecisionBadge, Status } from "@/components/ui";

const STEP_STYLE: Record<OrderDetail["steps"][number]["result"], { icon: string; label: string; className: string }> = {
  passou: { icon: "✓", label: "Passou", className: "text-good" },
  negou: { icon: "✕", label: "Negou", className: "text-critical" },
  ajustou: { icon: "↓", label: "Ajustou o valor", className: "text-foreground" },
};

function Facts({ title, rows }: { title: string; rows: [string, string][] }) {
  return (
    <Card>
      <h2 className="mb-2 font-medium">{title}</h2>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-muted">{label}</dt>
            <dd className="text-right tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export default function OrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: o, isLoading, error } = useQuery({ queryKey: ["orders", "detail", id], queryFn: () => api.order(id), retry: false });

  return (
    <div>
      <Link href="/pedidos" className="text-sm text-muted underline">← Pedidos</Link>
      <h1 className="mt-2 text-xl font-semibold">Pedido {o?.order_id ?? decodeURIComponent(id).toUpperCase()}</h1>
      <div className="mt-2"><Status loading={isLoading} error={error} /></div>
      {o && (
        <div className="mt-4 grid gap-4">
          <Card>
            <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2">
              <div><p className="text-sm text-muted">Decisão sugerida</p><DecisionBadge decision={o.decision} /></div>
              <div><p className="text-sm text-muted">Valor aprovado</p><p className="text-xl font-semibold tabular-nums">{brl(o.approved_amount)}</p></div>
              <div><p className="text-sm text-muted">Pedido</p><p className="tabular-nums">{brl(o.requested_amount)} em {o.term_months}x</p></div>
              <div><p className="text-sm text-muted">Chance de calote</p><p className="tabular-nums">{pct(o.default_risk)}</p></div>
              <div><p className="text-sm text-muted">Regra antiga</p><p><DecisionBadge decision={o.current_decision} subtle /> <span className="text-sm tabular-nums">{brl(o.current_approved_amount)}</span></p></div>
            </div>
            <h2 className="mt-4 font-medium">Por quê</h2>
            <ul className="mt-1 list-disc pl-5 text-sm">{o.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
          </Card>

          <Card>
            <h2 className="mb-2 font-medium">Passos da política aplicados</h2>
            <ol className="grid gap-2">
              {o.steps.map((s) => {
                const style = STEP_STYLE[s.result];
                return (
                  <li key={s.order} className="flex gap-3 text-sm">
                    <span className={`w-28 shrink-0 font-medium ${style.className}`}><span aria-hidden>{style.icon} </span>{style.label}</span>
                    <span><span className="font-medium">{s.order}. {s.title}:</span> {s.detail}</span>
                  </li>
                );
              })}
            </ol>
          </Card>

          <div className="grid gap-4 md:grid-cols-3">
            <Facts title="Cliente" rows={[
              ["Cliente", o.customer_id],
              ["Data do pedido", date(o.order_date)],
              ["Ocupação", o.employment_type],
              ["Renda declarada", brl(o.income_declared)],
              ["Parcela", brl(o.installment)],
              ["Comprometimento da renda", pct(o.income_commitment)],
            ]} />
            <Facts title="Bureau" rows={[
              ["Score", int(o.bureau.score)],
              ["Restrições ativas", int(o.bureau.active_restrictions)],
              ["Parcelas em outras instituições", brl(o.bureau.other_installments)],
              ["Consultas em 90 dias", int(o.bureau.inquiries_90d)],
              ["Meses de histórico", int(o.bureau.bureau_history_months)],
            ]} />
            <Facts title="Conta na Fortuna" rows={[
              ["Meses de histórico", int(o.account.months_of_history)],
              ["Salário médio que entra", brl(o.account.avg_salary_inflow)],
              ["Entradas médias", brl(o.account.avg_total_inflow)],
              ["Saídas médias", brl(o.account.avg_outflow)],
              ["Menor saldo", brl(o.account.min_balance)],
              ["Dias de cheque especial (12 meses)", int(o.account.overdraft_days_12m)],
            ]} />
          </div>
        </div>
      )}
    </div>
  );
}
