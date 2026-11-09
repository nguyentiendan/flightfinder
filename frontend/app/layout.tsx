import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Flight Finder",
  description: "Ask for a trip, compare fares, then confirm the price on an airline site.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased">{children}</body>
    </html>
  );
}
