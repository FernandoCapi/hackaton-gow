"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export default function StatusBanner() {
  const { error } = useQuery({ queryKey: ["health"], queryFn: api.health });
  if (!error) return null;
  return <p role="alert" className="bg-critical px-4 py-2 text-center text-sm text-white">{error.message}</p>;
}
