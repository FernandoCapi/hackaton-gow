"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type ParamSpec, type Policy, type PolicyParams } from "@/lib/api";
import { brl, int, paramValue } from "@/lib/format";
import { Card, Section, Stat, Status } from "./ui";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

function Control({ spec, value, onChange }: { spec: ParamSpec; value: number | string; onChange: (v: number | string) => void }) {
  const id = `param-${spec.name}`;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium">{spec.label}</label>
        {spec.kind === "number" && <span className="text-sm tabular-nums">{paramValue(value, spec.unit)}</span>}
      </div>
      {spec.kind === "select" ? (
        <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-sm">
          {spec.options?.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      ) : (
        <input
          id={id}
          type="range"
          min={spec.min ?? undefined}
          max={spec.max ?? undefined}
          step={spec.step ?? undefined}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="mt-1 w-full accent-[var(--series-1)]"
        />
      )}
      <p className="mt-1 text-xs text-muted">{spec.description}</p>
    </div>
  );
}

function ApproveForm({ params }: { params: PolicyParams }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [note, setNote] = useState("");
  const approve = useMutation({
    mutationFn: () => api.approve(params, name.trim(), note.trim() || undefined),
    onSuccess: () => {
      for (const key of ["policy", "summary", "orders"]) queryClient.invalidateQueries({ queryKey: [key] });
    },
  });
  return (
    <form
      onSubmit={(e) => { e.preventDefault(); approve.mutate(); }}
      className="mt-4 flex flex-col gap-2 border-t border-border pt-4"
    >
      <p className="text-sm font-medium">Aprovar estes parâmetros como política em vigor</p>
      <label htmlFor="approved-by" className="sr-only">Nome do analista</label>
      <input id="approved-by" required value={name} onChange={(e) => setName(e.target.value)} placeholder="Nome do analista" className="rounded-md border border-border bg-background px-2 py-1.5 text-sm" />
      <label htmlFor="approve-note" className="sr-only">Observação</label>
      <input id="approve-note" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Observação (opcional)" className="rounded-md border border-border bg-background px-2 py-1.5 text-sm" />
      <button disabled={approve.isPending || !name.trim()} className="rounded-md bg-foreground px-3 py-1.5 text-sm text-background disabled:opacity-50">
        {approve.isPending ? "Aprovando…" : "Aprovar política"}
      </button>
      {approve.isError && <p role="alert" className="text-sm text-critical">{approve.error.message}</p>}
    </form>
  );
}

function LabBody({ policy }: { policy: Policy }) {
  const [params, setParams] = useState<PolicyParams>(policy.params);
  const debounced = useDebounced(params, 300);
  // keepPreviousData keeps the last result on screen; the query key is the params, so a stale response never wins.
  const sim = useQuery({ queryKey: ["simulate", debounced], queryFn: () => api.simulate(debounced), placeholderData: keepPreviousData });
  const values = params as Record<string, number | string>;
  const data = sim.data;

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <Card>
        <div className="flex flex-col gap-5">
          {policy.param_specs.map((spec) => (
            <Control key={spec.name} spec={spec} value={values[spec.name] ?? spec.value} onChange={(v) => setParams({ ...params, [spec.name]: v })} />
          ))}
        </div>
        <button type="button" onClick={() => setParams(policy.params)} className="mt-4 text-sm text-muted underline">Voltar aos parâmetros em vigor</button>
        <ApproveForm params={params} />
      </Card>

      <div className={sim.isFetching ? "opacity-70 transition-opacity" : "transition-opacity"}>
        <Status loading={sim.isLoading} error={sim.error} />
        {data && (
          <>
            <h3 className="mb-2 text-sm font-medium text-muted">No histórico (contratos encerrados)</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <Stat label="Ganho sobre a regra antiga" value={brl(data.historical.gain)} hint={`${brl(data.historical.proposed_result)} contra ${brl(data.historical.current_result)}`} />
              <Stat label="Calotes evitados" value={int(data.historical.defaults_avoided)} hint="Aprovados pela regra antiga que a proposta nega" />
              <Stat label="Bons clientes ganhos" value={int(data.historical.good_customers_gained)} hint="Negados pela regra antiga que a proposta aprova" />
            </div>
            <h3 className="mb-2 mt-5 text-sm font-medium text-muted">Nos 2.000 pedidos novos</h3>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <Stat label="Aprovados" value={int(data.new_orders.approved)} hint={`Regra antiga: ${int(data.new_orders.current_approved)}`} />
              <Stat label="Valor total aprovado" value={brl(data.new_orders.total_approved_amount)} />
              <Stat label="Decisões que mudam" value={int(data.new_orders.changed_vs_current)} hint="Em relação à regra antiga" />
            </div>
            <Card className="mt-5">
              <h3 className="text-sm font-medium">Resultado no histórico por faixa de risco</h3>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={data.by_risk_band} margin={{ top: 16, right: 8, left: 8 }} barGap={2}>
                  <CartesianGrid vertical={false} stroke="var(--border)" />
                  <XAxis dataKey="band" tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--border)" />
                  <YAxis tickFormatter={(v: number) => brl(v)} width={90} tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--border)" />
                  <Tooltip
                    cursor={{ fill: "var(--border)", opacity: 0.4 }}
                    contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", color: "var(--foreground)" }}
                    formatter={(value) => brl(Number(value))}
                    labelFormatter={(band) => `Risco ${band}`}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar name="Regra antiga" dataKey="current_result" fill="var(--series-2)" radius={[4, 4, 0, 0]} />
                  <Bar name="Política proposta" dataKey="proposed_result" fill="var(--series-1)" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}

export default function Lab() {
  const { data: policy, isLoading, error } = useQuery({ queryKey: ["policy"], queryFn: api.policy });
  return (
    <Section title="Laboratório" subtitle="Teste outros parâmetros antes de aprovar. Simular não altera a política em vigor.">
      <Status loading={isLoading} error={error} />
      {policy?.approved_by && (
        <p role="status" className="mb-4 text-sm">
          <span className="text-good">✓ Em vigor: versão {policy.version}, aprovada por {policy.approved_by}.</span>{" "}
          <Link href="/politica" className="font-medium text-accent underline">Ver política aprovada</Link>
        </p>
      )}
      {/* key by version: after an approval the controls restart from the new policy */}
      {policy && <LabBody key={policy.version} policy={policy} />}
    </Section>
  );
}
