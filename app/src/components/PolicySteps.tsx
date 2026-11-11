"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { Card, Section, Status } from "./ui";

export default function PolicySteps() {
  const { data, isLoading, error } = useQuery({ queryKey: ["policy"], queryFn: api.policy });
  const approvedAt = data?.approved_at ? new Date(data.approved_at).toLocaleString("pt-BR") : null;
  return (
    <Section title="Política proposta" subtitle="Aplicada nesta ordem a cada pedido novo.">
      <Status loading={isLoading} error={error} />
      {data && (
        <>
          <p className="mb-3 text-sm text-muted">
            Versão {data.version} ·{" "}
            {approvedAt ? `aprovada por ${data.approved_by} em ${approvedAt}` : "proposta da IA, ainda não aprovada pelo analista"}
            {data.note && ` · ${data.note}`}
          </p>
          <ol className="grid gap-3 md:grid-cols-2">
            {data.steps.map((step) => (
              <li key={step.order}>
                <Card className="h-full">
                  <p className="text-sm text-muted">Passo {step.order}</p>
                  <p className="font-medium">{step.title}</p>
                  <p className="mt-1 text-sm">{step.rule_text}</p>
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
