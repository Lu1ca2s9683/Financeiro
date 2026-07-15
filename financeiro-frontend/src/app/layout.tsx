import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { FinanceiroProvider } from "@/contexts/FinanceiroContext";
import { AuthProvider } from "@/contexts/AuthContext";
import { DateFilterProvider } from "@/contexts/DateFilterContext";
import { MainLayout } from "@/components/MainLayout";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Sistema Financeiro - Gestão",
  description: "Gestão Financeira e Conciliação",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className={inter.className + " bg-slate-50 text-slate-900"}>
        <AuthProvider>
          <FinanceiroProvider>
          <DateFilterProvider>
            <MainLayout>
              {children}
            </MainLayout>
          </DateFilterProvider>
          </FinanceiroProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
