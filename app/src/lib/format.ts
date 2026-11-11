const brlFormat = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const intFormat = new Intl.NumberFormat("pt-BR");
const pctFormat = new Intl.NumberFormat("pt-BR", { style: "percent", maximumFractionDigits: 1 });

export const brl = (value: number) => brlFormat.format(value);
export const int = (value: number) => intFormat.format(value);
/** Rates come as fractions (0.12 = 12%). */
export const pct = (value: number) => pctFormat.format(value);
export const date = (iso: string) => new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR");

export function paramValue(value: number | string, unit?: string | null): string {
  if (typeof value === "string") return value;
  if (unit === "percent") return pct(value);
  if (unit === "brl") return brl(value);
  return int(value);
}
