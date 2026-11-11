"use client";

import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type Pattern } from "@/lib/api";
import { int, pct } from "@/lib/format";
import { Card, Section, Status } from "./ui";

const POLICY_VIEW: Record<Pattern["current_policy_view"], string> = {
  approves: "A regra antiga aprova esse grupo",
  denies: "A regra antiga nega esse grupo",
  mixed: "A regra antiga aprova parte desse grupo",
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
          contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--foreground)" }}
          formatter={(value, _name, item) => [`${pct(Number(value))} (${int(item.payload.customers)} clientes)`, "Inadimplência"]}
        />
        <ReferenceLine
          x={pattern.overall_default_rate}
          stroke="var(--muted)"
          strokeDasharray="4 4"
          label={{ value: `média ${pct(pattern.overall_default_rate)}`, position: "top", fill: "var(--muted)", fontSize: 12 }}
        />
        <Bar dataKey="default_rate" fill="var(--series-1)" radius={[0, 4, 4, 0]} barSize={20} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export default function Patterns() {
  const { data, isLoading, error } = useQuery({ queryKey: ["patterns"], queryFn: api.patterns });
  return (
    <Section title="Padrões encontrados" subtitle="Grupos de clientes que pagam pior ou melhor que a média, no histórico de contratos encerrados.">
      <Status loading={isLoading} error={error} />
      <div className="grid gap-4 lg:grid-cols-2">
        {data?.map((pattern) => (
          <Card key={pattern.id}>
            <p className="font-medium">{pattern.sentence}</p>
            <p className="mt-2 text-sm text-muted">
              <span aria-hidden>{pattern.direction === "worse" ? "▲ " : "▼ "}</span>
              {pattern.direction === "worse" ? "Paga pior que a média" : "Paga melhor que a média"} · {POLICY_VIEW[pattern.current_policy_view]}
            </p>
            <div className="mt-3"><PatternChart pattern={pattern} /></div>
          </Card>
        ))}
      </div>
    </Section>
  );
}
