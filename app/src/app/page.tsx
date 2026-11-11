"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import Overview from "@/components/Overview";
import { api } from "@/lib/api";
import { int } from "@/lib/format";

export default function Home() {
  const patterns = useQuery({ queryKey: ["patterns"], queryFn: api.patterns });
  const policy = useQuery({ queryKey: ["policy"], queryFn: api.policy });
  const changed = useQuery({ queryKey: ["orders", { changed: true, page_size: 1 }], queryFn: () => api.orders({ changed: true, page_size: 1 }) });

  const pending = policy.data && !policy.data.approved_by;
  const steps = [
    {
      href: "/padroes",
      title: "Padrões encontrados",
      text: patterns.data ? `${patterns.data.length} grupos de clientes pagam diferente da média.` : "Grupos que pagam pior ou melhor que a média.",
      action: "Ver padrões",
    },
    {
      href: "/politica",
      title: "Política proposta",
      text: pending
        ? "A proposta da IA aguarda a sua aprovação."
        : policy.data ? `Versão ${policy.data.version} aprovada por ${policy.data.approved_by}.` : "Regras aplicadas a cada pedido, em ordem.",
      action: pending ? "Revisar política" : "Ver política",
      highlight: pending,
    },
    {
      href: "/laboratorio",
      title: "Laboratório",
      text: "Mude os limites e veja o efeito em reais antes de aprovar.",
      action: "Abrir laboratório",
    },
    {
      href: "/pedidos",
      title: "Pedidos novos",
      text: changed.data ? `${int(changed.data.total)} decisões mudam em relação à regra antiga.` : "Decisão e motivos de cada pedido.",
      action: "Ver pedidos",
    },
  ];

  return (
    <>
      <Overview />
      <section aria-labelledby="next-steps">
        <h2 id="next-steps" className="mb-3 text-base font-semibold">Por onde seguir</h2>
        <ol className="grid gap-3 sm:grid-cols-2">
          {steps.map((step, i) => (
            <li key={step.href}>
              <Link
                href={step.href}
                className={`flex h-full gap-3 rounded-lg border bg-surface p-4 hover:border-accent ${step.highlight ? "border-accent" : "border-border"}`}
              >
                <span aria-hidden className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent tabular-nums">{i + 1}</span>
                <span>
                  <span className="block font-medium">{step.title}</span>
                  <span className="mt-1 block text-sm text-muted">{step.text}</span>
                  <span className="mt-2 block text-sm font-medium text-accent">{step.action}</span>
                </span>
              </Link>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
