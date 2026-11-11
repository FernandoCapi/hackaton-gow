"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowLeft, Building2, Check, HandCoins, Landmark, Lightbulb, UserRound, X } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import { api, type OrderDetail } from "@/lib/api";
import { brl, date, int, pct } from "@/lib/format";
import { Card, DecisionBadge, ExtraBadge, IconChip, Status } from "@/components/ui";
import type { LucideIcon } from "lucide-react";

const STEP_STYLE: Record<OrderDetail["steps"][number]["result"], { icon: LucideIcon; label: string; className: string }> = {
  passou: { icon: Check, label: "Passou", className: "bg-good text-on-solid" },
  negou: { icon: X, label: "Negou", className: "bg-critical text-on-solid" },
  ajustou: { icon: ArrowDownRight, label: "Ajustou o valor", className: "bg-gold text-on-solid" },
};

function Facts({ title, icon, rows }: { title: string; icon: LucideIcon; rows: [string, string][] }) {
  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <IconChip icon={icon} size="sm" />
        <h2 className="font-medium">{title}</h2>
      </div>
      <dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-sm">
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

function RiskGauge({ value, cutoff }: { value: number; cutoff: number }) {
  const color = value < cutoff * 0.66 ? "bg-good" : value <= cutoff ? "bg-gold" : "bg-critical";
  return (
    <div className="w-44">
      <div className="relative h-2 overflow-hidden rounded-full bg-border">
        <div className={`absolute inset-y-0 left-0 rounded-full ${color}`} style={{ width: `${Math.min(100, value * 100)}%` }} />
        <div className="absolute inset-y-0 w-0.5 bg-foreground/50" style={{ left: `${cutoff * 100}%` }} />
      </div>
      <p className="mt-1 text-[11px] text-muted">limite da política: {pct(cutoff)}</p>
    </div>
  );
}

function CounterofferCard({ o }: { o: OrderDetail }) {
  const c = o.counteroffer;
  if (!c) return null;
  return (
    <Card className="border-2 border-dashed border-extra/50 bg-extra-soft/40">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <IconChip icon={HandCoins} tone="extra" />
          <div>
            <p className="flex items-center gap-2 font-medium">Contraproposta <ExtraBadge /></p>
            <p className="mt-1 max-w-xl text-sm text-muted">
              O valor pedido não passa, mas as mesmas regras aprovariam um valor menor. Sugestão para oferecer ao cliente.
              <span className="font-medium text-foreground"> Não entra no arquivo oficial</span>, em que o pedido continua negado.
            </p>
          </div>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div><p className="text-xs text-muted">Valor sugerido</p><p className="text-xl font-semibold tabular-nums text-extra">{brl(c.amount)}</p></div>
        <div><p className="text-xs text-muted">Do valor pedido</p><p className="text-lg font-medium tabular-nums">{pct(c.share_of_request)}</p></div>
        <div><p className="text-xs text-muted">Parcela</p><p className="text-lg font-medium tabular-nums">{brl(c.installment)} × {o.term_months}</p></div>
        <div><p className="text-xs text-muted">Chance de calote</p><p className="text-lg font-medium tabular-nums">{pct(c.default_risk)}</p></div>
      </div>
    </Card>
  );
}

export default function OrderPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: o, isLoading, error } = useQuery({ queryKey: ["orders", "detail", id], queryFn: () => api.order(id), retry: false });
  const policy = useQuery({ queryKey: ["policy"], queryFn: api.policy });
  const cutoff = policy.data?.params.risk_cutoff ?? 0.15;
  const approved = o?.decision === "APROVADO";

  return (
    <div>
      <Link href="/pedidos" className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground"><ArrowLeft className="size-4" aria-hidden /> Pedidos</Link>
      <h1 className="mt-2 text-2xl font-semibold tracking-tight">Pedido {o?.order_id ?? decodeURIComponent(id).toUpperCase()}</h1>
      <div className="mt-2"><Status loading={isLoading} error={error} /></div>
      {o && (
        <div className="mt-4 grid gap-4">
          <Card className={`border-l-4 ${approved ? "border-l-good" : "border-l-critical"}`}>
            <div className="flex flex-wrap items-start gap-x-10 gap-y-4">
              <div><p className="text-xs uppercase tracking-wide text-muted">Decisão sugerida</p><div className="mt-1 scale-110 origin-left"><DecisionBadge decision={o.decision} /></div></div>
              <div><p className="text-xs uppercase tracking-wide text-muted">Valor aprovado</p><p className="text-2xl font-semibold tabular-nums">{brl(o.approved_amount)}</p></div>
              <div><p className="text-xs uppercase tracking-wide text-muted">Pedido</p><p className="text-lg tabular-nums">{brl(o.requested_amount)} em {o.term_months}x</p></div>
              <div><p className="text-xs uppercase tracking-wide text-muted">Chance de calote</p><p className="text-lg font-medium tabular-nums">{pct(o.default_risk)}</p><RiskGauge value={o.default_risk} cutoff={cutoff} /></div>
              <div><p className="text-xs uppercase tracking-wide text-muted">Regra antiga</p><p className="mt-1 flex items-center gap-2"><DecisionBadge decision={o.current_decision} subtle /> <span className="text-sm tabular-nums">{brl(o.current_approved_amount)}</span></p></div>
            </div>
            <div className="mt-5 rounded-lg bg-surface-2 p-4">
              <h2 className="flex items-center gap-2 font-medium"><Lightbulb className="size-4 text-gold" aria-hidden /> Por quê</h2>
              <ul className="mt-2 grid gap-1.5 text-sm">
                {o.reasons.map((r) => (
                  <li key={r} className="flex gap-2"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" aria-hidden />{r}</li>
                ))}
              </ul>
            </div>
          </Card>

          <CounterofferCard o={o} />

          <Card>
            <h2 className="mb-4 font-medium">Passos da política aplicados</h2>
            <ol className="relative grid gap-3 pl-10 before:absolute before:top-1 before:bottom-1 before:left-[13px] before:w-0.5 before:bg-border">
              {o.steps.map((s) => {
                const style = STEP_STYLE[s.result];
                const Icon = style.icon;
                return (
                  <li key={s.order} className="relative text-sm">
                    <span className={`absolute -left-10 top-0 grid size-7 place-items-center rounded-full ring-4 ring-surface ${style.className}`} title={style.label}>
                      <Icon className="size-3.5" strokeWidth={3} aria-hidden />
                    </span>
                    <p><span className="font-medium">{s.order}. {s.title}</span> <span className="text-muted">· {style.label}</span></p>
                    <p className="text-foreground/85">{s.detail}</p>
                  </li>
                );
              })}
            </ol>
          </Card>

          <div className="grid gap-4 md:grid-cols-3">
            <Facts title="Cliente" icon={UserRound} rows={[
              ["Cliente", o.customer_id],
              ["Data do pedido", date(o.order_date)],
              ["Ocupação", o.employment_type],
              ["Renda declarada", brl(o.income_declared)],
              ["Parcela", brl(o.installment)],
              ["Comprometimento da renda", pct(o.income_commitment)],
            ]} />
            <Facts title="Bureau" icon={Building2} rows={[
              ["Score", int(o.bureau.score)],
              ["Restrições ativas", int(o.bureau.active_restrictions)],
              ["Parcelas em outras instituições", brl(o.bureau.other_installments)],
              ["Consultas em 90 dias", int(o.bureau.inquiries_90d)],
              ["Meses de histórico", int(o.bureau.bureau_history_months)],
            ]} />
            <Facts title="Conta na Fortuna" icon={Landmark} rows={[
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
