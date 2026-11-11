"use client";

import { useQuery } from "@tanstack/react-query";
import { FlaskConical, LayoutDashboard, ListChecks, Scale, Search, Sprout } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import OrderSearch from "./OrderSearch";
import ThemeToggle from "./ThemeToggle";

const SECTIONS = [
  { href: "/", label: "Visão geral", icon: LayoutDashboard },
  { href: "/padroes", label: "Padrões encontrados", icon: Search },
  { href: "/politica", label: "Política proposta", icon: Scale },
  { href: "/laboratorio", label: "Laboratório", icon: FlaskConical },
  { href: "/pedidos", label: "Pedidos novos", icon: ListChecks },
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
  const live = health.data?.mode === "live";
  const nav = useRef<HTMLElement>(null);
  // Mobile: the nav scrolls sideways, keep the current section in view.
  useEffect(() => {
    nav.current?.querySelector('[aria-current="page"]')?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [pathname]);

  return (
    <aside className="bg-sidebar text-sidebar-fg md:sticky md:top-0 md:flex md:h-screen md:w-68 md:shrink-0 md:flex-col">
      <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-4 md:px-5 md:pt-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-gold to-[#8a6510] text-white shadow-md">
            <Sprout className="size-5" aria-hidden />
          </span>
          <span>
            <span className="block text-base font-semibold tracking-tight">Fortuna Crédito</span>
            <span className="block text-xs text-sidebar-muted">Painel do analista de risco</span>
          </span>
        </Link>
        <ThemeToggle />
      </div>
      <div className="px-4 pb-4 md:px-5 md:pb-5"><OrderSearch /></div>

      <nav ref={nav} aria-label="Seções" className="overflow-x-auto [scrollbar-width:none] px-2 pb-3 md:flex-1 md:px-3 md:pb-0">
        <ul className="flex gap-1 md:flex-col">
          {SECTIONS.map((section) => {
            const active = section.href === "/" ? pathname === "/" : isActive(pathname, section.href);
            const warn = section.href === "/politica" && pending;
            const Icon = section.icon;
            return (
              <li key={section.href}>
                <Link
                  href={section.href}
                  aria-current={active ? "page" : undefined}
                  className={`flex items-start gap-3 whitespace-nowrap rounded-lg px-3 py-2.5 transition-colors md:whitespace-normal ${
                    active ? "bg-sidebar-active shadow-[inset_3px_0_0_var(--gold)]" : "hover:bg-sidebar-active/60"
                  }`}
                >
                  <Icon className={`mt-0.5 size-4 shrink-0 ${active ? "text-gold" : "text-sidebar-muted"}`} aria-hidden />
                  <span>
                    <span className={`block text-sm ${active ? "font-medium" : "text-sidebar-fg/85"}`}>{section.label}</span>
                    {hints[section.href] && (
                      <span className={`hidden text-xs md:block ${warn ? "text-gold" : "text-sidebar-muted"}`}>
                        {warn && <span aria-hidden>● </span>}{hints[section.href]}
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
          <p role="alert" className="rounded-md bg-critical/20 p-2 text-white">{health.error.message}</p>
        ) : (
          <p className="flex items-center gap-2 text-sidebar-muted">
            <span className={`size-2 rounded-full ${live ? "bg-emerald-400" : "bg-gold"}`} aria-hidden />
            {live ? "Motor ao vivo · dados de 30/09/2026" : "Dados de exemplo"}
          </p>
        )}
      </div>
    </aside>
  );
}
