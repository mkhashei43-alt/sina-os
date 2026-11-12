import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "سینا AI OS — سیستم‌عامل شخصی هوش مصنوعی",
  description: "داشبورد مدیریت عامل هوشمند خودمختار سینا",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
