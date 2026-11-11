"use client";

import { ArrowRight, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

/** Always visible: the jury may ask for a specific order live. */
export default function OrderSearch() {
  const router = useRouter();
  const [id, setId] = useState("");
  return (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        const value = id.trim().toUpperCase();
        if (value) router.push(`/pedidos/${encodeURIComponent(value)}`);
      }}
      className="flex items-center gap-1 rounded-lg bg-white/10 p-1 ring-1 ring-white/10 focus-within:ring-gold/60"
    >
      <Search className="ml-2 size-4 shrink-0 text-sidebar-muted" aria-hidden />
      <label htmlFor="order-search" className="sr-only">Número do pedido</label>
      <input
        id="order-search"
        value={id}
        onChange={(e) => setId(e.target.value)}
        placeholder="Nº do pedido (P-05909)"
        className="min-w-0 flex-1 bg-transparent px-1 py-1 text-sm text-sidebar-fg placeholder:text-sidebar-muted focus:outline-none"
      />
      <button aria-label="Abrir pedido" className="grid size-7 place-items-center rounded-md bg-gold text-[#2a1f02] hover:brightness-110">
        <ArrowRight className="size-4" aria-hidden />
      </button>
    </form>
  );
}
