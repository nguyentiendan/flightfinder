import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Flight Finder",
  description: "A multi-agent search that ranks cheap fares first and compares OTA links.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-stone-100 text-stone-900 antialiased">{children}</body>
    </html>
  );
}
