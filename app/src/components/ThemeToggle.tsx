"use client";

import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";

const media = () => window.matchMedia("(prefers-color-scheme: dark)");

function current(): Theme {
  const chosen = document.documentElement.dataset.theme;
  if (chosen === "light" || chosen === "dark") return chosen;
  return media().matches ? "dark" : "light";
}

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  media().addEventListener("change", onChange);
  return () => {
    observer.disconnect();
    media().removeEventListener("change", onChange);
  };
}

export default function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, current, () => "light" as Theme);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      onClick={() => {
        document.documentElement.dataset.theme = next;
        try {
          localStorage.setItem("theme", next);
        } catch {}
      }}
      aria-label={next === "dark" ? "Usar tema escuro" : "Usar tema claro"}
      title={next === "dark" ? "Tema escuro" : "Tema claro"}
      className="rounded-lg px-2 py-1 text-sm text-sidebar-fg ring-1 ring-white/15 hover:bg-sidebar-active"
    >
      <span aria-hidden>{theme === "dark" ? "☀" : "☾"}</span>
    </button>
  );
}
