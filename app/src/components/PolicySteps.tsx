"use client";

import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, Ban, Clock, FlaskConical, Gauge, Scale, Wallet } from "lucide-react";
import Link from "next/link";
import { api, type Policy } from "@/lib/api";
import { Section, Status } from "./ui";

const OUTCOME: Record<Policy["steps"][number]["outcome"], { label: string; className: string; dot: string; icon: typeof Ban }> = {
  approve: { label: "Aprova", className: "bg-good/10 text-good", dot: "bg-good", icon: BadgeCheck },
  deny: { label: "Nega", className: "bg-critical/10 text-critical", dot: "bg-critical", icon: Ban },
  amount: { label: "Valor", className: "bg-gold-soft text-gold", dot: "bg-gold", icon: Wallet },
};

export default function PolicySteps() {
  const { data, isLoading, error } = useQuery({ queryKey: ["policy"], queryFn: api.policy });
  const approvedAt = data?.approved_at ? new Date(data.approved_at).toLocaleString("pt-BR") : null;
  return (
    <Section icon={Scale} title="Política proposta" subtitle="Aplicada nesta ordem a cada pedido novo: quem pode ser aprovado, o que nega e com qual valor.">
      <Status loading={isLoading} error={error} />
      {data && (
        <>
          <div className={`mb-6 flex flex-wrap items-center gap-2 rounded-xl px-4 py-3 text-sm ${approvedAt ? "bg-good/10 text-good" : "bg-warning-bg text-warning-fg"}`}>
            {approvedAt ? <BadgeCheck className="size-4" aria-hidden /> : <Clock className="size-4" aria-hidden />}
            <span className="font-medium">Versão {data.version}</span>
            <span>· {approvedAt ? `aprovada por ${data.approved_by} em ${approvedAt}` : "proposta, ainda não aprovada pelo analista"}</span>
            {data.note && <span className="opacity-80">· {data.note}</span>}
          </div>

          <ol className="relative grid gap-4 pl-12 before:absolute before:top-2 before:bottom-2 before:left-[19px] before:w-0.5 before:bg-border">
            {data.steps.map((step) => {
              const outcome = OUTCOME[step.outcome]; // older API versions do not send outcome
              const Icon = outcome?.icon ?? Gauge;
              return (
                <li key={step.order} className="relative">
                  <span className={`absolute -left-12 top-1 grid size-10 place-items-center rounded-full text-sm font-semibold text-on-solid ring-4 ring-background ${outcome?.dot ?? "bg-accent"}`}>
                    {step.order}
                  </span>
                  <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Icon className="size-4 text-muted" aria-hidden />
                      <p className="font-medium">{step.title}</p>
                      {outcome && <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${outcome.className}`}>{outcome.label}</span>}
                    </div>
                    <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-foreground/85">{step.rule_text}</p>
                  </div>
                </li>
              );
            })}
          </ol>
          <Link href="/laboratorio" className="mt-6 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-on-solid shadow-sm hover:bg-accent-strong">
            <FlaskConical className="size-4" aria-hidden />
            {data.approved_by ? "Testar outros limites" : "Testar e aprovar no laboratório"}
          </Link>
        </>
      )}
    </Section>
  );
}
