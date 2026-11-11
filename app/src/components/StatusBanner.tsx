"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { exampleDataWarning } from "@/lib/health";

export default function StatusBanner() {
  const { data, error } = useQuery({ queryKey: ["health"], queryFn: api.health });
  if (error) {
    return <p role="alert" className="bg-critical px-4 py-2 text-center text-sm text-white">{error.message}</p>;
  }
  const warning = exampleDataWarning(data);
  if (!warning) return null;
  return <p role="status" className="bg-warning-bg px-4 py-2 text-center text-sm text-warning-fg">{warning}</p>;
}
