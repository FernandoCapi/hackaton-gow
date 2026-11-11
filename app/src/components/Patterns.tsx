"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info, Search, Sparkle, TrendingDown, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Pattern } from "@/lib/api";
import { int, pct } from "@/lib/format";
import { Card, IconChip, Section, Status } from "./ui";

const POLICY_VIEW: Record<Pattern["current_policy_view"], string> = {
  approves: "Regra antiga aprova",
  denies: "Regra antiga nega",
  mixed: "Regra antiga aprova parte",
};

function PatternChart({ pattern }: { pattern: Pattern }) {
  return (
    <ResponsiveContainer width="100%" height={56 + pattern.groups.length * 40}>
      <BarChart data={pattern.groups} layout="vertical" margin={{ left: 8, right: 48, top: 20 }}>
        <CartesianGrid horizontal={false} stroke="var(--border)" />
        <XAxis type="number" tickFormatter={pct} tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--border)" />
        <YAxis type="category" dataKey="label" width={170} tick={{ fill: "var(--foreground)", fontSize: 12 }} stroke="var(--border)" />
        <Tooltip
          cursor={{ fill: "var(--border)", opacity: 0.4 }}
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, color: "var(--foreground)" }}
          formatter={(value, _name, item) => [`${pct(Number(value))} (${int(item.payload.customers)} clientes)`, "Inadimplência"]}
        />
        <ReferenceLine
          x={pattern.overall_default_rate}
          stroke="var(--muted)"
          strokeDasharray="4 4"
          label={{ value: `média ${pct(pattern.overall_default_rate)}`, position: "top", fill: "var(--muted)", fontSize: 12 }}
        />
        <Bar dataKey="default_rate" radius={[0, 6, 6, 0]} barSize={20}>
          {pattern.groups.map((group) => (
            <Cell key={group.label} fill={group.default_rate > pattern.overall_default_rate ? "var(--critical)" : "var(--series-1)"} fillOpacity={0.85} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function PatternCard({ pattern }: { pattern: Pattern }) {
  const worse = pattern.direction === "worse";
  const trap = pattern.kind === "trap";
  const border = trap ? "border-l-gold" : worse ? "border-l-critical" : "border-l-good";
  return (
    <Card className={`border-l-4 ${border}`}>
      <div className="flex items-start gap-3">
        <IconChip icon={trap ? Info : worse ? TrendingUp : TrendingDown} tone={trap ? "gold" : worse ? "critical" : "good"} />
        <div className="min-w-0">
          <p className="font-medium leading-snug">{pattern.sentence}</p>
          <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
            <span className={`rounded-full px-2 py-0.5 font-medium ${worse ? "bg-critical/10 text-critical" : "bg-good/10 text-good"}`}>
              {worse ? "Paga pior que a média" : "Paga melhor que a média"}
            </span>
            <span className="rounded-full bg-surface-2 px-2 py-0.5 text-muted ring-1 ring-border">{POLICY_VIEW[pattern.current_policy_view]}</span>
            {pattern.policy_step && (
              <span className="rounded-full bg-accent-soft px-2 py-0.5 font-medium text-accent">Passo: {pattern.policy_step}</span>
            )}
            {pattern.evidence === "piloto" && (
              <span className="rounded-full bg-surface-2 px-2 py-0.5 text-muted ring-1 ring-border">Base: piloto sorteado</span>
            )}
            {pattern.new_orders_affected != null && (
              <span className="rounded-full bg-gold-soft px-2 py-0.5 font-medium text-gold">{int(pattern.new_orders_affected)} pedidos novos no grupo</span>
            )}
          </div>
        </div>
      </div>
      {pattern.caveat && (
        <p className="mt-3 flex gap-2 rounded-lg bg-surface-2 px-3 py-2 text-xs text-muted">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden /> {pattern.caveat}
        </p>
      )}
      <div className="mt-3"><PatternChart pattern={pattern} /></div>
    </Card>
  );
}

const GROUPS = [
  { kind: "risk", icon: AlertTriangle, tone: "text-critical", title: "Onde a regra antiga aprova e perde dinheiro" },
  { kind: "opportunity", icon: Sparkle, tone: "text-good", title: "Onde a regra antiga nega quem pagaria" },
  { kind: "trap", icon: Info, tone: "text-gold", title: "Parecem perigosos, mas não são" },
] as const;

export default function Patterns() {
  const { data, isLoading, error } = useQuery({ queryKey: ["patterns"], queryFn: api.patterns });
  // older API versions do not send `kind`: fall back to the direction of the effect
  const kindOf = (p: Pattern) => p.kind ?? (p.direction === "worse" ? "risk" : "opportunity");
  return (
    <Section icon={Search} title="Padrões encontrados" subtitle="Grupos de clientes que pagam pior ou melhor que a média, no histórico de contratos com desfecho conhecido.">
      <Status loading={isLoading} error={error} />
      {data && (
        <div className="grid gap-8">
          {GROUPS.map((group) => {
            const items = data.filter((p) => kindOf(p) === group.kind);
            if (!items.length) return null;
            const Icon = group.icon;
            return (
              <div key={group.kind}>
                <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted">
                  <Icon className={`size-4 ${group.tone}`} aria-hidden /> {group.title} · {items.length}
                </h2>
                <div className="grid gap-4 lg:grid-cols-2">
                  {items.map((pattern) => <PatternCard key={pattern.id} pattern={pattern} />)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Section>
  );
}
