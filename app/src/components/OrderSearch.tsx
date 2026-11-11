"use client";

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
      className="flex gap-2"
    >
      <label htmlFor="order-search" className="sr-only">Número do pedido</label>
      <input
        id="order-search"
        value={id}
        onChange={(e) => setId(e.target.value)}
        placeholder="Nº do pedido"
        className="min-w-0 flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm"
      />
      <button className="rounded-md bg-foreground px-3 py-1.5 text-sm text-background">Abrir</button>
    </form>
  );
}
