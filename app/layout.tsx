import type { Metadata } from "next";
import "./globals.css";
import "./agroedge.css";

export const metadata: Metadata = {
  title: "AgroEdge IA · Monitoreo agroclimático",
  description: "Estación agroclimática del proyecto universitario AgroEdge IA en Toca, Boyacá.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
