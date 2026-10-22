import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Flight Finder — Multi-agent tìm vé máy bay",
  description: "Đội Agent hiểu câu hỏi tự nhiên về chuyến bay, tìm và tóm tắt lựa chọn tốt nhất.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi">
      <body className="bg-stone-100 text-stone-900 antialiased">{children}</body>
    </html>
  );
}
