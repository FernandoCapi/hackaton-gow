import type { Metadata } from "next";
import { IBM_Plex_Sans } from "next/font/google";
import Providers from "./providers";
import Sidebar from "@/components/Sidebar";
import StatusBanner from "@/components/StatusBanner";
import "./globals.css";

const plex = IBM_Plex_Sans({ variable: "--font-plex", subsets: ["latin"], weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Fortuna Crédito — Painel de risco",
  description: "Padrões encontrados nos dados e política de crédito proposta para o analista de risco.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <head>
        {/* Applies the saved theme before first paint, so the page does not flash the other one. */}
        <script dangerouslySetInnerHTML={{ __html: `try{var t=localStorage.getItem("theme");if(t)document.documentElement.dataset.theme=t}catch(e){}` }} />
      </head>
      <body className={`${plex.variable} font-sans antialiased`}>
        <Providers>
          <div className="md:flex">
            <Sidebar />
            <div className="min-w-0 flex-1">
              {/* mobile only: the sidebar footer with the data status is hidden on small screens */}
              <div className="md:hidden"><StatusBanner /></div>
              <main className="mx-auto max-w-6xl px-4 py-6 md:px-8 md:py-8">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
