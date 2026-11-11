"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { brl, int, pct } from "@/lib/format";
import { Section, Stat, Status } from "./ui";

export default function Overview() {
  const { data, isLoading, error } = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  return (
    <Section title="Visão geral" subtitle="Os 2.000 pedidos novos: política proposta × regra antiga (score > 600, renda > R$ 2.000, sem restrições).">
      <Status loading={isLoading} error={error} />
      {data && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Ganho esperado sobre a regra antiga" value={brl(data.gain)} hint={`${brl(data.proposed_policy.expected_result)} contra ${brl(data.current_policy.expected_result)}`} />
          <Stat label="Aprovados pela proposta" value={int(data.proposed_policy.approved)} hint={`Regra antiga: ${int(data.current_policy.approved)} de ${int(data.new_orders_total)}`} />
          <Stat label="Valor aprovado" value={brl(data.proposed_policy.approved_amount)} hint={`Regra antiga: ${brl(data.current_policy.approved_amount)}`} />
          <Stat label="Inadimplência histórica" value={pct(data.base_default_rate)} hint={`${int(data.historical_mature_total)} contratos já encerrados`} />
        </div>
      )}
    </Section>
  );
}
