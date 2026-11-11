import type { LucideIcon } from "lucide-react";
import { Check, Sparkles, X } from "lucide-react";

export function Section({ title, subtitle, icon: Icon, children }: { title: string; subtitle?: string; icon?: LucideIcon; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <header className="mb-6 flex items-start gap-3">
        {Icon && (
          <span className="mt-0.5 grid size-10 shrink-0 place-items-center rounded-xl bg-accent-soft text-accent">
            <Icon className="size-5" aria-hidden />
          </span>
        )}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p>}
        </div>
      </header>
      {children}
    </section>
  );
}

export function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-border bg-surface p-5 shadow-sm ${className}`}>{children}</div>;
}

const TONES = {
  accent: "bg-accent-soft text-accent",
  good: "bg-good/10 text-good",
  critical: "bg-critical/10 text-critical",
  gold: "bg-gold-soft text-gold",
  extra: "bg-extra-soft text-extra",
} as const;
export type Tone = keyof typeof TONES;

export function IconChip({ icon: Icon, tone = "accent", size = "md" }: { icon: LucideIcon; tone?: Tone; size?: "sm" | "md" }) {
  const box = size === "sm" ? "size-7 rounded-lg" : "size-9 rounded-xl";
  return (
    <span className={`grid shrink-0 place-items-center ${box} ${TONES[tone]}`}>
      <Icon className={size === "sm" ? "size-3.5" : "size-[18px]"} aria-hidden />
    </span>
  );
}

export function Stat({ label, value, hint, icon, tone = "accent" }: { label: string; value: string; hint?: string; icon?: LucideIcon; tone?: Tone }) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm text-muted">{label}</p>
        {icon && <IconChip icon={icon} tone={tone} size="sm" />}
      </div>
      <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </Card>
  );
}

export function Status({ loading, error }: { loading: boolean; error: Error | null }) {
  if (error) return <p role="alert" className="rounded-lg bg-critical/10 px-3 py-2 text-sm text-critical">{error.message}</p>;
  if (loading) return (
    <div className="flex items-center gap-2 text-sm text-muted">
      <span className="size-3 animate-pulse rounded-full bg-accent" aria-hidden /> Carregando…
    </div>
  );
  return null;
}

/** Marks what goes beyond the challenge: visible, but never mistaken for the official decision. */
export function ExtraBadge({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full bg-extra px-2 py-0.5 text-[11px] font-semibold tracking-wide text-white ${className}`}>
      <Sparkles className="size-3" aria-hidden /> EXTRA
    </span>
  );
}

/** `subtle` (outline only) is for reference values like the old rule, so the suggested decision stands out. */
export function DecisionBadge({ decision, subtle = false }: { decision: "APROVADO" | "NEGADO"; subtle?: boolean }) {
  const approved = decision === "APROVADO";
  const tone = approved
    ? subtle ? "border-good/40 text-good" : "border-transparent bg-good/15 text-good"
    : subtle ? "border-critical/40 text-critical" : "border-transparent bg-critical/15 text-critical";
  const Icon = approved ? Check : X;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${tone}`}>
      <Icon className="size-3" strokeWidth={3} aria-hidden />
      {approved ? "Aprovado" : "Negado"}
    </span>
  );
}

/** Default risk as a short colored bar: green below 10%, amber up to the 15% cutoff, red above. */
export function RiskMeter({ value, cutoff }: { value: number; cutoff?: number }) {
  const color = value < 0.1 ? "bg-good" : value <= (cutoff ?? 0.15) ? "bg-gold" : "bg-critical";
  return (
    <span className="inline-flex items-center gap-2">
      <span className="relative h-1.5 w-16 overflow-hidden rounded-full bg-border" aria-hidden>
        <span className={`absolute inset-y-0 left-0 rounded-full ${color}`} style={{ width: `${Math.min(100, value * 100 / 0.5)}%` }} />
      </span>
    </span>
  );
}
