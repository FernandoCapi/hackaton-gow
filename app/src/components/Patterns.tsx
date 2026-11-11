"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Pattern } from "@/lib/api";
import { int, pct } from "@/lib/format";
import { Card, Section, Status } from "./ui";

type Kind = NonNullable<Pattern["kind"]>;

// Short card titles; the full sentence stays under "Detalhes". Unknown ids fall back to group_description.
const TITLES: Record<string, string> = {
  outflow_over_inflow: "Saídas acima de 90% das entradas",
  recent_overdraft: "Cheque especial recente",
  account_drain: "Conta esvaziada antes do pedido",
  credit_seeking: "8 ou mais consultas ao CPF em 90 dias",
  inflated_income: "Entradas abaixo de 60% da renda",
  installment_over_slack: "Parcela acima de 45% da sobra do mês",
  amount_cut_by_30pct_rule: "Valor cortado pela regra dos 30%",
  total_debt_burden: "Dívidas somadas acima de 44% da renda",
  new_account: "Conta aberta há até 3 meses",
  active_restriction: "Restrição ativa no bureau",
  denied_with_healthy_account: "Negados hoje com conta saudável",
  score_does_not_predict: "Score até 600, sem restrição",
  income_1500_2000: "Renda entre R$ 1.500 e R$ 2.000",
  long_term: "Prazo de 36 meses",
  large_amount: "Valor acima de R$ 20 mil",
};

const KINDS: { kind: Kind; label: string; tab: string; hint: string; color: string }[] = [
  { kind: "risk", label: "Aprovados hoje com calote alto", tab: "Calote alto", hint: "A regra atual aprova; o grupo tem calote acima da base", color: "var(--critical)" },
  { kind: "opportunity", label: "Negados hoje com calote baixo", tab: "Calote baixo", hint: "A regra atual nega; no piloto, o grupo pagou", color: "var(--good)" },
  { kind: "trap", label: "Risco que depende de outro fator", tab: "Risco combinado", hint: "Calote alto só quando combinado com outra variável", color: "var(--series-1)" },
];

const EVIDENCE: Record<NonNullable<Pattern["evidence"]>, string> = {
  historico_maduro: "Contratos com 12+ meses",
  piloto: "Piloto (calote ainda parcial)",
};

const POLICY_VIEW: Record<Pattern["current_policy_view"], string> = {
  approves: "Regra atual aprova",
  denies: "Regra atual nega",
  mixed: "Regra atual aprova parte",
};

/** "… contra 9,7% de quem a política atual aprovaria. …" -> "de quem a política atual aprovaria" */
function comparisonLabel(sentence: string): string {
  return sentence.match(/contra [\d.,]+% (.+?)\.(?:\s|$)/)?.[1] ?? "da média";
}

/** The bar that is the pattern's own group, if it is drawn (some charts come from another base). */
function highlightIndex(pattern: Pattern): number {
  const diffs = pattern.groups.map((g) => Math.abs(g.default_rate - pattern.group_default_rate));
  const best = diffs.indexOf(Math.min(...diffs));
  return diffs[best] < 0.002 ? best : -1;
}

function PatternChart({ pattern, color }: { pattern: Pattern; color: string }) {
  const highlight = highlightIndex(pattern);
  return (
    <>
    <ResponsiveContainer width="100%" height={48 + pattern.groups.length * 32}>
      <BarChart data={pattern.groups} layout="vertical" margin={{ left: 8, right: 48, top: 20 }}>
        <CartesianGrid horizontal={false} stroke="var(--border)" />
        <XAxis type="number" tickFormatter={pct} tick={{ fill: "var(--foreground)", fontSize: 11 }} stroke="var(--border)" />
        <YAxis type="category" dataKey="label" width={150} tick={{ fill: "var(--foreground)", fontSize: 11 }} stroke="var(--border)" />
        <Tooltip
          cursor={{ fill: "var(--border)", opacity: 0.4 }}
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--foreground)" }}
          labelStyle={{ color: "var(--foreground)", fontWeight: 600 }}
          itemStyle={{ color: "var(--foreground)" }}
          separator=": "
          formatter={(value, _name, item) => [`${pct(Number(value))} (${int(item.payload.customers)} clientes)`, "Calote"]}
        />
        <ReferenceLine
          x={pattern.overall_default_rate}
          stroke="var(--muted)"
          strokeDasharray="4 4"
          label={{ value: `base ${pct(pattern.overall_default_rate)}`, position: "top", fill: "var(--foreground)", fontSize: 11 }}
        />
        <Bar dataKey="default_rate" radius={[0, 4, 4, 0]} barSize={16}>
          {pattern.groups.map((g, i) => (
            <Cell key={g.label} fill={highlight === -1 || i === highlight ? color : "var(--muted)"} fillOpacity={i === highlight || highlight === -1 ? 1 : 0.55} />
          ))}
          <LabelList dataKey="customers" position="right" formatter={(n) => int(Number(n))} fill="var(--muted)" fontSize={11} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
    <p className="text-xs text-muted">Número ao lado da barra: clientes no grupo.</p>
    </>
  );
}

/** Two groups: the chart only repeats the headline number, so list them with their size instead. */
function PatternPair({ pattern, color }: { pattern: Pattern; color: string }) {
  const highlight = highlightIndex(pattern);
  return (
    <ul className="divide-y divide-border rounded-md border border-border text-sm">
      {pattern.groups.map((g, i) => (
        <li key={g.label} className="flex items-baseline justify-between gap-3 px-3 py-2">
          <span>{g.label}</span>
          <span className="whitespace-nowrap">
            <span className="font-semibold tabular-nums" style={{ color: i === highlight ? color : undefined }}>{pct(g.default_rate)}</span>
            <span className="ml-2 text-xs text-muted tabular-nums">{int(g.customers)} clientes</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return <span className="rounded-full border border-border px-2 py-0.5 text-xs text-foreground/80">{children}</span>;
}

function PatternCard({ pattern, color }: { pattern: Pattern; color: string }) {
  return (
    <Card>
      <h3 className="font-semibold">{TITLES[pattern.id] ?? pattern.group_description}</h3>
      <p className="mt-2 flex flex-wrap items-baseline gap-x-2">
        <span className="text-3xl font-semibold tabular-nums" style={{ color }}>{pct(pattern.group_default_rate)}</span>
        <span className="text-sm text-muted">
          de calote vs {pct(pattern.overall_default_rate)} {comparisonLabel(pattern.sentence)}
        </span>
      </p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {pattern.policy_step && (
          <Link href="/politica" className="rounded-full border border-accent/50 bg-accent-soft px-2 py-0.5 text-xs font-medium text-foreground hover:underline">
            Passo: {pattern.policy_step}
          </Link>
        )}
        {pattern.new_orders_affected != null && (
          <span className="rounded-full border border-border px-2 py-0.5 text-xs font-medium">
            {int(pattern.new_orders_affected)} pedidos novos
          </span>
        )}
        <Tag>{POLICY_VIEW[pattern.current_policy_view]}</Tag>
        {pattern.evidence && <Tag>{EVIDENCE[pattern.evidence]}</Tag>}
      </div>
      <div className="mt-3">
        {pattern.groups.length === 2 ? <PatternPair pattern={pattern} color={color} /> : <PatternChart pattern={pattern} color={color} />}
      </div>
      <details className="mt-1 text-sm">
        <summary className="cursor-pointer text-foreground/80">Detalhes</summary>
        <p className="mt-2">{pattern.sentence}</p>
        {pattern.caveat && (
          <p className="mt-2 rounded-md bg-warning-bg px-3 py-2 text-xs text-warning-fg">
            <span aria-hidden>⚠ </span>{pattern.caveat}
          </p>
        )}
      </details>
    </Card>
  );
}

export default function Patterns() {
  const { data, isLoading, error } = useQuery({ queryKey: ["patterns"], queryFn: api.patterns });
  const [tab, setTab] = useState<Kind>("risk");
  const byKind = (kind: Kind) =>
    (data ?? [])
      .filter((p) => (p.kind ?? "risk") === kind)
      .sort((a, b) => (b.new_orders_affected ?? -1) - (a.new_orders_affected ?? -1));

  return (
    <Section title="Padrões encontrados" subtitle="Grupos que pagam pior ou melhor do que a regra atual supõe, no histórico e no piloto.">
      <Status loading={isLoading} error={error} />
      {data && (
        <>
          <div role="tablist" aria-label="Tipo de padrão" className="mb-4 inline-flex flex-wrap gap-1 rounded-lg bg-border/40 p-1">
            {KINDS.map(({ kind, tab: short, color }) => (
              <button
                key={kind}
                type="button"
                role="tab"
                aria-selected={tab === kind}
                onClick={() => setTab(kind)}
                className={`flex items-center gap-2 whitespace-nowrap rounded-md px-4 py-2 text-sm font-medium transition ${tab === kind ? "bg-surface shadow-sm" : "text-foreground/70 hover:text-foreground"}`}
              >
                <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: color }} />
                {short}
                <span className="tabular-nums text-muted">{byKind(kind).length}</span>
              </button>
            ))}
          </div>
          {KINDS.filter(({ kind }) => kind === tab).map(({ kind, label, hint, color }) => (
            <div key={kind} role="tabpanel">
              <p className="mb-4 text-sm text-muted"><span className="font-medium text-foreground">{label}.</span> {hint}</p>
              {byKind(kind).length ? (
                <div className="grid gap-4 lg:grid-cols-2">
                  {byKind(kind).map((p) => <PatternCard key={p.id} pattern={p} color={color} />)}
                </div>
              ) : (
                <p className="text-sm text-muted">Nenhum padrão neste grupo.</p>
              )}
            </div>
          ))}
        </>
      )}
    </Section>
  );
}
