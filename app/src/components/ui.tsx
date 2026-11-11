export function Section({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
      {subtitle && <p className="mb-4 text-sm text-muted">{subtitle}</p>}
      <div className={subtitle ? "" : "mt-4"}>{children}</div>
    </section>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-lg border border-border bg-surface p-4 ${className}`}>{children}</div>;
}

export function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </Card>
  );
}

export function Status({ loading, error }: { loading: boolean; error: Error | null }) {
  if (error) return <p role="alert" className="text-sm text-critical">{error.message}</p>;
  if (loading) return <p className="text-sm text-muted">Carregando…</p>;
  return null;
}

export function DecisionBadge({ decision }: { decision: "APROVADO" | "NEGADO" }) {
  const approved = decision === "APROVADO";
  return (
    <span className={`inline-flex items-center gap-1 text-sm font-medium ${approved ? "text-good" : "text-critical"}`}>
      <span aria-hidden>{approved ? "✓" : "✕"}</span>
      {approved ? "Aprovado" : "Negado"}
    </span>
  );
}
