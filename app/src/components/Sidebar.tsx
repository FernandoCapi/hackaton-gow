"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { exampleDataWarning } from "@/lib/health";
import OrderSearch from "./OrderSearch";

// The analyst's journey, in the order it is meant to be followed.
const STEPS = [
  { href: "/padroes", label: "Padrões encontrados" },
  { href: "/politica", label: "Política proposta" },
  { href: "/laboratorio", label: "Laboratório" },
  { href: "/pedidos", label: "Pedidos novos" },
];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export default function Sidebar() {
  const pathname = usePathname();
  const policy = useQuery({ queryKey: ["policy"], queryFn: api.policy });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });

  const hints: Record<string, string | undefined> = {
    "/politica": policy.data
      ? policy.data.approved_by
        ? `Versão ${policy.data.version}, aprovada por ${policy.data.approved_by}`
        : "Aguardando sua aprovação"
      : undefined,
    "/laboratorio": "Teste antes de aprovar",
  };
  const pending = policy.data && !policy.data.approved_by;
  const nav = useRef<HTMLElement>(null);
  // Mobile: the nav scrolls sideways, keep the current section in view.
  useEffect(() => {
    nav.current?.querySelector('[aria-current="page"]')?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [pathname]);

  return (
    <aside className="border-b border-border bg-surface md:sticky md:top-0 md:flex md:h-screen md:w-64 md:shrink-0 md:flex-col md:border-r md:border-b-0">
      <div className="px-4 pt-4 pb-3 md:px-5 md:pt-6">
        <Link href="/" className="text-base font-semibold tracking-tight">Fortuna Crédito</Link>
        <p className="text-xs text-muted">Painel do analista de risco</p>
      </div>
      <div className="px-4 pb-3 md:px-5 md:pb-5"><OrderSearch /></div>

      <nav ref={nav} aria-label="Seções" className="overflow-x-auto [scrollbar-width:none] px-2 pb-2 md:flex-1 md:px-3 md:pb-0">
        <ul className="flex gap-1 md:flex-col md:gap-0">
          <li>
            <Link
              href="/"
              aria-current={pathname === "/" ? "page" : undefined}
              className={`block whitespace-nowrap rounded-md px-3 py-2 text-sm ${pathname === "/" ? "bg-accent-soft font-medium text-foreground" : "text-muted hover:text-foreground"}`}
            >
              Visão geral
            </Link>
          </li>
          {STEPS.map((step, i) => {
            const active = isActive(pathname, step.href);
            const last = i === STEPS.length - 1;
            const warn = step.href === "/politica" && pending;
            return (
              <li key={step.href} className="relative">
                {/* rail connecting the steps (desktop only) */}
                {!last && <span aria-hidden className="absolute top-9 bottom-[-6px] left-[23px] hidden w-px bg-border md:block" />}
                <Link
                  href={step.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-start gap-3 whitespace-nowrap rounded-md px-3 py-2 md:whitespace-normal ${active ? "bg-accent-soft" : "hover:bg-background"}`}
                >
                  <span
                    aria-hidden
                    className={`relative z-10 mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold tabular-nums ${active ? "border-accent bg-accent text-white" : "border-border bg-surface text-muted"}`}
                  >
                    {i + 1}
                  </span>
                  <span className="min-w-0">
                    <span className={`block text-sm ${active ? "font-medium text-foreground" : "text-foreground/80"}`}>{step.label}</span>
                    {hints[step.href] && (
                      <span className={`hidden text-xs md:block ${warn ? "text-warning-fg" : "text-muted"}`}>
                        {warn && <span aria-hidden>● </span>}{hints[step.href]}
                      </span>
                    )}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="hidden px-5 py-4 text-xs md:block">
        {health.error ? (
          <p role="alert" className="rounded-md bg-critical/10 p-2 text-critical">{health.error.message}</p>
        ) : exampleDataWarning(health.data) ? (
          <p role="status" className="rounded-md bg-warning-bg p-2 text-warning-fg">{exampleDataWarning(health.data)}</p>
        ) : null}
        <p className="mt-3 text-muted">A IA sugere, o analista de risco decide.</p>
      </div>
    </aside>
  );
}
