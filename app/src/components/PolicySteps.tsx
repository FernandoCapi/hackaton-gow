"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api, type Policy } from "@/lib/api";
import { Card, Section, Status } from "./ui";

const OUTCOME: Record<Policy["steps"][number]["outcome"], { label: string; className: string }> = {
  approve: { label: "Aprova", className: "bg-accent-soft text-foreground" },
  deny: { label: "Nega", className: "bg-critical/10 text-critical" },
  amount: { label: "Valor", className: "bg-warning-bg text-warning-fg" },
};

export default function PolicySteps() {
  const { data, isLoading, error } = useQuery({ queryKey: ["policy"], queryFn: api.policy });
  const approvedAt = data?.approved_at ? new Date(data.approved_at).toLocaleString("pt-BR") : null;
  return (
    <Section title="Política proposta" subtitle="Aplicada nesta ordem a cada pedido novo: quem pode ser aprovado, o que nega e com qual valor.">
      <Status loading={isLoading} error={error} />
      {data && (
        <>
          <p className="mb-3 text-sm text-muted">
            Versão {data.version} ·{" "}
            {approvedAt ? `aprovada por ${data.approved_by} em ${approvedAt}` : "proposta, ainda não aprovada pelo analista"}
            {data.note && ` · ${data.note}`}
          </p>
          <ol className="grid gap-3 md:grid-cols-2">
            {data.steps.map((step) => (
              <li key={step.order}>
                <Card className="h-full">
                  <p className="flex items-center gap-2 text-sm text-muted">
                    Passo {step.order}
                    {/* older API versions do not send outcome */}
                    {OUTCOME[step.outcome] && (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${OUTCOME[step.outcome].className}`}>
                        {OUTCOME[step.outcome].label}
                      </span>
                    )}
                  </p>
                  <p className="mt-1 font-medium">{step.title}</p>
                  <p className="mt-1 whitespace-pre-line text-sm">{step.rule_text}</p>
                </Card>
              </li>
            ))}
          </ol>
          <Link href="/laboratorio" className="mt-4 inline-block rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white">
            {data.approved_by ? "Testar outros limites" : "Testar e aprovar no laboratório"}
          </Link>
        </>
      )}
    </Section>
  );
}
