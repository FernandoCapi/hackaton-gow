"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import OrderSearch from "./OrderSearch";
import ThemeToggle from "./ThemeToggle";

const SECTIONS = [
  { href: "/", label: "Visão geral" },
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
      <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-3 md:px-5 md:pt-6">
        <div>
          <Link href="/" className="text-base font-semibold tracking-tight">Fortuna Crédito</Link>
          <p className="text-xs text-muted">Painel do analista de risco</p>
        </div>
        <ThemeToggle />
      </div>
      <div className="px-4 pb-3 md:px-5 md:pb-5"><OrderSearch /></div>

      <nav ref={nav} aria-label="Seções" className="overflow-x-auto [scrollbar-width:none] px-2 pb-2 md:flex-1 md:px-3 md:pb-0">
        <ul className="flex gap-1 md:flex-col">
          {SECTIONS.map((section) => {
            const active = section.href === "/" ? pathname === "/" : isActive(pathname, section.href);
            const warn = section.href === "/politica" && pending;
            return (
              <li key={section.href}>
                <Link
                  href={section.href}
                  aria-current={active ? "page" : undefined}
                  className={`block whitespace-nowrap rounded-md px-3 py-2 md:whitespace-normal ${active ? "bg-accent-soft" : "hover:bg-background"}`}
                >
                  <span className={`block text-sm ${active ? "font-medium text-foreground" : "text-foreground/80"}`}>{section.label}</span>
                  {hints[section.href] && (
                    <span className={`hidden text-xs md:block ${warn ? "text-warning-fg" : "text-muted"}`}>
                      {warn && <span aria-hidden>● </span>}{hints[section.href]}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="hidden px-5 py-4 text-xs md:block">
        {health.error ? (
          <p role="alert" className="rounded-md bg-critical/10 p-2 text-critical">{health.error.message}</p>
        ) : null}
      </div>
    </aside>
  );
}
