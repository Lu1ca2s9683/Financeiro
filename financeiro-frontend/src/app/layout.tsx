import type { Metadata } from 'next';
import { Inter, Geist } from 'next/font/google';
import './globals.css';
import { FinanceiroProvider } from '@/contexts/FinanceiroContext';
import { AuthProvider } from '@/contexts/AuthContext';
import { MainLayout } from '@/components/MainLayout';
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

const inter = Inter({ 
  subsets: ['latin'],
  variable: '--font-inter',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'Sistema Financeiro Corporativo',
  description: 'Gestão de Fechamento e Despesas',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR" className={cn("font-sans", geist.variable)}>
      <body className="font-sans antialiased bg-slate-50 text-slate-900">
        <AuthProvider>
          <FinanceiroProvider>
             <MainLayout>{children}</MainLayout>
          </FinanceiroProvider>
        </AuthProvider>
      </body>
    </html>
  );
}