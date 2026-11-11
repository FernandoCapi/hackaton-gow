"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, BadgeCheck, Banknote, FlaskConical, LayoutDashboard, Scale, Search, ShieldAlert, Target, TrendingUp } from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { brl, int, pct } from "@/lib/format";
import { Card, ExtraBadge, IconChip, Section, Stat, Status } from "./ui";

const JOURNEY = [
  { href: "/padroes", icon: Search, title: "1. Padrões", text: "Quem paga pior ou melhor que a média, e onde a regra antiga erra." },
  { href: "/politica", icon: Scale, title: "2. Política", text: "Os passos que decidem cada pedido, na ordem em que são aplicados." },
  { href: "/laboratorio", icon: FlaskConical, title: "3. Laboratório", text: "Mude os limites, veja o efeito em reais e aprove." },
];

export default function Overview() {
  const { data, isLoading, error } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  return (
    <Section icon={LayoutDashboard} title="Visão geral" subtitle="Os 2.000 pedidos novos: política proposta × regra antiga (score > 600, renda > R$ 2.000, sem restrições, parcela até 30% da renda).">
      <Status loading={isLoading} error={error} />
      {data && (
        <div className="grid gap-5">
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-sidebar via-[#0f3d36] to-accent-strong p-6 text-white shadow-lg md:p-8">
            <div className="absolute -right-10 -top-10 size-48 rounded-full bg-gold/20 blur-2xl" aria-hidden />
            <p className="flex items-center gap-2 text-sm text-white/75"><TrendingUp className="size-4" aria-hidden /> Ganho esperado sobre a regra antiga</p>
            <p className="mt-2 text-4xl font-semibold tracking-tight tabular-nums md:text-5xl">{brl(data.gain)}</p>
            <p className="mt-2 text-sm text-white/75">
              {brl(data.proposed_policy.expected_result)} com a política proposta, contra {brl(data.current_policy.expected_result)} da regra antiga
              {" "}(+15% pago em dia, +5% com atraso, −60% sem pagamento).
            </p>
            <div className="mt-5 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-white/10 px-3 py-1 ring-1 ring-white/15">Qualidade do modelo: {data.model.auc.toFixed(2).replace(".", ",")} (score do bureau: {data.model.auc_current_rule.toFixed(2).replace(".", ",")})</span>
              <span className="rounded-full bg-white/10 px-3 py-1 ring-1 ring-white/15">Validado em {data.model.validated_on}</span>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <Stat icon={BadgeCheck} tone="good" label="Aprovados pela proposta" value={int(data.proposed_policy.approved)} hint={`Regra antiga: ${int(data.current_policy.approved)} de ${int(data.new_orders_total)}`} />
            <Stat icon={Banknote} tone="gold" label="Valor aprovado" value={brl(data.proposed_policy.approved_amount)} hint={`Regra antiga: ${brl(data.current_policy.approved_amount)}`} />
            <Stat icon={ShieldAlert} tone="critical" label="Inadimplência histórica" value={pct(data.base_default_rate)} hint={`${int(data.historical_mature_total)} contratos com desfecho conhecido`} />
            <Stat icon={Target} label="Negados pela proposta" value={int(data.proposed_policy.denied)} hint={`Regra antiga: ${int(data.current_policy.denied)}`} />
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {JOURNEY.map((step) => (
              <Link key={step.href} href={step.href} className="group">
                <Card className="h-full transition hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-md">
                  <div className="flex items-center justify-between">
                    <IconChip icon={step.icon} />
                    <ArrowRight className="size-4 text-muted transition group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden />
                  </div>
                  <p className="mt-3 font-medium">{step.title}</p>
                  <p className="mt-1 text-sm text-muted">{step.text}</p>
                </Card>
              </Link>
            ))}
          </div>

          {data.counteroffers != null && data.counteroffers > 0 && (
            <Card className="border-dashed border-extra/40 bg-extra-soft/40">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <IconChip icon={Banknote} tone="extra" />
                  <div>
                    <p className="flex items-center gap-2 font-medium">Contraproposta para negados <ExtraBadge /></p>
                    <p className="mt-1 max-w-2xl text-sm text-muted">
                      <span className="font-medium text-foreground">{int(data.counteroffers)} pedidos</span> negados por capacidade ou risco seriam
                      aprovados com um valor menor, pelas mesmas regras. Vira oferta de venda e explicação ao cliente.
                      Não entra no arquivo oficial de decisões.
                    </p>
                  </div>
                </div>
                <Link href="/pedidos" className="rounded-lg bg-extra px-3 py-1.5 text-sm font-medium text-white hover:brightness-110">Ver pedidos</Link>
              </div>
            </Card>
          )}
        </div>
      )}
    </Section>
  );
}
